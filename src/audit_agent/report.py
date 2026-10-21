"""Human-readable report rendered from structured findings, not from free text alone."""

from __future__ import annotations

from audit_agent.state import AuditState, Finding

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
STATUS_SECTIONS = (
    ("confirmed", "已确认的问题"),
    ("needs_review", "需要再确认的问题"),
    ("disputed", "复核员否决、尚未改判的问题"),
    ("rejected", "已排除的可疑点"),
    ("candidate", "未完成判断的候选"),
)


ROLE_LABELS = {
    "anonymous": "匿名",
    "registered_open": "可自助注册的用户",
    "registered_restricted": "已有账号的用户",
    "privileged": "管理员或特权用户",
    "not_applicable": "无请求入口",
}
CRITIC_LABELS = {"agree": "同意", "dispute": "否决"}


def _target_name(meta: dict) -> str:
    url = (meta.get("target_url") or "").rstrip("/")
    if url:
        return url.rsplit("/", 1)[-1]
    return (meta.get("target_dir") or "目标仓库").rstrip("/").rsplit("/", 1)[-1]


def _cell(text: str) -> str:
    return (text or "").replace("|", "\\|").replace("\n", " ")


def render_report(state: AuditState, meta: dict, verification: list[dict], events: list[dict]) -> str:
    confirmed = [item for item in state.findings.values() if item.status == "confirmed"]
    counts = _count(state)
    failed = [row for row in verification if not row.get("ok")]
    critic_model = meta.get("critic_model") or meta.get("model", "")
    lines = [
        f"# {_target_name(meta)} 应用安全审计报告",
        "",
        f"- 目标：`{meta.get('target_url') or meta.get('target_dir', '')}`，commit `{meta.get('commit', '')}`",
        f"- 模型：审计员 `{meta.get('model', '')}`，复核员 `{critic_model}`",
        f"- 时间：{meta.get('started_at', '')} → {meta.get('finished_at', '')}",
        f"- 结论：{_verdict(confirmed)}",
        f"- 统计：已确认 {counts.get('confirmed', 0)}，待再确认 {counts.get('needs_review', 0)}，已排除 {counts.get('rejected', 0)}；"
        f"引用核对 {len(verification)} 条，未通过 {len(failed)} 条",
        "",
        "## 发现总表",
        "",
    ]
    reported = sorted(
        (item for item in state.findings.values() if item.status in {"confirmed", "needs_review", "disputed"}),
        key=lambda item: (SEVERITY_ORDER.get(item.severity, 9), item.status != "confirmed", item.id),
    )
    if reported:
        lines.append("| 严重性 | 编号 | 问题 | 入口身份 | 状态 | 复核员 | 位置 |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for item in reported:
            where = f"`{item.evidence[0].path}:{item.evidence[0].start_line}`" if item.evidence else "—"
            lines.append(
                f"| {item.severity} | [`{item.id}`](#{_anchor(item)}) | {_cell(item.title)} | {ROLE_LABELS.get(item.entry_role, item.entry_role or '未填')} | "
                f"{item.status} | {CRITIC_LABELS.get(item.critic_verdict, '未复核')} | {where} |"
            )
    else:
        lines.append("没有上报的问题。")
    lines.extend(
        [
            "",
            "下面的发现由 Agent 写入，每条引用都回到源码核对过。审计员综述写在复核之前，单条发现的状态以复核后为准。"
            "线索处置、读过的文件、阶段记录、工具序列和引用核对见 `appendix.md`，关键决策见 `decisions.md`。",
            "",
            "## 审计员综述",
            "",
            state.executive_summary or "（审计员没有提交综述。）",
            "",
            "## 风险概览",
            "",
            state.risk_overview or "（无）",
            "",
        ]
    )
    for status, title in STATUS_SECTIONS:
        items = sorted(
            (item for item in state.findings.values() if item.status == status),
            key=lambda item: (SEVERITY_ORDER.get(item.severity, 9), item.id),
        )
        lines.extend([f"## {title}", ""])
        if not items:
            lines.extend(["无。", ""])
            continue
        for finding in items:
            lines.extend(_finding_block(finding))
    lines.extend(["## 范围", "", state.scope or "（无）", "", "## 局限", "", state.limitations or "（无）", ""])
    lines.extend(["## 复核意见", "", state.critic_notes or "（复核员没有留下说明。）", "", "## 复核缺口", ""])
    if not state.gaps:
        lines.extend(["无。", ""])
    else:
        for gap in state.gaps:
            flag = "已回应" if gap.resolved else "未回应"
            lines.append(f"- `{gap.id}`（{flag}）{gap.description}")
            if gap.resolution:
                lines.append(f"  - 审计员回应：{gap.resolution}")
        lines.append("")
    if state.warnings:
        lines.extend(["## 运行警告", ""])
        lines.extend(f"- {warning}" for warning in state.warnings)
        lines.append("")
    return "\n".join(lines)


def _anchor(finding: Finding) -> str:
    return "finding-" + finding.id.lower()

def render_appendix(state: AuditState, meta: dict, verification: list[dict], events: list[dict]) -> str:
    leads = state.leads.values()
    lines = [
        f"# {_target_name(meta)} 审计附录",
        "",
        "## A. 运行统计",
        "",
        f"- 阅读过的文件：{len(state.files_read)}",
        f"- pattern_scan 线索：{len(state.leads)}（关联发现 {sum(1 for lead in leads if lead.disposition.startswith('finding'))}，"
        f"判为无害 {sum(1 for lead in leads if lead.disposition == 'benign')}，"
        f"重复 {sum(1 for lead in leads if lead.disposition == 'duplicate')}，"
        f"未处理 {sum(1 for lead in leads if not lead.disposition)}）",
        f"- pattern_scan 次数：{state.scans}；search_code / find_references 次数：{state.searches}；list_endpoints：{'用过' if state.endpoints_listed else '没用'}",
        f"- prompt tokens：{meta.get('prompt_tokens', 0)}（缓存命中 {meta.get('cached_tokens', 0)}）",
        f"- completion tokens：{meta.get('completion_tokens', 0)}（其中推理 {meta.get('reasoning_tokens', 0)}）",
        f"- 复核：{meta.get('critic_reviews', 0)} 次 review_finding，其中否决 {meta.get('critic_disputes', 0)} 次",
        "",
        "## B. 扫描线索处置",
        "",
    ]
    if not state.leads:
        lines.extend(["无。", ""])
    else:
        lines.append("| 线索 | 规则 | 文件:行 | 处置 | 说明 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for lead in state.leads.values():
            where = f"{lead.path}:{','.join(str(n) for n in lead.lines[:6])}{'…' if len(lead.lines) > 6 else ''}"
            lines.append(f"| {lead.id} | `{lead.rule_id}` | `{where}` | {lead.disposition or '未处理'} | {_cell(lead.note)} |")
        lines.append("")
    lines.extend(["## C. 阶段记录", ""])
    lines.extend([f"- `{stage['stage']}`：{stage['note']}" for stage in state.stages] or ["无。"])
    lines.extend(["", "## D. 读过的文件", ""])
    lines.extend(f"- `{path}`" for path in state.files_read)
    lines.extend(["", "## E. 工具调用序列", "", "完整参数和返回见 `trajectory.md` 和 `trace.jsonl`。顺序就是模型每次返回的 tool call，代码里没有预设。a = 审计员，c = 复核员。", ""])
    sequence = [f"{(event.get('role') or '')[:1]}:{event['name']}" for event in events if event.get("kind") == "tool"]
    lines.append(" → ".join(f"`{name}`" for name in sequence) if sequence else "（没有工具调用。）")
    lines.extend(["", "## F. 引用核对", ""])
    if not verification:
        lines.append("没有可核对的引用。")
    else:
        failed = [row for row in verification if not row.get("ok")]
        lines.extend([f"共核对 {len(verification)} 条引用，未通过 {len(failed)} 条。", ""])
        for row in verification:
            mark = "通过" if row.get("ok") else "未通过"
            lines.append(f"- {mark} `{row['id']}` `{row['path']}:{row['start_line']}-{row['end_line']}`")
    lines.append("")
    return "\n".join(lines)


def _parse_preview(event: dict) -> dict:
    import json

    try:
        return json.loads(event.get("preview") or "")
    except (json.JSONDecodeError, TypeError):
        return {}


def render_decisions(events: list[dict]) -> str:
    """Digest of the moments that changed the outcome, so a reviewer does not have to read the full trajectory."""
    gates, rewrites, reviews, gaps, triage = [], [], [], [], []
    seen_status: dict[str, str] = {}
    for event in events:
        if event.get("kind") != "tool":
            continue
        name, args = event.get("name"), event.get("arguments") or {}
        if not isinstance(args, dict):
            continue
        out = _parse_preview(event)
        ok = out.get("ok")
        where = f"{event.get('role')} step {event.get('step')}"
        if name in {"finalize_report", "accept_report"}:
            problems = out.get("problems") or [out.get("error", "")]
            gates.append(f"- {where} `{name}` " + ("通过" if ok else "被拒：" + "；".join(str(item) for item in problems)[:600]))
        elif name == "upsert_finding" and args.get("id"):
            fid, status = str(args["id"]), str(args.get("status", ""))
            if not ok:
                rewrites.append(f"- {where} `{fid}` 写入被拒：{str(out.get('error', ''))[:300]}")
                continue
            if fid in seen_status and seen_status[fid] != status:
                rewrites.append(f"- {where} `{fid}` 改判 {seen_status[fid]} → {status}（{args.get('severity', '')}）")
            seen_status[fid] = status
        elif name == "review_finding":
            if ok:
                verdict = CRITIC_LABELS.get(str(args.get("verdict")), str(args.get("verdict")))
                weakest = str(args.get("weakest_point") or "（未填）")[:300]
                suggested = f"，建议 {args['suggested_severity']}" if args.get("suggested_severity") else ""
                reviews.append(f"- {where} `{args.get('id')}` {verdict}{suggested}。最弱一环：{weakest}")
            else:
                reviews.append(f"- {where} `{args.get('id')}` 复核被拒：{str(out.get('error', ''))[:200]}")
        elif name in {"note_gap", "resolve_gap"}:
            text = args.get("description") or args.get("resolution") or ""
            flag = "" if ok else f"（被拒：{str(out.get('error', ''))[:160]}）"
            gaps.append(f"- {where} `{name}` {args.get('id') or out.get('id', '')}：{str(text)[:400]}{flag}")
        elif name == "triage_leads" and args.get("disposition") == "benign" and ok:
            triage.append(f"- {where} {', '.join(map(str, args.get('ids') or []))} 判为无害：{str(args.get('note', ''))[:240]}")
    lines = ["# 关键决策", "", "从 `trace.jsonl` 里抽出来的关键节点，完整过程见 `trajectory.md`。", ""]
    for title, rows in (
        ("门禁", gates),
        ("发现的写入被拒与改判", rewrites),
        ("复核", reviews),
        ("缺口", gaps),
        ("判为无害的扫描线索", triage),
    ):
        lines.extend([f"## {title}", ""])
        lines.extend(rows or ["无。"])
        lines.append("")
    return "\n".join(lines)


def render_trajectory(events: list[dict]) -> str:
    lines = ["# Agent 工具调用轨迹", "", "每一节是模型的一次调用。工具返回只保留前 2500 个字符。", ""]
    for event in events:
        if event.get("kind") == "assistant":
            tools = ", ".join(event.get("tools") or []) or "（无）"
            lines.append(f"## {event.get('role')} step {event.get('step')}")
            lines.append("")
            lines.append(f"调用：{tools}")
            reasoning = (event.get("reasoning") or "").strip()
            if reasoning:
                lines.extend(["", "<details><summary>模型推理（节选）</summary>", "", reasoning, "", "</details>"])
            text = (event.get("text") or "").strip()
            if text:
                lines.extend(["", "模型说明：", "", text])
            lines.append("")
        elif event.get("kind") == "compact":
            lines.extend([f"> 上下文压缩：{event.get('role')} step {event.get('step')}，压缩后约 {event.get('chars')} 字符", ""])
        elif event.get("kind") == "tool":
            lines.append(f"### {event.get('name')}")
            lines.append("")
            lines.append("参数：")
            lines.append("")
            lines.append("```json")
            lines.append(_pretty(event.get("arguments")))
            lines.append("```")
            lines.append("")
            lines.append("返回：")
            lines.append("")
            lines.append("```")
            lines.append(event.get("preview") or "")
            lines.append("```")
            lines.append("")
    return "\n".join(lines)


def _finding_block(finding: Finding) -> list[str]:
    lines = [
        f'<a id="{_anchor(finding)}"></a>',
        "",
        f"### [{finding.severity.upper()}] {finding.title}",
        "",
        f"- 编号：`{finding.id}`",
        f"- 类别：`{finding.category}`",
        f"- CWE：`{finding.cwe or '未标注'}`",
        f"- 入口身份：{ROLE_LABELS.get(finding.entry_role, finding.entry_role or '未填')}",
        f"- 置信度：`{finding.confidence}`",
        f"- 状态：`{finding.status}`",
        f"- 复核员：{CRITIC_LABELS.get(finding.critic_verdict, '未复核')}",
        "",
        finding.summary,
        "",
        f"**触发条件。** {finding.trigger or '（无）'}",
        "",
    ]
    if finding.data_flow:
        lines.extend([f"**数据流。** {finding.data_flow}", ""])
    lines.extend(
        [
            f"**影响。** {finding.impact or '（无）'}",
            "",
            f"**修复。** {finding.remediation or '（无）'}",
            "",
        ]
    )
    if finding.critic_weakest_point:
        lines.extend([f"**复核员指出的最弱一环。** {finding.critic_weakest_point}", ""])
    if finding.dispute_reason:
        lines.extend([f"**异议或降级说明。** {finding.dispute_reason}", ""])
    if finding.history:
        lines.append("**判定历史。**")
        lines.append("")
        lines.extend(f"- {entry}" for entry in finding.history)
        lines.append("")
    if not finding.evidence:
        lines.extend(["没有代码引用。", ""])
        return lines
    lines.append("**证据。**")
    lines.append("")
    for evidence in finding.evidence:
        lines.append(f"`{evidence.path}:{evidence.start_line}-{evidence.end_line}`")
        lines.append("")
        lines.append("```")
        lines.append(evidence.quote.rstrip())
        lines.append("```")
        lines.append("")
    return lines


def _count(state: AuditState) -> dict[str, int]:
    counts: dict[str, int] = {}
    for finding in state.findings.values():
        counts[finding.status] = counts.get(finding.status, 0) + 1
    return counts


def _verdict(confirmed: list[Finding]) -> str:
    if not confirmed:
        return "没有留下通过引用核对的已确认问题。"
    worst = min(confirmed, key=lambda item: SEVERITY_ORDER.get(item.severity, 9))
    return f"确认 {len(confirmed)} 个问题，最高严重性为 {worst.severity}。"


def _pretty(value) -> str:
    import json

    if value is None:
        return "null"
    return json.dumps(value, ensure_ascii=False, indent=2)
