"""Model-driven audit loop.

The model chooses every tool and the order. This module only sends the
conversation, executes the requested tool, appends the observation, and stops
when a terminal tool succeeds or the step budget runs out. Auditor and critic
are chained by the runner so a finished audit does not depend on a person
copying output between stages.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from audit_agent.llm import ContextTooLong, LLMResponse
from audit_agent.prompts import (
    AUDITOR_SYSTEM,
    CRITIC_SYSTEM,
    auditor_feedback,
    auditor_mission,
    critic_mission,
    near_limit,
)
from audit_agent.report import render_appendix, render_decisions, render_report, render_trajectory
from audit_agent.sandbox import Sandbox
from audit_agent.state import AuditState
from audit_agent.tools import ToolContext, execute_tool, openai_tools
from audit_agent.verifier import verify_state

MAX_CONTEXT_CHARS = 600_000
KEEP_RECENT_TOOL_OUTPUTS = 12
PACKET_LIMIT = 60_000


@dataclass
class LoopResult:
    steps: int
    stopped: bool
    reason: str


class Trace:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("", encoding="utf-8")
        self.events: list[dict] = []

    def write(self, event: dict) -> None:
        payload = {"ts": datetime.now().astimezone().isoformat(timespec="seconds"), **event}
        self.events.append(payload)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def compact_messages(messages: list[dict], max_chars: int = MAX_CONTEXT_CHARS) -> bool:
    """Replace old tool outputs with a stub, keeping every tool_call_id answered.

    Compacts down to 60% of the budget so the prompt prefix stays stable (and
    cacheable) for many steps between compactions. Returns True if anything changed.
    """
    if _chars(messages) <= max_chars:
        return False
    tool_indexes = [i for i, message in enumerate(messages) if message.get("role") == "tool"]
    candidates = tool_indexes[:-KEEP_RECENT_TOOL_OUTPUTS] if len(tool_indexes) > KEEP_RECENT_TOOL_OUTPUTS else []
    target = int(max_chars * 0.6)
    changed = False
    for index in candidates:
        if _chars(messages) <= target:
            break
        content = messages[index].get("content") or ""
        if content.startswith("[elided]"):
            continue
        messages[index] = {**messages[index], "content": "[elided] " + _summarize_tool_output(content)}
        changed = True
    for message in messages:
        if _chars(messages) <= target:
            break
        if message.get("role") == "assistant" and message.get("reasoning_content"):
            message["reasoning_content"] = ""
            changed = True
    return changed


def _summarize_tool_output(content: str) -> str:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return "old output removed; call the tool again if you need it"
    keep = {key: payload[key] for key in ("ok", "path", "start_line", "end_line", "pattern", "count", "lead_count", "id", "error") if key in payload}
    return json.dumps(keep, ensure_ascii=False) + " — old output removed to save context; call read_file / get_audit_state again instead of quoting from memory"


def run_loop(
    llm,
    ctx: ToolContext,
    messages: list[dict],
    max_steps: int,
    trace: Trace,
    usage: dict,
    state_path: Path,
) -> LoopResult:
    nudges = 0
    for step in range(1, max_steps + 1):
        if compact_messages(messages):
            trace.write({"role": ctx.role, "step": step, "kind": "compact", "chars": _chars(messages)})
        response = _complete(llm, ctx, messages, trace, step)
        for key in ("prompt_tokens", "completion_tokens", "reasoning_tokens", "cached_tokens"):
            value = int(getattr(response, key, 0) or 0)
            usage[key] = usage.get(key, 0) + value
            usage.setdefault("by_role", {}).setdefault(ctx.role, {})
            usage["by_role"][ctx.role][key] = usage["by_role"][ctx.role].get(key, 0) + value
        assistant: dict = {"role": "assistant", "content": response.content or ("" if not response.tool_calls else None)}
        if response.reasoning:
            assistant["reasoning_content"] = response.reasoning
        if response.tool_calls:
            assistant["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.name, "arguments": call.raw_arguments or "{}"},
                }
                for call in response.tool_calls
            ]
        messages.append(assistant)
        names = [call.name for call in response.tool_calls]
        print(f"[{ctx.role} {step}/{max_steps}] {', '.join(names) if names else 'no tool call'}", flush=True)
        trace.write(
            {
                "role": ctx.role,
                "step": step,
                "kind": "assistant",
                "text": (response.content or "")[:2000],
                "reasoning": (response.reasoning or "")[:3000],
                "tools": names,
                "finish_reason": getattr(response, "finish_reason", ""),
            }
        )
        if not response.tool_calls:
            nudges += 1
            if nudges >= 4:
                return LoopResult(step, False, "no_tool_calls")
            messages.append(
                {
                    "role": "user",
                    "content": "继续必须调用工具。审计员要结束时调用 finalize_report；复核员要结束时调用 accept_report。",
                }
            )
            continue
        nudges = 0
        stopped = False
        for call in response.tool_calls:
            if stopped:
                content = json.dumps({"ok": False, "error": "skipped: a terminal tool already succeeded in this batch"})
                messages.append({"role": "tool", "tool_call_id": call.id, "content": content})
                trace.write({"role": ctx.role, "step": step, "kind": "tool", "name": call.name, "arguments": _public_args(call.arguments), "stop": False, "preview": content})
                continue
            result = execute_tool(call.name, call.arguments, ctx)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result.content})
            print(f"    -> {call.name} stop={result.stop} chars={len(result.content)}", flush=True)
            trace.write(
                {
                    "role": ctx.role,
                    "step": step,
                    "kind": "tool",
                    "name": call.name,
                    "arguments": _public_args(call.arguments),
                    "stop": result.stop,
                    "preview": result.content[:2500],
                }
            )
            stopped = stopped or result.stop
        ctx.state.save(state_path)
        if stopped:
            return LoopResult(step, True, "tool_stop")
        if step == max_steps - 3:
            messages.append({"role": "user", "content": near_limit(ctx.role)})
    return LoopResult(max_steps, False, "max_steps")


def _complete(llm, ctx: ToolContext, messages: list[dict], trace: Trace, step: int) -> LLMResponse:
    budget = MAX_CONTEXT_CHARS
    for _attempt in range(3):
        try:
            return llm.complete(messages, openai_tools(ctx.role))
        except ContextTooLong as exc:
            budget //= 2
            compact_messages(messages, max_chars=budget)
            trace.write({"role": ctx.role, "step": step, "kind": "compact", "chars": _chars(messages), "text": str(exc)[:800]})
            print(f"[{ctx.role} {step}] context compacted after API limit", flush=True)
    return llm.complete(messages, openai_tools(ctx.role))


def run_audit(
    sandbox: Sandbox,
    llm,
    run_dir: Path,
    commit: str,
    target_url: str,
    auditor_steps: int = 80,
    critic_steps: int = 40,
    resume_steps: int = 40,
    max_rounds: int = 3,
    critic_llm=None,
    extra_meta: dict | None = None,
) -> AuditState:
    critic_llm = critic_llm or llm
    run_dir.mkdir(parents=True, exist_ok=True)
    state = AuditState()
    trace = Trace(run_dir / "trace.jsonl")
    state_path = run_dir / "state.json"
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0, "cached_tokens": 0}
    started = datetime.now().astimezone().isoformat(timespec="seconds")
    budgets = {"auditor": auditor_steps, "critic": critic_steps, "resume": resume_steps, "max_rounds": max_rounds}

    auditor_ctx = ToolContext(sandbox=sandbox, state=state, role="auditor")
    auditor_messages = [
        {"role": "system", "content": AUDITOR_SYSTEM},
        {"role": "user", "content": auditor_mission(commit, target_url)},
    ]
    rounds = 0
    verification: list = []
    try:
        first = run_loop(llm, auditor_ctx, auditor_messages, auditor_steps, trace, usage, state_path)
        if not state.finalized:
            state.warnings.append(f"auditor did not finalize ({first.reason} after {first.steps} steps)")

        for round_index in range(1, max_rounds + 1):
            rounds = round_index
            last = round_index == max_rounds
            gaps_before = len(state.gaps)
            state.critic_accepted = False
            critic_ctx = ToolContext(sandbox=sandbox, state=state, role="critic", allow_gaps=round_index == 1)
            critic_messages = [
                {"role": "system", "content": CRITIC_SYSTEM},
                {"role": "user", "content": critic_mission(_packet(state), round_index, last)},
            ]
            result = run_loop(critic_llm, critic_ctx, critic_messages, critic_steps, trace, usage, state_path)
            if not state.critic_accepted:
                state.warnings.append(f"critic round {round_index} did not accept ({result.reason})")
            new_gaps = len(state.gaps) > gaps_before
            if not new_gaps and not _needs_resume(state):
                break
            if last:
                break
            state.finalized = False
            auditor_messages.append({"role": "user", "content": auditor_feedback(_packet(state))})
            resumed = run_loop(llm, auditor_ctx, auditor_messages, resume_steps, trace, usage, state_path)
            if not state.finalized:
                state.warnings.append(f"auditor resume {round_index} did not finalize ({resumed.reason})")

        for finding in state.findings.values():
            if finding.status == "disputed":
                finding.status = "needs_review"
                finding.history.append("复核轮次用尽仍有异议，降为 needs_review")
        verification = verify_state(sandbox, state)
    except Exception as exc:
        state.warnings.append(f"run interrupted: {exc}")
        trace.write({"role": "runner", "step": 0, "kind": "error", "text": str(exc)[:2000]})
        verification = verify_state(sandbox, state)
        raise
    finally:
        meta = build_meta(state, trace, usage, target_url, commit, llm, started, budgets, rounds, critic_llm)
        meta.update(extra_meta or {})
        write_outputs(run_dir, state, meta, verification, trace.events)
    return state


def build_meta(state, trace, usage, target_url, commit, llm, started, budgets, rounds, critic_llm=None) -> dict:
    critic_llm = critic_llm or llm
    reviews = [event for event in trace.events if event.get("kind") == "tool" and event.get("name") == "review_finding"]
    accepted = [event for event in reviews if '"ok": true' in (event.get("preview") or "")]
    disputes = sum(1 for event in accepted if (event.get("arguments") or {}).get("verdict") == "dispute")
    return {
        "target_url": target_url,
        "commit": commit,
        "model": getattr(llm, "model", "unknown"),
        "base_url": str(getattr(llm, "base_url", "") or ""),
        "reasoning_effort": getattr(llm, "reasoning_effort", "") or "",
        "critic_model": getattr(critic_llm, "model", "unknown"),
        "critic_base_url": str(getattr(critic_llm, "base_url", "") or ""),
        "critic_reviews": len(accepted),
        "critic_disputes": disputes,
        "started_at": started,
        "finished_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "budgets": budgets,
        "critic_rounds": rounds,
        **usage,
        "tool_sequence": [event["name"] for event in trace.events if event.get("kind") == "tool"],
        "warnings": state.warnings,
        "finalized": state.finalized,
        "critic_accepted": state.critic_accepted,
    }


def write_outputs(run_dir: Path, state: AuditState, meta: dict, verification: list, events: list[dict]) -> None:
    (run_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "findings.json").write_text(
        json.dumps([item.to_dict() for item in state.findings.values()], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_dir / "verification.json").write_text(json.dumps(verification, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "report.md").write_text(render_report(state, meta, verification, events), encoding="utf-8")
    (run_dir / "appendix.md").write_text(render_appendix(state, meta, verification, events), encoding="utf-8")
    if events:
        (run_dir / "trajectory.md").write_text(render_trajectory(events), encoding="utf-8")
        (run_dir / "decisions.md").write_text(render_decisions(events), encoding="utf-8")
    state.save(run_dir / "state.json")


def _needs_resume(state: AuditState) -> bool:
    if any(not gap.resolved for gap in state.gaps):
        return True
    return any(finding.status == "disputed" for finding in state.findings.values())


def _packet(state: AuditState) -> str:
    """Structured hand-off between roles. Shrinks by dropping detail, never by slicing JSON."""
    findings = [item.to_dict() for item in state.findings.values()]
    payload = {
        "findings": findings,
        "gaps": [gap.to_dict() for gap in state.gaps],
        "leads": [lead.to_dict() for lead in state.leads.values()],
        "files_read": state.files_read,
        "warnings": state.warnings,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=1)
    if len(text) <= PACKET_LIMIT:
        return text
    payload["leads"] = [{"id": lead.id, "rule_id": lead.rule_id, "path": lead.path, "disposition": lead.disposition} for lead in state.leads.values()]
    for item in findings:
        item.pop("history", None)
        for ev in item["evidence"]:
            ev["quote"] = ev["quote"][:300]
    return json.dumps(payload, ensure_ascii=False, indent=1)


def _chars(messages: list[dict]) -> int:
    return sum(len(json.dumps(message, ensure_ascii=False)) for message in messages)


def _public_args(arguments: dict | None):
    if arguments is None:
        return None
    text = json.dumps(arguments, ensure_ascii=False)
    if len(text) <= 4000:
        return arguments
    return {"_truncated": text[:4000]}