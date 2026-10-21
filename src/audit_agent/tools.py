"""Tool schemas and handlers.

The model sees the schemas. The loop executes whatever name the model picks.
Nothing here walks the repository on its own.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from audit_agent.endpoints import list_endpoints as _list_endpoints
from audit_agent.sandbox import Sandbox, SandboxError
from audit_agent.scanner import CATEGORIES, SURFACE_RULES, group_hits, scan
from audit_agent.state import AuditState, Evidence, Finding, Gap, Lead
from audit_agent.verifier import check_quote

STAGES = ["recon", "hunt", "investigate", "verify"]
STATUSES = ["candidate", "confirmed", "rejected", "needs_review"]
LEAD_DISPOSITIONS = ["finding", "benign", "duplicate"]
FLOW_CATEGORIES = {"injection", "xss", "file_access", "redirect", "deserialization", "access_control"}
CRITIC_VERDICTS = ["agree", "dispute"]
SEVERITIES = ["critical", "high", "medium", "low", "info"]
CONFIDENCE = ["high", "medium", "low"]
ENTRY_ROLES = ["anonymous", "registered_open", "registered_restricted", "privileged", "not_applicable"]
CATEGORIES_ENUM = [
    "injection",
    "xss",
    "auth",
    "access_control",
    "csrf",
    "crypto",
    "deserialization",
    "file_access",
    "config",
    "redirect",
    "xml",
    "sensitive_data",
    "other",
]
READ_WINDOW = 180
CWE_RE = re.compile(r"^CWE-\d+$")


@dataclass
class ToolResult:
    content: str
    stop: bool = False


@dataclass
class ToolContext:
    sandbox: Sandbox
    state: AuditState
    role: str
    allow_gaps: bool = True
    files_read_this_role: set[str] = field(default_factory=set)
    read_ranges: dict[str, list[tuple[int, int, int]]] = field(default_factory=dict)

    def covered(self, path: str, start: int, end: int, margin: int = 10) -> bool:
        """True if one read window covers the cited lines plus some context (or the whole file)."""
        for low, high, total in self.read_ranges.get(path, []):
            need_low = max(1, start - margin)
            need_high = min(total, end + margin)
            if low <= need_low and high >= need_high:
                return True
        return False


def openai_tools(role: str) -> list[dict]:
    names = AUDITOR_TOOLS if role == "auditor" else CRITIC_TOOLS
    return [SCHEMAS[name] for name in names]


def execute_tool(name: str, arguments: dict | None, ctx: ToolContext) -> ToolResult:
    if arguments is None:
        return _err("arguments are not valid JSON")
    handler = HANDLERS.get(name)
    allowed = AUDITOR_TOOLS if ctx.role == "auditor" else CRITIC_TOOLS
    if handler is None or name not in allowed:
        return _err(f"unknown tool for {ctx.role}: {name}")
    try:
        return handler(arguments, ctx)
    except SandboxError as exc:
        return _err(str(exc))
    except (TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
        return _err(f"invalid arguments: {exc}")
    except OSError as exc:
        return _err(f"filesystem error: {exc}")


def _ok(**payload) -> ToolResult:
    payload["ok"] = True
    return ToolResult(_dump(payload))


def _err(message: str, **payload) -> ToolResult:
    payload["ok"] = False
    payload["error"] = message
    return ToolResult(_dump(payload))


def _stop(**payload) -> ToolResult:
    payload["ok"] = True
    return ToolResult(_dump(payload), stop=True)


def _dump(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _schema(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


def _str(description: str) -> dict:
    return {"type": "string", "description": description}


def _int(description: str) -> dict:
    return {"type": "integer", "description": description}


def _bool(description: str) -> dict:
    return {"type": "boolean", "description": description}


def _enum(description: str, values: list[str]) -> dict:
    return {"type": "string", "enum": values, "description": description}


def _as_int(value, name: str) -> int:
    if isinstance(value, bool):
        raise TypeError(name)
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    raise TypeError(f"{name} must be an integer")


def _as_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, str):
        parsed = json.loads(value)
        if not isinstance(parsed, list):
            raise TypeError("expected a list")
        return parsed
    if not isinstance(value, list):
        raise TypeError("expected a list")
    return value


def _require(args: dict, *keys: str) -> None:
    missing = [key for key in keys if key not in args or args[key] in ("", None, [])]
    if missing:
        raise ValueError("missing " + ", ".join(missing))


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...[truncated {len(text) - limit} chars]"


def list_files(args: dict, ctx: ToolContext) -> ToolResult:
    path = str(args.get("path") or ".")
    glob = str(args.get("glob") or "*")
    max_depth = _as_int(args.get("max_depth", 3), "max_depth")
    max_entries = _as_int(args.get("max_entries", 200), "max_entries")
    include_vendor = _as_bool(args.get("include_vendor"), False)
    max_depth = min(max(max_depth, 0), 8)
    max_entries = min(max(max_entries, 1), 400)
    base = ctx.sandbox.resolve(path)
    if not base.exists():
        return _err(f"path not found: {path}")
    rows: list[str] = []
    truncated = False
    if base.is_file():
        rows.append(ctx.sandbox.rel(base))
    else:
        for file_path in ctx.sandbox.iter_files(path, include_vendor, glob, max_depth):
            if len(rows) >= max_entries:
                truncated = True
                break
            rows.append(ctx.sandbox.rel(file_path))
    ctx.state.listed = True
    return _ok(path=path, count=len(rows), truncated=truncated, skipped_by_default=ctx.sandbox.vendor_description(), files=rows)


def read_file(args: dict, ctx: ToolContext) -> ToolResult:
    _require(args, "path")
    path = str(args["path"])
    start = _as_int(args.get("start_line", 1), "start_line")
    if "end_line" in args and args["end_line"] not in (None, ""):
        end = _as_int(args["end_line"], "end_line")
    else:
        end = start + READ_WINDOW - 1
    if end - start + 1 > READ_WINDOW:
        end = start + READ_WINDOW - 1
    window = ctx.sandbox.read_window(path, start, end)
    ctx.state.remember_read(window["path"])
    ctx.files_read_this_role.add(window["path"])
    ctx.read_ranges.setdefault(window["path"], []).append(
        (window["start_line"], window["end_line"], window["total_lines"])
    )
    body = _clip(window["text"], 12000)
    return _ok(
        path=window["path"],
        encoding=window["encoding"],
        total_lines=window["total_lines"],
        start_line=window["start_line"],
        end_line=window["end_line"],
        note="Line prefixes like '12| ' are not part of the file. Quotes must omit them.",
        content=body,
    )


def search_code(args: dict, ctx: ToolContext) -> ToolResult:
    _require(args, "pattern")
    pattern = str(args["pattern"])
    if len(pattern) > 200:
        return _err("pattern is too long")
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        return _err(f"invalid regex: {exc}")
    path = str(args.get("path") or ".")
    glob = str(args.get("glob") or "*.py")
    include_vendor = _as_bool(args.get("include_vendor"), False)
    max_matches = min(_as_int(args.get("max_matches", 40), "max_matches"), 80)
    matches = []
    for file_path in ctx.sandbox.iter_files(path, include_vendor, glob, max_depth=12):
        if len(matches) >= max_matches:
            break
        try:
            rel, _encoding, text = ctx.sandbox.read_text(ctx.sandbox.rel(file_path))
        except (SandboxError, OSError, ValueError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if compiled.search(line):
                matches.append({"path": rel, "line": lineno, "text": line.strip()[:240]})
                if len(matches) >= max_matches:
                    break
    ctx.state.searches += 1
    return _ok(pattern=pattern, count=len(matches), matches=matches)


REFERENCE_SUFFIXES = {".py", ".html", ".htm", ".txt", ".xml", ".fcgi", ".cfg", ".ini"}


def find_references(args: dict, ctx: ToolContext) -> ToolResult:
    _require(args, "symbol")
    symbol = str(args["symbol"]).strip()
    if not re.fullmatch(r"[A-Za-z_][\w.]{0,119}", symbol):
        return _err("symbol must be an identifier or dotted name such as SESSION_ENGINE or settings.SECRET_KEY")
    name = symbol.rsplit(".", 1)[-1]
    word = re.compile(rf"(?<![\w]){re.escape(name)}(?!\w)")
    definition = re.compile(rf"^\s*(def|class)\s+{re.escape(name)}\b|^\s*{re.escape(name)}\s*(=(?!=)|:\s*\w+\s*=)")
    include_vendor = _as_bool(args.get("include_vendor"), False)
    path = str(args.get("path") or ".")
    rows: dict[str, list[dict]] = {"definitions": [], "imports": [], "uses": []}
    cap = 80
    total = 0
    for file_path in ctx.sandbox.iter_files(path, include_vendor, "*", max_depth=12):
        if file_path.suffix.lower() not in REFERENCE_SUFFIXES and file_path.suffix:
            continue
        try:
            rel, _encoding, text = ctx.sandbox.read_text(ctx.sandbox.rel(file_path))
        except (SandboxError, OSError, ValueError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if not word.search(line):
                continue
            total += 1
            stripped = line.strip()
            kind = "definitions" if definition.search(line) else "imports" if re.match(r"(from|import)\s", stripped) else "uses"
            if sum(len(items) for items in rows.values()) < cap:
                rows[kind].append({"path": rel, "line": lineno, "text": stripped[:200]})
    ctx.state.searches += 1
    return _ok(
        symbol=symbol,
        matched_name=name,
        total=total,
        truncated=total > cap,
        note="Word-boundary text match on the last name segment, not import resolution. "
        "No definitions means the framework default applies; read the code before relying on that.",
        **rows,
    )


def list_endpoints(args: dict, ctx: ToolContext) -> ToolResult:
    result = _list_endpoints(ctx.sandbox, str(args.get("root_urlconf") or "").strip())
    endpoints = result["endpoints"]
    ctx.state.endpoints_listed = True
    rows = [item.to_dict() for item in endpoints]
    flagged = sum(1 for item in endpoints if item.flags)
    return _ok(
        root_urlconf=result["root_urlconf"],
        note=(
            (result.get("note") or result.get("error") or "")
            + ". Text-based map of route -> view -> decorators and body hints. auth lists checks seen in the decorators or body "
            "(an is_authenticated check deep in a branch still counts). flags are heuristics, not findings: "
            "writes_without_auth_check, writes_on_any_method (state change without a method check), "
            "object_id_without_owner_check (route takes an id, no request.user use, no role check), csrf_exempt. "
            "read_file the view before concluding anything."
        ),
        count=len(rows),
        resolved=sum(1 for item in endpoints if item.file),
        flagged=flagged,
        unresolved_includes=result["unresolved_includes"],
        endpoints=rows,
    )


def pattern_scan(args: dict, ctx: ToolContext) -> ToolResult:
    raw_categories = args.get("categories")
    categories = [str(item) for item in _as_list(raw_categories)] if raw_categories else None
    if categories:
        unknown = sorted(set(categories) - set(CATEGORIES))
        if unknown:
            return _err(f"unknown categories: {unknown}", available=CATEGORIES)
    path = str(args.get("path") or ".")
    include_vendor = _as_bool(args.get("include_vendor"), False)
    hits, truncated = scan(ctx.sandbox, path, categories, include_vendor)
    ctx.state.scans += 1
    groups = group_hits(hits)
    surface = []
    leads = []
    for row in groups:
        if row["rule_id"] in SURFACE_RULES:
            surface.append({"rule_id": row["rule_id"], "path": row["path"], "count": len(row["lines"])})
            continue
        lead = _register_lead(ctx.state, row)
        leads.append({**lead.to_dict(), "snippets": row["snippets"]})
    return _ok(
        note=(
            "Each lead groups one rule in one file. Leads are candidates, not findings. "
            "Before finalize_report every lead must be triaged with triage_leads: link it to a finding id, "
            "or dismiss it as benign after you read_file the code around it."
        ),
        available_categories=CATEGORIES,
        lead_count=len(leads),
        truncated=truncated,
        leads=leads,
        surface=surface,
    )


def _register_lead(state: AuditState, row: dict) -> Lead:
    for lead in state.leads.values():
        if lead.rule_id == row["rule_id"] and lead.path == row["path"]:
            lead.lines = sorted(set(lead.lines) | set(row["lines"]))
            return lead
    lead = Lead(
        id=f"L{len(state.leads) + 1}",
        rule_id=row["rule_id"],
        category=row["category"],
        path=row["path"],
        lines=list(row["lines"]),
        snippet=row["snippets"][0] if row["snippets"] else "",
    )
    state.leads[lead.id] = lead
    return lead


def triage_leads(args: dict, ctx: ToolContext) -> ToolResult:
    _require(args, "ids", "disposition", "note")
    ids = [str(item).strip() for item in _as_list(args["ids"])]
    disposition = str(args["disposition"]).strip()
    note = str(args["note"]).strip()
    if disposition not in LEAD_DISPOSITIONS:
        return _err(f"disposition must be one of {LEAD_DISPOSITIONS}")
    if len(note) < 15:
        return _err("note must explain the judgement (at least 15 characters)")
    finding_id = str(args.get("finding_id") or "").strip()
    if disposition == "finding" and finding_id not in ctx.state.findings:
        return _err("disposition=finding needs finding_id of an existing finding; upsert_finding first")
    done, failures = [], []
    for lead_id in ids:
        lead = ctx.state.leads.get(lead_id)
        if lead is None:
            failures.append({"id": lead_id, "error": "unknown lead"})
            continue
        if disposition == "benign" and lead.path not in ctx.state.files_read:
            failures.append({"id": lead_id, "error": f"read_file {lead.path} before dismissing this lead"})
            continue
        lead.disposition = f"finding:{finding_id}" if disposition == "finding" else disposition
        lead.note = note
        done.append(lead_id)
    pending = [lead.id for lead in ctx.state.leads.values() if not lead.disposition]
    payload = {"triaged": done, "pending_leads": pending}
    if failures:
        return _err("some leads were not triaged", failures=failures, **payload)
    return _ok(**payload)


def set_stage(args: dict, ctx: ToolContext) -> ToolResult:
    _require(args, "stage", "note")
    stage = str(args["stage"])
    note = str(args["note"]).strip()
    if stage not in STAGES:
        return _err(f"stage must be one of {STAGES}")
    if len(note) < 8:
        return _err("note must describe what you actually learned (at least 8 characters)")
    precondition = _stage_precondition(stage, ctx.state)
    if precondition:
        return _err(precondition)
    ctx.state.stages.append({"stage": stage, "note": note})
    return _ok(stage=stage, completed=sorted(ctx.state.stage_names()))


def _stage_precondition(stage: str, state: AuditState) -> str:
    read_names = {path.rsplit("/", 1)[-1] for path in state.files_read}
    if stage == "recon" and not (state.listed or state.endpoints_listed or {"settings.py", "urls.py"} & read_names):
        return "read the tree or settings.py/urls.py before marking recon"
    if stage == "hunt" and state.scans + state.searches < 1:
        return "run pattern_scan or search_code before marking hunt"
    if stage == "investigate" and len(state.files_read) < 3:
        return "read at least 3 files before marking investigate"
    if stage == "verify" and not state.findings:
        return "upsert at least one finding before marking verify"
    return ""


def upsert_finding(args: dict, ctx: ToolContext) -> ToolResult:
    _require(args, "id", "title", "category", "status", "summary")
    status = str(args["status"])
    if status not in STATUSES:
        return _err(f"status must be one of {STATUSES}")
    category = str(args["category"])
    if category not in CATEGORIES_ENUM:
        return _err(f"category must be one of {CATEGORIES_ENUM}")
    severity = str(args.get("severity") or "info")
    confidence = str(args.get("confidence") or "medium")
    if severity not in SEVERITIES:
        return _err(f"severity must be one of {SEVERITIES}")
    if confidence not in CONFIDENCE:
        return _err(f"confidence must be one of {CONFIDENCE}")
    cwe = str(args.get("cwe") or "").strip()
    summary = str(args.get("summary") or "").strip()
    impact = str(args.get("impact") or "").strip()
    remediation = str(args.get("remediation") or "").strip()
    trigger = str(args.get("trigger") or "").strip()
    data_flow = str(args.get("data_flow") or "").strip()
    entry_role = str(args.get("entry_role") or "").strip()
    if entry_role and entry_role not in ENTRY_ROLES:
        return _err(f"entry_role must be one of {ENTRY_ROLES}")
    if status in {"confirmed", "needs_review"}:
        if len(summary) < 15 or len(impact) < 15 or len(remediation) < 15 or len(trigger) < 15:
            return _err("confirmed/needs_review findings need summary, impact, remediation, and trigger of at least 15 characters each")
        if not CWE_RE.match(cwe):
            return _err("cwe must look like CWE-89")
        if not entry_role:
            return _err(
                "entry_role is required for confirmed/needs_review: who can reach the entry point. "
                "anonymous; registered_open (any visitor can sign up); registered_restricted (accounts are invite/admin-made); "
                "privileged (staff/admin/permission); not_applicable (config or code-level issue with no request entry). "
                "Base it on the decorators and checks you read, and on whether registration is open."
            )
    if status == "confirmed" and category in FLOW_CATEGORIES and len(data_flow) < 20:
        return _err(
            "confirmed findings in flow categories need data_flow: name the untrusted source "
            "(request param, header, stored user content, upload name...), each hop, and the sink. "
            "If you cannot name the source from code you read, use needs_review or rejected."
        )
    evidence, errors = _parse_evidence(args.get("evidence"), ctx, required=status != "candidate")
    if errors:
        return _err("evidence quote did not match the file", failures=errors)
    if status in {"confirmed", "needs_review", "rejected"} and not evidence:
        return _err("this status requires at least one evidence item with a verbatim quote")
    finding_id = str(args["id"]).strip()
    if not finding_id:
        return _err("id is empty")
    previous = ctx.state.findings.get(finding_id)
    history = list(previous.history) if previous else []
    if previous and previous.status == "disputed":
        history.append(f"复核员否决：{previous.dispute_reason}")
    if previous and previous.status != status:
        history.append(f"状态 {previous.status} → {status}")
    finding = Finding(
        id=finding_id,
        title=str(args["title"]).strip(),
        category=category,
        status=status,
        severity=severity,
        confidence=confidence,
        cwe=cwe,
        summary=summary,
        impact=impact,
        remediation=remediation,
        trigger=trigger,
        evidence=evidence,
        dispute_reason=previous.dispute_reason if previous else "",
        data_flow=data_flow,
        history=history,
        entry_role=entry_role,
    )
    ctx.state.findings[finding.id] = finding
    duplicates = [
        other.id
        for other in ctx.state.findings.values()
        if other.id != finding.id
        and other.status != "rejected"
        and any((a.path, a.start_line) == (b.path, b.start_line) for a in other.evidence for b in finding.evidence)
    ]
    payload = {"id": finding.id, "status": finding.status, "evidence_count": len(evidence)}
    if duplicates:
        payload["warning"] = f"evidence overlaps with {duplicates}; merge them if they describe the same issue"
    return _ok(**payload)


def _parse_evidence(raw, ctx: ToolContext, required: bool) -> tuple[list[Evidence], list[dict]]:
    items = _as_list(raw)
    if required and not items:
        return [], [{"error": "evidence is required"}]
    evidence: list[Evidence] = []
    failures: list[dict] = []
    for item in items:
        if isinstance(item, str):
            item = json.loads(item)
        if not isinstance(item, dict):
            failures.append({"error": "evidence item is not an object"})
            continue
        path = str(item.get("path") or "")
        start = _as_int(item.get("start_line"), "start_line")
        end = _as_int(item.get("end_line"), "end_line")
        quote = str(item.get("quote") or "")
        ok, detail = check_quote(ctx.sandbox, path, start, end, quote)
        if not ok:
            structural = detail.startswith("line range") or "must" in detail or "escapes" in detail or "not a file" in detail
            failures.append(
                {
                    "path": path,
                    "start_line": start,
                    "end_line": end,
                    "error": detail if structural else "quote not found in that line range",
                    "actual": detail[:1500],
                }
            )
            continue
        evidence.append(Evidence(path=ctx.sandbox.rel(ctx.sandbox.resolve(path)), start_line=start, end_line=end, quote=quote))
    return evidence, failures


def mark_reviewed(args: dict, ctx: ToolContext) -> ToolResult:
    _require(args, "path", "note")
    path = str(args["path"])
    resolved = ctx.sandbox.resolve(path)
    if not resolved.exists():
        return _err(f"path not found: {path}")
    rel = ctx.sandbox.rel(resolved) if resolved.is_file() else ctx.sandbox.rel(resolved)
    note = str(args["note"]).strip()
    ctx.state.reviewed.append({"path": rel, "note": note})
    return _ok(path=rel)


def get_audit_state(args: dict, ctx: ToolContext) -> ToolResult:
    findings = []
    for finding in ctx.state.findings.values():
        findings.append(
            {
                "id": finding.id,
                "title": finding.title,
                "status": finding.status,
                "severity": finding.severity,
                "category": finding.category,
                "cwe": finding.cwe,
                "trigger": finding.trigger,
                "entry_role": finding.entry_role,
                "summary": finding.summary,
                "data_flow": finding.data_flow,
                "dispute_reason": finding.dispute_reason,
                "critic_verdict": finding.critic_verdict,
                "evidence": [item.to_dict() for item in finding.evidence],
            }
        )
    return _ok(
        stages=ctx.state.stages,
        stage_names=sorted(ctx.state.stage_names()),
        files_read=ctx.state.files_read,
        searches=ctx.state.searches,
        scans=ctx.state.scans,
        findings=findings,
        pending_leads=[lead.to_dict() for lead in ctx.state.leads.values() if not lead.disposition],
        triaged_leads=sum(1 for lead in ctx.state.leads.values() if lead.disposition),
        gaps=[gap.to_dict() for gap in ctx.state.gaps],
        reviewed=ctx.state.reviewed[-30:],
        finalized=ctx.state.finalized,
    )


def finalize_report(args: dict, ctx: ToolContext) -> ToolResult:
    _require(args, "executive_summary", "risk_overview", "scope", "limitations")
    problems = _finalize_problems(ctx.state, ctx.sandbox)
    if problems:
        return _err("audit is not ready to finalize", problems=problems)
    ctx.state.executive_summary = str(args["executive_summary"]).strip()
    ctx.state.risk_overview = str(args["risk_overview"]).strip()
    ctx.state.scope = str(args["scope"]).strip()
    ctx.state.limitations = str(args["limitations"]).strip()
    for field_name in ("executive_summary", "risk_overview", "scope", "limitations"):
        if len(getattr(ctx.state, field_name)) < 20:
            return _err(f"{field_name} is too short")
    ctx.state.finalized = True
    return _stop(message="report accepted", finding_count=len(ctx.state.findings))


def _finalize_problems(state: AuditState, sandbox: Sandbox) -> list[str]:
    problems: list[str] = []
    missing_stages = [stage for stage in STAGES if stage not in state.stage_names()]
    if missing_stages:
        problems.append("call set_stage for: " + ", ".join(missing_stages))
    read = set(state.files_read)
    names = {path.rsplit("/", 1)[-1] for path in read}
    if "settings.py" not in names:
        problems.append("read settings.py")
    if "urls.py" not in names:
        problems.append("read urls.py")
    views = sorted(sandbox.rel(path) for path in sandbox.iter_files(".", False, "views.py", 12))
    unread_views = [path for path in views if path not in read]
    if views and len(unread_views) > len(views) // 5:
        problems.append(
            f"read at least 80% of the views.py entry points ({len(views) - len(unread_views)}/{len(views)} so far). "
            "Unread: " + ", ".join(unread_views)
        )
    if state.scans < 1:
        problems.append("run pattern_scan at least once")
    if state.searches < 1:
        problems.append("run search_code at least once")
    pending = [lead.id for lead in state.leads.values() if not lead.disposition]
    if pending:
        problems.append("triage_leads for every pattern_scan lead. Pending: " + ", ".join(pending))
    if any(finding.status == "candidate" for finding in state.findings.values()):
        problems.append("resolve candidate findings to confirmed, rejected, or needs_review")
    if any(finding.status == "disputed" for finding in state.findings.values()):
        problems.append("resolve disputed findings to confirmed, rejected, or needs_review")
    unresolved = [gap.id for gap in state.gaps if not gap.resolved]
    if unresolved:
        problems.append("resolve gaps: " + ", ".join(unresolved))
    return problems


def resolve_gap(args: dict, ctx: ToolContext) -> ToolResult:
    _require(args, "id", "resolution")
    gap_id = str(args["id"])
    resolution = str(args["resolution"]).strip()
    if len(resolution) < 15:
        return _err("resolution is too short")
    for gap in ctx.state.gaps:
        if gap.id == gap_id:
            if len(ctx.state.files_read) <= gap.files_read_at_open and ctx.state.searches <= gap.searches_at_open:
                return _err("search_code or read_file the implementation behind this gap before resolving it; do not answer from framework defaults")
            gap.resolved = True
            gap.resolution = resolution
            return _ok(id=gap.id, resolved=True)
    return _err(f"unknown gap {gap_id}")


def review_finding(args: dict, ctx: ToolContext) -> ToolResult:
    _require(args, "id", "weakest_point", "verdict", "reason")
    finding_id = str(args["id"])
    weakest = str(args["weakest_point"]).strip()
    verdict = str(args["verdict"]).strip()
    reason = str(args["reason"]).strip()
    if verdict not in CRITIC_VERDICTS:
        return _err(f"verdict must be one of {CRITIC_VERDICTS}")
    if len(weakest) < 15:
        return _err("weakest_point must name the least supported claim in this finding (source, reachability, entry_role, sanitizer, config in effect, or severity)")
    if len(reason) < 15:
        return _err("reason is too short")
    finding = ctx.state.findings.get(finding_id)
    if finding is None:
        return _err(f"unknown finding {finding_id}")
    if finding.status == "rejected":
        return _err("rejected findings do not need review")
    uncovered = [
        f"{item.path}:{item.start_line}-{item.end_line}"
        for item in finding.evidence
        if not ctx.covered(item.path, item.start_line, item.end_line)
    ]
    if uncovered:
        return _err(
            "read_file each evidence location with at least 10 lines of context on both sides before judging it",
            uncovered=uncovered,
        )
    suggested = str(args.get("suggested_severity") or "").strip()
    if suggested and suggested not in SEVERITIES:
        return _err(f"suggested_severity must be one of {SEVERITIES}")
    finding.critic_weakest_point = weakest
    if verdict == "dispute":
        finding.status = "disputed"
        finding.dispute_reason = reason + (f"（建议严重性：{suggested}）" if suggested else "")
        finding.critic_verdict = "dispute"
    else:
        finding.critic_verdict = "agree"
        finding.history.append(f"复核员同意：{reason}（最弱一环：{weakest}）")
    return _ok(id=finding.id, status=finding.status, verdict=verdict)


def note_gap(args: dict, ctx: ToolContext) -> ToolResult:
    if not ctx.allow_gaps:
        return _err("note_gap is not available in this critic round")
    _require(args, "description")
    description = str(args["description"]).strip()
    if len(description) < 15:
        return _err("description is too short")
    if sum(1 for gap in ctx.state.gaps if not gap.resolved) >= 3:
        return _err("at most 3 open gaps")
    gap = Gap(
        id=f"G{len(ctx.state.gaps) + 1}",
        description=description,
        files_read_at_open=len(ctx.state.files_read),
        searches_at_open=ctx.state.searches,
    )
    ctx.state.gaps.append(gap)
    return _ok(id=gap.id)


def accept_report(args: dict, ctx: ToolContext) -> ToolResult:
    notes = str(args.get("notes") or "").strip()
    if len(notes) < 15:
        return _err("notes must summarize what you checked")
    problems = []
    unreviewed = [
        finding.id
        for finding in ctx.state.findings.values()
        if finding.status in {"confirmed", "needs_review"} and not finding.critic_verdict
    ]
    if unreviewed:
        problems.append("review_finding every confirmed and needs_review finding. Unreviewed: " + ", ".join(unreviewed))
    if problems:
        return _err("critic cannot accept yet", problems=problems)
    ctx.state.critic_accepted = True
    ctx.state.critic_notes = notes
    return _stop(message="critic accepted the current findings")


_EVIDENCE_SCHEMA = {
    "type": "array",
    "description": "Verbatim source quotes. quote must appear inside start_line..end_line and must not include the '12| ' prefix.",
    "items": {
        "type": "object",
        "properties": {
            "path": _str("Repository-relative path"),
            "start_line": _int("First line, inclusive"),
            "end_line": _int("Last line, inclusive"),
            "quote": _str("Exact source text from that range"),
        },
        "required": ["path", "start_line", "end_line", "quote"],
    },
}

SCHEMAS = {
    "list_files": _schema(
        "list_files",
        "List text files under a repository path. Skips static/media/vendor directories unless include_vendor is true "
        "(the result says which ones).",
        {
            "path": _str("Relative directory or file. Default '.'"),
            "glob": _str("Filename glob such as *.py or *.html. Default *"),
            "max_depth": _int("Directory depth relative to path. Default 3"),
            "max_entries": _int("Cap on returned paths. Default 200"),
            "include_vendor": _bool("Include static/media/vendor directories. Default false"),
        },
        [],
    ),
    "read_file": _schema(
        "read_file",
        "Read a window of a text file with line numbers. This is the only way to cite code.",
        {
            "path": _str("Repository-relative file path"),
            "start_line": _int("First line, default 1"),
            "end_line": _int("Last line, inclusive. Window is capped at 180 lines"),
        },
        ["path"],
    ),
    "search_code": _schema(
        "search_code",
        "Regex search across text files. You choose the pattern and where to look.",
        {
            "pattern": _str("Python regular expression"),
            "path": _str("Directory to search. Default '.'"),
            "glob": _str("Filename glob. Default *.py"),
            "include_vendor": _bool("Search vendor trees. Default false"),
            "max_matches": _int("Maximum matches. Default 40"),
        },
        ["pattern"],
    ),
    "pattern_scan": _schema(
        "pattern_scan",
        "Run built-in candidate rules for injection, XSS, CSRF, crypto, deserialization, files, config, redirects, and XML. "
        "Returns leads grouped per rule and file. Every lead must later be closed with triage_leads.",
        {
            "categories": {
                "type": "array",
                "items": {"type": "string", "enum": CATEGORIES},
                "description": "Optional subset. Omit to run every category.",
            },
            "path": _str("Directory to scan. Default '.'"),
            "include_vendor": _bool("Scan vendor trees. Default false"),
        },
        [],
    ),
    "list_endpoints": _schema(
        "list_endpoints",
        "Map Django URLconfs to views: route, view file:line, decorators, auth checks seen, request inputs, write lines, "
        "and heuristic flags. Follows include() from ROOT_URLCONF. Use it to plan which views to read; it does not read them for you.",
        {"root_urlconf": _str("Optional dotted module or path. Default: ROOT_URLCONF from settings.py")},
        [],
    ),
    "find_references": _schema(
        "find_references",
        "Find where a name is defined, imported, and used (word-boundary match on the last dotted segment) across "
        "Python, templates, and config. Use it to check whether a setting is overridden, who calls a helper, or where a field is rendered.",
        {
            "symbol": _str("Identifier or dotted name, e.g. SESSION_ENGINE, make_password, Post.content_html"),
            "path": _str("Directory to search. Default '.'"),
            "include_vendor": _bool("Search static/media/vendor directories too. Default false"),
        },
        ["symbol"],
    ),
    "set_stage": _schema(
        "set_stage",
        "Record that a phase of your own plan has real work behind it. Order is up to you; preconditions stop empty claims.",
        {"stage": _enum("Phase name", STAGES), "note": _str("What you learned in this phase")},
        ["stage", "note"],
    ),
    "upsert_finding": _schema(
        "upsert_finding",
        "Create or replace a finding. confirmed and needs_review quotes are checked against the file before they are stored.",
        {
            "id": _str("Stable id such as SQLI-001"),
            "title": _str("Short Chinese title"),
            "category": _enum("Issue class", CATEGORIES_ENUM),
            "status": _enum("Judgement", STATUSES),
            "severity": _enum("Impact", SEVERITIES),
            "confidence": _enum("How sure you are", CONFIDENCE),
            "cwe": _str("CWE-89 style id. Required for confirmed and needs_review"),
            "summary": _str("What is wrong"),
            "impact": _str("What an attacker gains. No exploit steps"),
            "remediation": _str("How to fix it"),
            "trigger": _str("Where untrusted data or the insecure configuration comes from"),
            "entry_role": _enum(
                "Required for confirmed/needs_review. Who can reach it: anonymous; registered_open (anyone can sign up); "
                "registered_restricted; privileged (staff/admin/permission); not_applicable (no request entry)",
                ENTRY_ROLES,
            ),
            "data_flow": _str(
                "Required for confirmed injection/xss/file_access/redirect/deserialization/access_control: "
                "source -> hops -> sink with file:line, plus what authentication the entry point requires"
            ),
            "evidence": _EVIDENCE_SCHEMA,
        },
        ["id", "title", "category", "status", "summary"],
    ),
    "mark_reviewed": _schema(
        "mark_reviewed",
        "Optional coverage note for a file or directory you finished or deliberately skipped.",
        {"path": _str("Repository-relative path"), "note": _str("Why it is reviewed or skipped")},
        ["path", "note"],
    ),
    "get_audit_state": _schema(
        "get_audit_state",
        "Return findings, stages, files already read, and open gaps. Use this after context was trimmed.",
        {},
        [],
    ),
    "resolve_gap": _schema(
        "resolve_gap",
        "Answer a gap filed by the critic.",
        {"id": _str("Gap id such as G1"), "resolution": _str("What you changed or why it is not an issue")},
        ["id", "resolution"],
    ),
    "finalize_report": _schema(
        "finalize_report",
        "Close the auditor loop. Fails with a problem list if evidence, stages, or coverage gates are unmet.",
        {
            "executive_summary": _str("Chinese summary of the security posture"),
            "risk_overview": _str("Chinese overview of the highest risks"),
            "scope": _str("What you covered and what you left out"),
            "limitations": _str("What this static review cannot prove"),
        },
        ["executive_summary", "risk_overview", "scope", "limitations"],
    ),
    "review_finding": _schema(
        "review_finding",
        "Give a verdict on one finding after re-reading every evidence location with context. "
        "dispute sends it back to the auditor; agree keeps it.",
        {
            "id": _str("Finding id"),
            "weakest_point": _str(
                "Write this first: the single least supported claim in the finding (source, reachability, entry_role, "
                "sanitizer, whether the config is in effect, or severity) and what you found when you checked it"
            ),
            "verdict": _enum("agree or dispute", CRITIC_VERDICTS),
            "reason": _str("What you checked: source, sink, reachability, severity"),
            "suggested_severity": _enum("Optional: the severity you think fits", SEVERITIES),
        },
        ["id", "weakest_point", "verdict", "reason"],
    ),
    "triage_leads": _schema(
        "triage_leads",
        "Close pattern_scan leads. Link them to a finding you wrote, or dismiss them as benign/duplicate after reading the code.",
        {
            "ids": {"type": "array", "items": {"type": "string"}, "description": "Lead ids such as L3"},
            "disposition": _enum("finding: covered by finding_id; benign: read and not a vulnerability; duplicate: same root cause as another lead", LEAD_DISPOSITIONS),
            "finding_id": _str("Required when disposition=finding"),
            "note": _str("Why, in one or two sentences"),
        },
        ["ids", "disposition", "note"],
    ),
    "note_gap": _schema(
        "note_gap",
        "Point at a likely missed high-risk issue without writing an exploit.",
        {"description": _str("What was missed and where to look")},
        ["description"],
    ),
    "accept_report": _schema(
        "accept_report",
        "Accept the current finding set after review_finding has been called for every confirmed and needs_review finding.",
        {"notes": _str("What you re-read and what you still doubt")},
        ["notes"],
    ),
}

HANDLERS = {
    "list_files": list_files,
    "read_file": read_file,
    "search_code": search_code,
    "find_references": find_references,
    "list_endpoints": list_endpoints,
    "pattern_scan": pattern_scan,
    "triage_leads": triage_leads,
    "set_stage": set_stage,
    "upsert_finding": upsert_finding,
    "mark_reviewed": mark_reviewed,
    "get_audit_state": get_audit_state,
    "resolve_gap": resolve_gap,
    "finalize_report": finalize_report,
    "review_finding": review_finding,
    "note_gap": note_gap,
    "accept_report": accept_report,
}

AUDITOR_TOOLS = [
    "list_files",
    "list_endpoints",
    "read_file",
    "search_code",
    "find_references",
    "pattern_scan",
    "triage_leads",
    "set_stage",
    "upsert_finding",
    "mark_reviewed",
    "get_audit_state",
    "resolve_gap",
    "finalize_report",
]

CRITIC_TOOLS = [
    "list_files",
    "list_endpoints",
    "read_file",
    "search_code",
    "find_references",
    "get_audit_state",
    "review_finding",
    "note_gap",
    "accept_report",
]
