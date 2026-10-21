"""Check that a quoted excerpt really occurs in the cited line range."""

from __future__ import annotations

import re

from audit_agent.sandbox import Sandbox, SandboxError, strip_line_prefix
from audit_agent.state import AuditState

MAX_SPAN = 30
MIN_QUOTE = 8


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\r\n", "\n").replace("\r", "\n")).strip()


def quote_in_excerpt(excerpt: str, quote: str) -> bool:
    candidates = [quote, strip_line_prefix(quote)]
    folded = "\n".join(line.strip() for line in excerpt.splitlines()).strip()
    for candidate in candidates:
        stripped = candidate.strip()
        if len(stripped) < MIN_QUOTE:
            continue
        if stripped in excerpt:
            return True
        folded_quote = "\n".join(line.strip() for line in stripped.splitlines()).strip()
        if folded_quote and folded_quote in folded:
            return True
        if normalize_ws(stripped) and normalize_ws(stripped) in normalize_ws(excerpt):
            return True
    return False


def check_quote(sandbox: Sandbox, path: str, start_line: int, end_line: int, quote: str) -> tuple[bool, str]:
    """Return (ok, actual_excerpt_or_error)."""
    if isinstance(start_line, str) and start_line.strip().isdigit():
        start_line = int(start_line.strip())
    if isinstance(end_line, str) and end_line.strip().isdigit():
        end_line = int(end_line.strip())
    if not isinstance(start_line, int) or not isinstance(end_line, int):
        return False, "start_line and end_line must be integers"
    if end_line < start_line:
        return False, "end_line is before start_line"
    if end_line - start_line + 1 > MAX_SPAN:
        return False, f"line range exceeds {MAX_SPAN} lines; split the evidence"
    if len((quote or "").strip()) < MIN_QUOTE:
        return False, f"quote must be at least {MIN_QUOTE} characters of source text"
    try:
        _rel, _encoding, text = sandbox.read_text(path)
    except SandboxError as exc:
        return False, str(exc)
    lines = text.splitlines()
    if start_line < 1 or end_line > len(lines):
        return False, f"line range {start_line}-{end_line} is outside the file ({len(lines)} lines)"
    excerpt = "\n".join(lines[start_line - 1 : end_line])
    if quote_in_excerpt(excerpt, quote):
        return True, excerpt
    return False, excerpt


def verify_state(sandbox: Sandbox, state: AuditState) -> list[dict]:
    """Re-check every stored quote. Downgrade confirmed findings that no longer match."""
    rows: list[dict] = []
    for finding in state.findings.values():
        finding_ok = True
        for evidence in finding.evidence:
            ok, detail = check_quote(
                sandbox,
                evidence.path,
                evidence.start_line,
                evidence.end_line,
                evidence.quote,
            )
            rows.append(
                {
                    "id": finding.id,
                    "path": evidence.path,
                    "start_line": evidence.start_line,
                    "end_line": evidence.end_line,
                    "ok": ok,
                    "detail": "match" if ok else detail[:500],
                }
            )
            finding_ok = finding_ok and ok
        if finding.status == "confirmed" and finding.evidence and not finding_ok:
            finding.status = "needs_review"
            note = "机械核对未能在引用范围内找到 quote，已从 confirmed 降级为 needs_review。"
            finding.dispute_reason = f"{finding.dispute_reason}\n{note}".strip()
    return rows
