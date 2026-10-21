"""Command line entry for a full audit run."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from audit_agent.agent import run_audit, write_outputs
from audit_agent.llm import OpenAICompatible, RecordingLLM, ReplayLLM
from audit_agent.sandbox import Sandbox
from audit_agent.state import load_state
from audit_agent.verifier import verify_state


TARGET_URL = "https://github.com/gwind/ylinux_old"
TARGET_COMMIT = "8a7316deec88287d020eca21c38dad921b623ffc"
DEFAULT_VENDOR = "lib/markdown"


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="audit-agent", description="Tool-calling audit of a local repository.")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Clone the target if needed and run the auditor/critic loop")
    run.add_argument("--target-url", default=os.getenv("AUDIT_TARGET_URL", TARGET_URL))
    run.add_argument("--target-dir", default="workspace/ylinux_old")
    run.add_argument("--commit", default=os.getenv("AUDIT_TARGET_COMMIT", TARGET_COMMIT), help="Commit to check out ('' keeps HEAD)")
    run.add_argument(
        "--local",
        action="store_true",
        help="Audit --target-dir as is (no clone, no checkout). --commit is then only recorded in the report",
    )
    run.add_argument(
        "--vendor",
        default=os.getenv("AUDIT_VENDOR_DIRS", DEFAULT_VENDOR),
        help="Comma-separated extra directories to skip by default (static/media/vendor names are always skipped)",
    )
    run.add_argument("--run-dir", default="")
    run.add_argument("--max-steps", type=int, default=int(os.getenv("AUDIT_MAX_STEPS", "80")))
    run.add_argument("--critic-steps", type=int, default=int(os.getenv("AUDIT_CRITIC_STEPS", "40")))
    run.add_argument("--resume-steps", type=int, default=int(os.getenv("AUDIT_RESUME_STEPS", "40")))
    run.add_argument("--max-rounds", type=int, default=int(os.getenv("AUDIT_MAX_ROUNDS", "3")))

    verify = sub.add_parser("verify", help="Re-check quotes in an existing run directory and re-render its report")
    verify.add_argument("run_dir")
    verify.add_argument("--target-dir", default="")

    replay = sub.add_parser("replay", help="Re-run a recorded audit offline from llm_responses.jsonl, no API key needed")
    replay.add_argument("run_dir")
    replay.add_argument("--target-dir", default="")
    replay.add_argument("--out", default="", help="Output directory. Default <run_dir>/replay")

    evaluate = sub.add_parser("evaluate", help="Score runs against a labelled ground truth file")
    evaluate.add_argument("run_dirs", nargs="+")
    evaluate.add_argument("--truth", default="eval/ground_truth.json")
    evaluate.add_argument("--out", default="", help="Write a markdown scorecard here")
    evaluate.add_argument("--group", action="append", default=[], help="name=dir1,dir2,... : report mean and spread over repeated runs")

    args = parser.parse_args(argv)
    load_dotenv(Path(".env"))
    if args.command == "verify":
        return _verify(Path(args.run_dir), _target_for(Path(args.run_dir), args.target_dir))
    if args.command == "replay":
        return _replay(Path(args.run_dir), _target_for(Path(args.run_dir), args.target_dir), args.out)
    if args.command == "evaluate":
        from audit_agent.evaluate import main as evaluate_main

        groups = {}
        for item in args.group:
            name, _, dirs = item.partition("=")
            groups[name] = [Path(part) for part in dirs.split(",") if part]
        return evaluate_main([Path(item) for item in args.run_dirs], Path(args.truth), Path(args.out) if args.out else None, groups)
    return _run(args)


def _target_for(run_dir: Path, explicit: str) -> Path:
    if explicit:
        return Path(explicit)
    meta_path = run_dir / "meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("target_dir"):
            return Path(meta["target_dir"])
    return Path("workspace/ylinux_old")


def _vendor_list(raw: str) -> list[str]:
    return [item.strip() for item in (raw or "").split(",") if item.strip()]


def _run(args) -> int:
    target = Path(args.target_dir)
    if args.local:
        if not target.is_dir():
            raise SystemExit(f"--local target does not exist: {target}")
        commit = args.commit or "unknown (local directory)"
    else:
        commit = ensure_checkout(args.target_url, target, args.commit)
    api_key, base_url, model = resolve_llm()
    effort = os.getenv("AUDIT_LLM_REASONING_EFFORT", "max").strip()
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    run_dir = Path(args.run_dir) if args.run_dir else Path("results") / stamp
    run_dir.mkdir(parents=True, exist_ok=True)
    recording = run_dir / "llm_responses.jsonl"
    recording.write_text("", encoding="utf-8")
    print(f"target={target.resolve()}", flush=True)
    print(f"commit={commit}", flush=True)
    print(f"model={model} base_url={base_url} reasoning_effort={effort or 'off'}", flush=True)
    base = OpenAICompatible(api_key=api_key, base_url=base_url, model=model, reasoning_effort=effort)
    critic_base = base
    critic_cfg = resolve_critic_llm()
    if critic_cfg:
        c_key, c_base, c_model, c_effort = critic_cfg
        critic_base = OpenAICompatible(api_key=c_key, base_url=c_base, model=c_model, reasoning_effort=c_effort)
        print(f"critic_model={c_model} critic_base_url={c_base}", flush=True)
    print(f"run_dir={run_dir.resolve()}", flush=True)
    vendor = _vendor_list(args.vendor)
    state = run_audit(
        sandbox=Sandbox(target, vendor),
        llm=RecordingLLM(base, recording, "auditor"),
        critic_llm=RecordingLLM(critic_base, recording, "critic"),
        run_dir=run_dir,
        commit=commit,
        target_url=args.target_url,
        auditor_steps=args.max_steps,
        critic_steps=args.critic_steps,
        resume_steps=args.resume_steps,
        max_rounds=args.max_rounds,
        extra_meta={"target_dir": target.as_posix(), "vendor": vendor},
    )
    confirmed = sum(1 for item in state.findings.values() if item.status == "confirmed")
    print(f"done findings={len(state.findings)} confirmed={confirmed} report={run_dir / 'report.md'}", flush=True)
    return 0


def _verify(run_dir: Path, target: Path) -> int:
    state_path = run_dir / "state.json"
    if not state_path.exists():
        print(f"missing {state_path}", file=sys.stderr)
        return 1
    state = load_state(state_path)
    meta_path = run_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    rows = verify_state(Sandbox(target, meta.get("vendor") or [DEFAULT_VENDOR]), state)
    failed = [row for row in rows if not row["ok"]]
    events = []
    trace_path = run_dir / "trace.jsonl"
    if trace_path.exists():
        events = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    write_outputs(run_dir, state, meta, rows, events)
    print(f"checked={len(rows)} failed={len(failed)} rewrote report in {run_dir}")
    return 1 if failed else 0


def _replay(run_dir: Path, target: Path, out: str) -> int:
    """Feed recorded model responses back through the real tools. Same tools + same responses must give the same findings."""
    recording = run_dir / "llm_responses.jsonl"
    if not recording.exists():
        print(f"missing {recording}; only runs made with this version record responses", file=sys.stderr)
        return 1
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    rows = ReplayLLM.load(recording)
    out_dir = Path(out) if out else run_dir / "replay"
    budgets = meta.get("budgets") or {}
    state = run_audit(
        sandbox=Sandbox(target, meta.get("vendor") or [DEFAULT_VENDOR]),
        llm=ReplayLLM(rows, "auditor", model=f"replay:{meta.get('model', '')}"),
        critic_llm=ReplayLLM(rows, "critic", model=f"replay:{meta.get('critic_model', meta.get('model', ''))}"),
        run_dir=out_dir,
        commit=meta.get("commit", ""),
        target_url=meta.get("target_url", ""),
        auditor_steps=budgets.get("auditor", 80),
        critic_steps=budgets.get("critic", 40),
        resume_steps=budgets.get("resume", 40),
        max_rounds=budgets.get("max_rounds", 3),
        extra_meta={"target_dir": target.as_posix(), "vendor": meta.get("vendor") or [], "replay_of": run_dir.as_posix()},
    )
    original = {item["id"]: (item["status"], item["severity"]) for item in json.loads((run_dir / "findings.json").read_text(encoding="utf-8"))}
    replayed = {item.id: (item.status, item.severity) for item in state.findings.values()}
    same = original == replayed
    print(f"replayed into {out_dir}: findings={len(replayed)} identical_to_original={same} unused_responses={len(rows)}")
    if not same:
        for key in sorted(set(original) | set(replayed)):
            if original.get(key) != replayed.get(key):
                print(f"  {key}: original={original.get(key)} replay={replayed.get(key)}")
    return 0 if same else 1


def ensure_checkout(url: str, dest: Path, commit: str = "") -> str:
    dest = dest.resolve()
    if not (dest / ".git").is_dir():
        if dest.exists():
            raise SystemExit(f"{dest} exists but is not a git checkout")
        _clone(url, dest)
    if commit and _rev_parse(dest) != commit:
        completed = subprocess.run(["git", "checkout", "-q", commit], cwd=dest, capture_output=True, text=True)
        if completed.returncode != 0:
            raise SystemExit(f"cannot check out {commit}: {completed.stderr.strip()}")
    return _rev_parse(dest)


def _clone(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    commands = [
        ["git", "clone", url, str(dest)],
        ["git", "-c", "http.https://github.com.proxy=", "-c", "https.https://github.com.proxy=", "clone", url, str(dest)],
    ]
    errors: list[str] = []
    for command in commands:
        if dest.exists():
            shutil.rmtree(dest)
        completed = subprocess.run(command, capture_output=True, text=True)
        if completed.returncode == 0:
            return
        errors.append((completed.stderr or completed.stdout or "git clone failed").strip())
    raise SystemExit("git clone failed:\n" + "\n---\n".join(errors))


def resolve_llm() -> tuple[str, str, str]:
    explicit = os.getenv("AUDIT_LLM_API_KEY", "").strip()
    if explicit:
        return (
            explicit,
            os.getenv("AUDIT_LLM_BASE_URL", "https://api.deepseek.com").strip(),
            os.getenv("AUDIT_LLM_MODEL", "deepseek-v4-pro").strip(),
        )
    providers = (
        ("DEEPSEEK", "https://api.deepseek.com", "deepseek-v4-pro"),
        ("OPENAI", "https://api.openai.com/v1", "gpt-4o-mini"),
        ("MOONSHOT", "https://api.moonshot.cn/v1", "kimi-k3"),
        ("DASHSCOPE", "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus"),
    )
    for prefix, default_base, default_model in providers:
        key = os.getenv(f"{prefix}_API_KEY", "").strip()
        if not key:
            continue
        base = os.getenv("AUDIT_LLM_BASE_URL", "").strip() or os.getenv(f"{prefix}_BASE_URL", "").strip() or default_base
        model = os.getenv("AUDIT_LLM_MODEL", "").strip() or os.getenv(f"{prefix}_MODEL", "").strip() or default_model
        return key, base, model
    raise SystemExit(
        "No LLM API key found. Set AUDIT_LLM_API_KEY, or one of "
        "DEEPSEEK_API_KEY / OPENAI_API_KEY / MOONSHOT_API_KEY / DASHSCOPE_API_KEY."
    )


def resolve_critic_llm() -> tuple[str, str, str, str] | None:
    """Optional separate critic model. Unset AUDIT_CRITIC_MODEL means the critic uses the auditor's model."""
    model = os.getenv("AUDIT_CRITIC_MODEL", "").strip()
    if not model:
        return None
    key = os.getenv("AUDIT_CRITIC_API_KEY", "").strip()
    base = os.getenv("AUDIT_CRITIC_BASE_URL", "").strip()
    if not key:
        key, default_base, _model = resolve_llm()
        base = base or default_base
    if not base:
        raise SystemExit("AUDIT_CRITIC_API_KEY is set but AUDIT_CRITIC_BASE_URL is empty")
    effort = os.getenv("AUDIT_CRITIC_REASONING_EFFORT", "").strip()
    return key, base, model, effort


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _rev_parse(dest: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=dest,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()
