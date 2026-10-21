"""Score a run against a labelled ground-truth file.

Matching is by evidence location, not by title: a finding matches a truth item
if one of its evidence ranges overlaps one of the truth item's locations
(same file, line ranges within a small tolerance) and the finding's category
is the item's category or one of its ``also_categories``. Without the category
check a rate-limit finding that quotes the login view would also be credited
with the open redirect three lines below it.

False-positive traps are matched on exact lines. Evidence that lands in a
fired conditional trap (wrong category, CWE, or minimum severity) earns no
credit: calling the reboot os.system "injection" is wrong even though the same
lines are a real GET/CSRF issue. If the finding's other evidence still hits a
truth item it stays a true positive and the trap is recorded in ``trap_notes``
(right bug, overstated impact).
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

from audit_agent.state import load_state

LINE_TOLERANCE = 3
SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}
REPORTED = {"confirmed", "needs_review"}


def _overlaps(evidence: dict, location: dict, tolerance: int = LINE_TOLERANCE) -> bool:
    if evidence["path"] != location["path"]:
        return False
    low = location["start_line"] - tolerance
    high = location["end_line"] + tolerance
    return evidence["start_line"] <= high and evidence["end_line"] >= low


def _category_ok(finding: dict, item: dict) -> bool:
    if "category" not in item:
        return True
    return finding["category"] in {item["category"], *item.get("also_categories", [])}


def _hits(finding: dict, items: list[dict], tolerance: int = LINE_TOLERANCE, evidence: list[dict] | None = None) -> list[str]:
    evidence = finding["evidence"] if evidence is None else evidence
    return [
        item["id"]
        for item in items
        if _category_ok(finding, item)
        and any(_overlaps(ev, loc, tolerance) for ev in evidence for loc in item["locations"])
    ]


def _trap_conditional(trap: dict) -> bool:
    return any(key in trap for key in ("wrong_categories", "wrong_cwes", "wrong_min_severity"))


def _trap_fires(trap: dict, finding: dict) -> bool:
    if not _trap_conditional(trap):
        return True
    if finding["category"] in trap.get("wrong_categories", []):
        return True
    cwe = (finding.get("cwe") or "").upper()
    if any(cwe.startswith(item) for item in trap.get("wrong_cwes", [])):
        return True
    floor = trap.get("wrong_min_severity")
    return bool(floor) and SEVERITY_RANK.get(finding["severity"], 0) >= SEVERITY_RANK[floor]


def _impact_traps(ids: list[str], traps: dict[str, dict]) -> list[str]:
    # A category trap on co-cited contrast code says nothing; a severity or CWE trap means the impact is overstated.
    return [tid for tid in ids if "wrong_min_severity" in traps[tid] or "wrong_cwes" in traps[tid]]


def score(findings: list[dict], truth: dict) -> dict:
    issues = truth["issues"]
    optional = truth.get("optional", [])
    traps = {trap["id"]: trap for trap in truth.get("false_positive_traps", [])}
    reported = [item for item in findings if item["status"] in REPORTED]
    matched_truth: dict[str, list[str]] = {}
    matched_optional: set[str] = set()
    finding_rows = []
    for finding in reported:
        trap_hits = [tid for tid in _hits(finding, list(traps.values()), 0) if _trap_fires(traps[tid], finding)]
        strong_traps = [tid for tid in trap_hits if _trap_conditional(traps[tid])]
        trapped_locs = [loc for tid in strong_traps for loc in traps[tid]["locations"]]
        # Evidence inside a fired conditional trap cannot earn credit; evidence elsewhere still can.
        clean = [ev for ev in finding["evidence"] if not any(_overlaps(ev, loc, 0) for loc in trapped_locs)]
        hits = _hits(finding, issues, evidence=clean)
        optional_hits = _hits(finding, optional, evidence=clean)
        if strong_traps and not hits and not optional_hits:
            verdict, trap_hits, trap_notes = "false_positive_trap", strong_traps, []
        elif hits:
            verdict, trap_hits, trap_notes = "true_positive", [], _impact_traps(strong_traps, traps)
        elif trap_hits and not optional_hits:
            verdict, trap_notes = "false_positive_trap", []
        elif optional_hits:
            verdict, trap_hits, trap_notes = "true_positive_optional", [], _impact_traps(strong_traps, traps)
        else:
            verdict, trap_notes = "unmatched", []
        for issue_id in hits:
            matched_truth.setdefault(issue_id, []).append(finding["id"])
        matched_optional.update(optional_hits)
        severity_note = ""
        expected = ""
        target = hits or optional_hits
        if target:
            # A finding can overlap several truth items; judge severity against the one it fits best.
            levels = [next(item for item in issues + optional if item["id"] == tid)["severity"] for tid in target]
            own = SEVERITY_RANK.get(finding["severity"], 0)
            expected = min(levels, key=lambda level: abs(own - SEVERITY_RANK.get(level, 0)))
            delta = own - SEVERITY_RANK.get(expected, 0)
            severity_note = "ok" if abs(delta) <= 1 else ("over" if delta > 0 else "under")
        finding_rows.append(
            {
                "id": finding["id"],
                "title": finding["title"],
                "status": finding["status"],
                "severity": finding["severity"],
                "category": finding["category"],
                "verdict": verdict,
                "truth": hits or optional_hits,
                "traps": trap_hits,
                "trap_notes": trap_notes,
                "severity_fit": severity_note,
                "expected_severity": expected,
            }
        )
    weighted_total = sum(SEVERITY_RANK[issue["severity"]] + 1 for issue in issues)
    weighted_found = sum(SEVERITY_RANK[issue["severity"]] + 1 for issue in issues if issue["id"] in matched_truth)
    tp = sum(1 for row in finding_rows if row["verdict"].startswith("true_positive"))
    fp_trap = sum(1 for row in finding_rows if row["verdict"] == "false_positive_trap")
    high_issues = [issue for issue in issues if SEVERITY_RANK[issue["severity"]] >= SEVERITY_RANK["high"]]
    return {
        "reported": len(reported),
        "true_positive_findings": tp,
        "false_positive_trap_findings": fp_trap,
        "unmatched_findings": len(reported) - tp - fp_trap,
        "precision_lower_bound": round(tp / len(reported), 3) if reported else 0.0,
        "recall": round(len(matched_truth) / len(issues), 3) if issues else 0.0,
        "high_recall": round(sum(1 for issue in high_issues if issue["id"] in matched_truth) / len(high_issues), 3) if high_issues else 0.0,
        "severity_weighted_recall": round(weighted_found / weighted_total, 3) if weighted_total else 0.0,
        "missed": [issue["id"] for issue in issues if issue["id"] not in matched_truth],
        "found": sorted(matched_truth),
        "optional_found": sorted(matched_optional),
        "traps_hit": sorted({tid for row in finding_rows for tid in row["traps"]}),
        "findings": finding_rows,
    }


def load_findings(run_dir: Path) -> list[dict]:
    state_path = run_dir / "state.json"
    if state_path.exists():
        return [item.to_dict() for item in load_state(state_path).findings.values()]
    return json.loads((run_dir / "findings.json").read_text(encoding="utf-8"))


def render(results: dict[str, dict], truth: dict, truth_path: Path = Path("eval/ground_truth.json")) -> str:
    titles = {issue["id"]: f"{issue['id']} [{issue['severity']}] {issue['title']}" for issue in truth["issues"]}
    trap_titles = {trap["id"]: trap["title"] for trap in truth.get("false_positive_traps", [])}
    lines = ["# 评测结果", "", f"用 `python -m audit_agent evaluate` 生成，真值文件是 `{truth_path.as_posix()}`（{truth.get('target', '')}）。", ""]
    lines.append("| 运行 | 上报 | 命中真值 | 踩中误报陷阱 | 未匹配 | 精确率下限 | 召回率 | 高危及以上召回 | 按严重性加权召回 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for name, result in results.items():
        lines.append(
            f"| `{name}` | {result['reported']} | {result['true_positive_findings']} | {result['false_positive_trap_findings']} | "
            f"{result['unmatched_findings']} | {result['precision_lower_bound']} | {result['recall']} | {result['high_recall']} | {result['severity_weighted_recall']} |"
        )
    lines.append("")
    lines.append("“未匹配”可能是误报，也可能是真值里没收录的真问题，要人工看，所以精确率只给下限。“附带陷阱”指发现本身命中了真值，但有一部分证据或影响描述落在已知的误判上，也就是问题找对了、影响说过头了。")
    for name, result in results.items():
        lines.extend(["", f"## `{name}`", "", "| 发现 | 状态 | 严重性 | 判定 | 对应真值 | 严重性偏差 |", "| --- | --- | --- | --- | --- | --- |"])
        for row in result["findings"]:
            target = ", ".join(row["truth"] or row["traps"]) or "—"
            if row["trap_notes"]:
                target += "（附带陷阱 " + ", ".join(row["trap_notes"]) + "）"
            lines.append(f"| `{row['id']}` {row['title']} | {row['status']} | {row['severity']} | {row['verdict']} | {target} | {row['severity_fit'] or '—'} |")
        if result["traps_hit"]:
            lines.extend(["", "踩中的误报陷阱：", ""])
            lines.extend(f"- {tid} {trap_titles[tid]}" for tid in result["traps_hit"])
        lines.extend(["", "漏报：", ""])
        lines.extend(f"- {titles[item]}" for item in result["missed"]) if result["missed"] else lines.append("- 无")
    lines.append("")
    return "\n".join(lines)


GROUP_METRICS = ("reported", "precision_lower_bound", "recall", "high_recall", "severity_weighted_recall")
VERDICT_LABELS = {
    "true_positive": "命中真值",
    "true_positive_optional": "命中可选项",
    "false_positive_trap": "误报（踩中已知陷阱）",
    "unmatched": "未匹配（需人工判断）",
}
SEVERITY_FIT_LABELS = {"ok": "相符", "over": "偏高两级以上", "under": "偏低两级以上", "": "—"}


def _spread(values: list[float]) -> tuple[float, float, float, float]:
    mean = statistics.fmean(values)
    stdev = statistics.stdev(values) if len(values) > 1 else 0.0
    return round(mean, 3), round(stdev, 3), min(values), max(values)


def summarize_group(results: list[dict], truth: dict) -> dict:
    metrics = {key: _spread([float(result[key]) for result in results]) for key in GROUP_METRICS}
    hit_rate = {issue["id"]: sum(issue["id"] in result["found"] for result in results) for issue in truth["issues"]}
    return {"runs": len(results), "metrics": metrics, "hit_rate": hit_rate}


def render_groups(groups: dict[str, dict], truth: dict) -> str:
    lines = ["## 重复运行的波动", "", "均值 ± 样本标准差（最小 – 最大）。代码、模型、目标都相同，差别只来自模型每次的采样。", ""]
    lines.append("| 组 | 次数 | " + " | ".join(METRIC_LABELS[key] for key in GROUP_METRICS) + " |")
    lines.append("| --- | --- | " + " | ".join("---" for _ in GROUP_METRICS) + " |")
    for name, group in groups.items():
        cells = [f"{m} ± {s} ({lo:g} – {hi:g})" for m, s, lo, hi in (group["metrics"][key] for key in GROUP_METRICS)]
        lines.append(f"| `{name}` | {group['runs']} | " + " | ".join(cells) + " |")
    titles = {issue["id"]: (issue["severity"], issue["title"]) for issue in truth["issues"]}
    for name, group in groups.items():
        runs = group["runs"]
        lines.extend(["", f"### `{name}`：每条真值被找到的次数", "", "| 真值 | 严重性 | 标题 | 命中 |", "| --- | --- | --- | --- |"])
        for issue_id, count in sorted(group["hit_rate"].items(), key=lambda kv: (-SEVERITY_RANK[titles[kv[0]][0]], kv[1], kv[0])):
            severity, title = titles[issue_id]
            lines.append(f"| {issue_id} | {severity} | {title} | {count}/{runs} |")
        stable = sum(1 for count in group["hit_rate"].values() if count == runs)
        never = sum(1 for count in group["hit_rate"].values() if count == 0)
        lines.extend(["", f"每次都找到 {stable} 条，从未找到 {never} 条，其余 {len(group['hit_rate']) - stable - never} 条时有时无。"])
    return "\n".join(lines)


def render_review(name: str, result: dict, truth: dict, truth_path: Path) -> str:
    """Per-run review written from the scorecard. Lives beside report.md and never touches findings.json."""
    issues = {issue["id"]: issue for issue in truth["issues"] + truth.get("optional", [])}
    traps = {trap["id"]: trap for trap in truth.get("false_positive_traps", [])}
    lines = [
        f"# 运行 `{name}` 的评审",
        "",
        f"用 `audit_agent evaluate` 对照 `{truth_path.as_posix()}` 生成，只是给 report.md 打分，不改报告本身。",
        "",
        f"- 上报 {result['reported']} 条：命中真值 {result['true_positive_findings']}，踩中误报陷阱 {result['false_positive_trap_findings']}，未匹配 {result['unmatched_findings']}",
        f"- 精确率下限 {result['precision_lower_bound']}，召回率 {result['recall']}，高危及以上召回 {result['high_recall']}，按严重性加权召回 {result['severity_weighted_recall']}",
        "",
        "## 逐条判定",
        "",
        "| 发现 | 报告严重性 | 判定 | 对应真值 / 陷阱 | 真值严重性 | 严重性对比 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in result["findings"]:
        refs = row["truth"] or row["traps"]
        expected = row.get("expected_severity") or "—"
        target = ", ".join(refs) or "—"
        if row["trap_notes"]:
            target += "（影响说过头：" + ", ".join(row["trap_notes"]) + "）"
        lines.append(
            f"| `{row['id']}` {row['title']} | {row['severity']} | {VERDICT_LABELS[row['verdict']]} | {target} | {expected} | {SEVERITY_FIT_LABELS[row['severity_fit']]} |"
        )
    if result["traps_hit"]:
        lines.extend(["", "## 踩中的误报陷阱", ""])
        for tid in result["traps_hit"]:
            lines.append(f"- {tid} {traps[tid].get('title', '')}：{traps[tid].get('why', traps[tid].get('note', ''))}".rstrip("："))
    lines.extend(["", "## 漏报", ""])
    if result["missed"]:
        for issue_id in result["missed"]:
            issue = issues[issue_id]
            where = ", ".join(f"{loc['path']}:{loc['start_line']}" for loc in issue["locations"][:3])
            lines.append(f"- {issue_id} [{issue['severity']}] {issue['title']}（{where}）")
    else:
        lines.append("- 无")
    unmatched = [row for row in result["findings"] if row["verdict"] == "unmatched"]
    if unmatched:
        lines.extend(["", "## 未匹配的发现", "", "真值里没有对应条目，可能是误报，也可能是真值漏了，需要打开证据看。", ""])
        lines.extend(f"- `{row['id']}` {row['title']}（{row['category']}，{row['severity']}）" for row in unmatched)
    lines.append("")
    return "\n".join(lines)


METRIC_LABELS = {
    "reported": "上报数",
    "precision_lower_bound": "精确率下限",
    "recall": "召回率",
    "high_recall": "高危及以上召回",
    "severity_weighted_recall": "加权召回",
}


def main(run_dirs: list[Path], truth_path: Path, out: Path | None, groups: dict[str, list[Path]] | None = None) -> int:
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    groups = groups or {}
    results = {}
    ordered = list(dict.fromkeys([*run_dirs, *(path for dirs in groups.values() for path in dirs)]))
    for run_dir in ordered:
        result = score(load_findings(run_dir), truth)
        results[run_dir.name] = result
        (run_dir / "evaluation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        (run_dir / "REVIEW.md").write_text(render_review(run_dir.name, result, truth, truth_path), encoding="utf-8")
        print(
            f"{run_dir.name}: reported={result['reported']} tp={result['true_positive_findings']} "
            f"fp_trap={result['false_positive_trap_findings']} recall={result['recall']} "
            f"weighted_recall={result['severity_weighted_recall']} missed={result['missed']}"
        )
    summaries = {name: summarize_group([results[path.name] for path in dirs], truth) for name, dirs in groups.items() if dirs}
    for name, group in summaries.items():
        cells = ", ".join(f"{key}={m}±{s}" for key, (m, s, _lo, _hi) in group["metrics"].items())
        print(f"group {name} (n={group['runs']}): {cells}")
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        text = render(results, truth, truth_path)
        if summaries:
            text = text.rstrip("\n") + "\n\n" + render_groups(summaries, truth) + "\n"
        out.write_text(text, encoding="utf-8")
    return 0
