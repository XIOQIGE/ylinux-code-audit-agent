"""Mutable audit memory shared by the auditor, the critic, and the report."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Evidence:
    path: str
    start_line: int
    end_line: int
    quote: str

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "quote": self.quote,
        }


@dataclass
class Finding:
    id: str
    title: str
    category: str
    status: str
    severity: str
    confidence: str
    cwe: str
    summary: str
    impact: str
    remediation: str
    trigger: str
    evidence: list[Evidence] = field(default_factory=list)
    dispute_reason: str = ""
    data_flow: str = ""
    history: list[str] = field(default_factory=list)
    critic_verdict: str = ""
    entry_role: str = ""
    critic_weakest_point: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "status": self.status,
            "severity": self.severity,
            "confidence": self.confidence,
            "cwe": self.cwe,
            "summary": self.summary,
            "impact": self.impact,
            "remediation": self.remediation,
            "trigger": self.trigger,
            "entry_role": self.entry_role,
            "data_flow": self.data_flow,
            "evidence": [item.to_dict() for item in self.evidence],
            "dispute_reason": self.dispute_reason,
            "critic_verdict": self.critic_verdict,
            "critic_weakest_point": self.critic_weakest_point,
            "history": self.history,
        }


@dataclass
class Lead:
    """A scanner hit cluster (one rule in one file) that must be triaged before finalize."""

    id: str
    rule_id: str
    category: str
    path: str
    lines: list[int]
    snippet: str
    disposition: str = ""
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "category": self.category,
            "path": self.path,
            "lines": self.lines,
            "snippet": self.snippet,
            "disposition": self.disposition,
            "note": self.note,
        }


@dataclass
class Gap:
    id: str
    description: str
    resolved: bool = False
    resolution: str = ""
    files_read_at_open: int = 0
    searches_at_open: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "resolved": self.resolved,
            "resolution": self.resolution,
            "files_read_at_open": self.files_read_at_open,
            "searches_at_open": self.searches_at_open,
        }


@dataclass
class AuditState:
    findings: dict[str, Finding] = field(default_factory=dict)
    stages: list[dict] = field(default_factory=list)
    reviewed: list[dict] = field(default_factory=list)
    files_read: list[str] = field(default_factory=list)
    searches: int = 0
    scans: int = 0
    listed: bool = False
    endpoints_listed: bool = False
    gaps: list[Gap] = field(default_factory=list)
    leads: dict[str, Lead] = field(default_factory=dict)
    executive_summary: str = ""
    risk_overview: str = ""
    scope: str = ""
    limitations: str = ""
    finalized: bool = False
    critic_accepted: bool = False
    critic_notes: str = ""
    warnings: list[str] = field(default_factory=list)

    def stage_names(self) -> set[str]:
        return {item["stage"] for item in self.stages}

    def remember_read(self, path: str) -> None:
        if path not in self.files_read:
            self.files_read.append(path)

    def snapshot(self) -> dict:
        return {
            "findings": [item.to_dict() for item in self.findings.values()],
            "stages": self.stages,
            "reviewed": self.reviewed,
            "files_read": self.files_read,
            "searches": self.searches,
            "scans": self.scans,
            "listed": self.listed,
            "endpoints_listed": self.endpoints_listed,
            "gaps": [gap.to_dict() for gap in self.gaps],
            "leads": [lead.to_dict() for lead in self.leads.values()],
            "executive_summary": self.executive_summary,
            "risk_overview": self.risk_overview,
            "scope": self.scope,
            "limitations": self.limitations,
            "finalized": self.finalized,
            "critic_accepted": self.critic_accepted,
            "critic_notes": self.critic_notes,
            "warnings": self.warnings,
        }

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")


def load_state(path: Path) -> AuditState:
    raw = json.loads(path.read_text(encoding="utf-8"))
    state = AuditState(
        stages=list(raw.get("stages") or []),
        reviewed=list(raw.get("reviewed") or []),
        files_read=list(raw.get("files_read") or []),
        searches=int(raw.get("searches") or 0),
        scans=int(raw.get("scans") or 0),
        listed=bool(raw.get("listed")),
        endpoints_listed=bool(raw.get("endpoints_listed")),
        executive_summary=raw.get("executive_summary") or "",
        risk_overview=raw.get("risk_overview") or "",
        scope=raw.get("scope") or "",
        limitations=raw.get("limitations") or "",
        finalized=bool(raw.get("finalized")),
        critic_accepted=bool(raw.get("critic_accepted")),
        critic_notes=raw.get("critic_notes") or "",
        warnings=list(raw.get("warnings") or []),
    )
    for item in raw.get("findings") or []:
        evidence = [
            Evidence(path=ev["path"], start_line=int(ev["start_line"]), end_line=int(ev["end_line"]), quote=ev["quote"])
            for ev in item.get("evidence") or []
        ]
        state.findings[item["id"]] = Finding(
            id=item["id"],
            title=item.get("title") or "",
            category=item.get("category") or "other",
            status=item.get("status") or "candidate",
            severity=item.get("severity") or "info",
            confidence=item.get("confidence") or "medium",
            cwe=item.get("cwe") or "",
            summary=item.get("summary") or "",
            impact=item.get("impact") or "",
            remediation=item.get("remediation") or "",
            trigger=item.get("trigger") or "",
            evidence=evidence,
            dispute_reason=item.get("dispute_reason") or "",
            data_flow=item.get("data_flow") or "",
            history=list(item.get("history") or []),
            critic_verdict=item.get("critic_verdict") or "",
            entry_role=item.get("entry_role") or "",
            critic_weakest_point=item.get("critic_weakest_point") or "",
        )
    for gap in raw.get("gaps") or []:
        state.gaps.append(
            Gap(
                id=gap["id"],
                description=gap.get("description") or "",
                resolved=bool(gap.get("resolved")),
                resolution=gap.get("resolution") or "",
                files_read_at_open=int(gap.get("files_read_at_open") or 0),
                searches_at_open=int(gap.get("searches_at_open") or 0),
            )
        )
    for lead in raw.get("leads") or []:
        state.leads[lead["id"]] = Lead(
            id=lead["id"],
            rule_id=lead.get("rule_id") or "",
            category=lead.get("category") or "",
            path=lead.get("path") or "",
            lines=list(lead.get("lines") or []),
            snippet=lead.get("snippet") or "",
            disposition=lead.get("disposition") or "",
            note=lead.get("note") or "",
        )
    return state
