import json
from pathlib import Path

from audit_agent.agent import Trace, _packet, compact_messages, run_audit, run_loop
from audit_agent.evaluate import score
from audit_agent.llm import LLMResponse, ToolCall
from audit_agent.sandbox import Sandbox
from audit_agent.state import AuditState, load_state
from audit_agent.tools import ToolContext, execute_tool

SQLI = {
    "id": "SQLI-001",
    "title": "拼接 SQL",
    "category": "injection",
    "status": "confirmed",
    "severity": "high",
    "confidence": "high",
    "cwe": "CWE-89",
    "entry_role": "anonymous",
    "summary": "视图把请求参数拼进 SQL 字符串后执行。",
    "impact": "攻击者可以改变查询语义并读取或修改数据库内容。",
    "remediation": "使用参数化查询，不要把请求参数拼进 SQL 文本。",
    "trigger": "search 视图从 request.GET 取 q，再用百分号拼进 SELECT。",
    "data_flow": "app/views.py:2 request.GET['q'] -> :3 拼进 SQL -> :4 cursor.execute，匿名可达",
    "evidence": [{"path": "app/views.py", "start_line": 3, "end_line": 4, "quote": "cursor.execute(sql)"}],
}


def _repo(tmp_path: Path) -> Sandbox:
    (tmp_path / "settings.py").write_text("DEBUG = True\nSECRET_KEY = 'fixture-secret-value'\n", encoding="utf-8")
    (tmp_path / "urls.py").write_text("urlpatterns = []\n", encoding="utf-8")
    app = tmp_path / "app"
    app.mkdir()
    (app / "views.py").write_text(
        "def search(request):\n"
        "    q = request.GET.get('q')\n"
        "    sql = \"SELECT * FROM posts WHERE title = '%s'\" % q\n"
        "    cursor.execute(sql)\n",
        encoding="utf-8",
    )
    other = tmp_path / "blog"
    other.mkdir()
    (other / "views.py").write_text("def index(request):\n    return None\n", encoding="utf-8")
    return Sandbox(tmp_path)


def _ok(result) -> bool:
    return json.loads(result.content)["ok"]


def test_confirmed_injection_requires_data_flow(tmp_path: Path):
    ctx = ToolContext(_repo(tmp_path), AuditState(), "auditor")
    missing = dict(SQLI, data_flow="")
    assert not _ok(execute_tool("upsert_finding", missing, ctx))
    as_review = dict(missing, status="needs_review")
    assert _ok(execute_tool("upsert_finding", as_review, ctx))


def test_scan_leads_block_finalize_until_triaged(tmp_path: Path):
    sandbox = _repo(tmp_path)
    ctx = ToolContext(sandbox, AuditState(), "auditor")
    scan = json.loads(execute_tool("pattern_scan", {}, ctx).content)
    lead_ids = [lead["id"] for lead in scan["leads"]]
    assert lead_ids
    by_rule = {lead["rule_id"]: lead["id"] for lead in scan["leads"]}
    for path in ("settings.py", "urls.py", "app/views.py", "blog/views.py"):
        execute_tool("read_file", {"path": path}, ctx)
    execute_tool("search_code", {"pattern": "execute"}, ctx)
    for stage in ("recon", "hunt", "investigate"):
        assert _ok(execute_tool("set_stage", {"stage": stage, "note": "did the work for " + stage}, ctx))
    assert _ok(execute_tool("upsert_finding", SQLI, ctx))
    assert _ok(execute_tool("set_stage", {"stage": "verify", "note": "re-read the evidence"}, ctx))
    summary = {
        "executive_summary": "仓库存在一处 SQL 注入以及调试配置问题，已给出证据。",
        "risk_overview": "最高风险是匿名用户可控的 SQL 拼接，可以读取数据库。",
        "scope": "覆盖 settings、urls、全部 views 以及扫描线索。",
        "limitations": "静态阅读，没有运行目标应用做动态验证，结论以代码为准。",
    }
    blocked = json.loads(execute_tool("finalize_report", summary, ctx).content)
    assert not blocked["ok"]
    assert any("triage_leads" in problem for problem in blocked["problems"])
    sql_lead = by_rule.get("sql-statement-format") or by_rule.get("sql-execute-format")
    assert _ok(execute_tool("triage_leads", {"ids": [sql_lead], "disposition": "finding", "finding_id": "SQLI-001", "note": "同一处拼接 SQL，已写成发现"}, ctx))
    rest = [lead_id for lead_id in lead_ids if lead_id != sql_lead]
    assert _ok(execute_tool("triage_leads", {"ids": rest, "disposition": "benign", "note": "测试夹具中的配置，仅用于验证流程"}, ctx))
    assert _ok(execute_tool("finalize_report", summary, ctx))


def test_benign_triage_requires_reading_the_file(tmp_path: Path):
    ctx = ToolContext(_repo(tmp_path), AuditState(), "auditor")
    scan = json.loads(execute_tool("pattern_scan", {}, ctx).content)
    lead = next(item for item in scan["leads"] if item["path"] == "settings.py")
    result = json.loads(execute_tool("triage_leads", {"ids": [lead["id"]], "disposition": "benign", "note": "没读文件就想直接排除这条线索"}, ctx).content)
    assert not result["ok"]


def test_finalize_requires_most_views(tmp_path: Path):
    ctx = ToolContext(_repo(tmp_path), AuditState(), "auditor")
    execute_tool("read_file", {"path": "app/views.py"}, ctx)
    result = json.loads(
        execute_tool(
            "finalize_report",
            {"executive_summary": "x" * 30, "risk_overview": "x" * 30, "scope": "x" * 30, "limitations": "x" * 30},
            ctx,
        ).content
    )
    assert any("blog/views.py" in problem for problem in result["problems"])


def test_critic_dispute_keeps_history_and_resets_verdict(tmp_path: Path):
    sandbox = _repo(tmp_path)
    state = AuditState()
    auditor = ToolContext(sandbox, state, "auditor")
    execute_tool("read_file", {"path": "app/views.py"}, auditor)
    assert _ok(execute_tool("upsert_finding", SQLI, auditor))
    critic = ToolContext(sandbox, state, "critic")
    execute_tool("read_file", {"path": "app/views.py"}, critic)
    assert _ok(execute_tool("review_finding", {"id": "SQLI-001", "weakest_point": "来源 q 是否真来自请求参数：已读第 2 行确认来自 request.GET", "verdict": "dispute", "reason": "严重性偏高，夹具里没有数据库，影响有限", "suggested_severity": "medium"}, critic))
    assert state.findings["SQLI-001"].status == "disputed"
    assert _ok(execute_tool("upsert_finding", dict(SQLI, status="needs_review", severity="medium"), auditor))
    finding = state.findings["SQLI-001"]
    assert finding.critic_verdict == ""
    assert any("复核员否决" in entry for entry in finding.history)
    assert "medium" in finding.dispute_reason


def test_compaction_keeps_tool_call_pairs(tmp_path: Path):
    messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]
    for index in range(40):
        messages.append({"role": "assistant", "content": None, "tool_calls": [{"id": f"c{index}", "type": "function", "function": {"name": "read_file", "arguments": "{}"}}]})
        messages.append({"role": "tool", "tool_call_id": f"c{index}", "content": json.dumps({"ok": True, "path": "a.py", "content": "x" * 5000})})
    assert compact_messages(messages, max_chars=60_000)
    tool_ids = [m["tool_call_id"] for m in messages if m["role"] == "tool"]
    call_ids = [c["id"] for m in messages if m["role"] == "assistant" for c in m["tool_calls"]]
    assert tool_ids == call_ids
    assert messages[-1]["content"].startswith('{"ok"')
    assert messages[2 + 1]["content"].startswith("[elided]")


def test_packet_stays_valid_json(tmp_path: Path):
    sandbox = _repo(tmp_path)
    state = AuditState()
    ctx = ToolContext(sandbox, state, "auditor")
    execute_tool("read_file", {"path": "app/views.py"}, ctx)
    for index in range(200):
        execute_tool("upsert_finding", dict(SQLI, id=f"SQLI-{index:03d}", summary="很长的摘要" * 40), ctx)
    json.loads(_packet(state))


class _Script:
    model = "scripted"
    base_url = ""

    def __init__(self, plan):
        self.plan = plan

    def complete(self, messages, tools):
        names = {tool["function"]["name"] for tool in tools}
        role = "critic" if "accept_report" in names else "auditor"
        calls = self.plan[role].pop(0)
        return LLMResponse(
            reasoning="思考",
            tool_calls=[ToolCall(id=f"{role}-{len(self.plan[role])}-{i}", name=n, arguments=a, raw_arguments=json.dumps(a)) for i, (n, a) in enumerate(calls)],
        )


def test_full_run_with_dispute_and_resume(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    sandbox = _repo(repo)
    summary = {
        "executive_summary": "仓库存在一处 SQL 注入以及调试配置问题，已给出证据。",
        "risk_overview": "最高风险是匿名用户可控的 SQL 拼接，可以读取数据库。",
        "scope": "覆盖 settings、urls、全部 views 以及扫描线索。",
        "limitations": "静态阅读，没有运行目标应用做动态验证，结论以代码为准。",
    }
    reads = [("read_file", {"path": p}) for p in ("settings.py", "urls.py", "app/views.py", "blog/views.py")]
    auditor = [
        reads + [("search_code", {"pattern": "execute"}), ("pattern_scan", {})],
        [("set_stage", {"stage": s, "note": "did the work for " + s}) for s in ("recon", "hunt", "investigate")]
        + [
            ("upsert_finding", SQLI),
            ("triage_leads", {"ids": ["L3"], "disposition": "finding", "finding_id": "SQLI-001", "note": "这条扫描线索就是 SQLI-001 记录的 SQL 注入"}),
            ("triage_leads", {"ids": ["L1", "L2"], "disposition": "benign", "note": "测试夹具里的配置项，读过 settings.py，不计入发现"}),
        ],
        [("set_stage", {"stage": "verify", "note": "re-read the evidence"}), ("finalize_report", summary), ("get_audit_state", {})],
        [("upsert_finding", dict(SQLI, severity="medium"))],
        [("finalize_report", summary)],
    ]
    critic = [
        [("read_file", {"path": "app/views.py"})],
        [("review_finding", {"id": "SQLI-001", "weakest_point": "来源 q 是否真来自请求参数：已读第 2 行确认来自 request.GET", "verdict": "dispute", "reason": "严重性偏高，夹具里没有数据库，影响有限", "suggested_severity": "medium"}), ("accept_report", {"notes": "否决一条后接受，等审计员按建议严重性改判后再看"})],
        [("read_file", {"path": "app/views.py"})],
        [("review_finding", {"id": "SQLI-001", "weakest_point": "来源 q 是否真来自请求参数：已读第 2 行确认来自 request.GET", "verdict": "agree", "reason": "改为 medium 后与证据相符，同意上报"}), ("accept_report", {"notes": "所有发现都已逐条复核并读过上下文，接受报告"})],
    ]
    run_dir = tmp_path / "run"
    state = run_audit(sandbox, _Script({"auditor": auditor, "critic": critic}), run_dir, "abc", "https://example.invalid", auditor_steps=5, critic_steps=4, resume_steps=4, max_rounds=3)
    assert state.finalized and state.critic_accepted
    finding = state.findings["SQLI-001"]
    assert (finding.status, finding.severity, finding.critic_verdict) == ("confirmed", "medium", "agree")
    events = [json.loads(line) for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
    skipped = [e for e in events if e.get("kind") == "tool" and e["name"] == "get_audit_state"]
    assert skipped and "skipped" in skipped[0]["preview"]
    assert "数据流" in (run_dir / "report.md").read_text(encoding="utf-8")
    reloaded = load_state(run_dir / "state.json")
    assert reloaded.findings["SQLI-001"].history


def test_evaluate_matches_by_location():
    truth = {
        "issues": [
            {"id": "GT-1", "title": "a", "severity": "high", "locations": [{"path": "a.py", "start_line": 10, "end_line": 12}]},
            {"id": "GT-2", "title": "b", "severity": "low", "locations": [{"path": "b.py", "start_line": 1, "end_line": 1}]},
        ],
        "false_positive_traps": [{"id": "FP-1", "locations": [{"path": "c.py", "start_line": 5, "end_line": 5}], "wrong_categories": ["injection"]}],
    }
    findings = [
        {"id": "F1", "title": "t", "status": "confirmed", "severity": "high", "category": "xss", "evidence": [{"path": "a.py", "start_line": 11, "end_line": 11}]},
        {"id": "F2", "title": "t", "status": "confirmed", "severity": "high", "category": "injection", "evidence": [{"path": "c.py", "start_line": 5, "end_line": 5}]},
        {"id": "F3", "title": "t", "status": "rejected", "severity": "high", "category": "xss", "evidence": [{"path": "b.py", "start_line": 1, "end_line": 1}]},
    ]
    result = score(findings, truth)
    assert result["found"] == ["GT-1"]
    assert result["false_positive_trap_findings"] == 1
    assert result["missed"] == ["GT-2"]


def test_evaluate_trap_with_condition_beats_truth_overlap():
    truth = {
        "issues": [{"id": "GT-14", "title": "get", "severity": "medium", "locations": [{"path": "admin.py", "start_line": 362, "end_line": 363}]}],
        "optional": [{"id": "OPT-1", "title": "o", "severity": "info", "locations": [{"path": "s.py", "start_line": 90, "end_line": 99}]}],
        "false_positive_traps": [
            {"id": "FP-01", "title": "t", "wrong_categories": ["injection"], "locations": [{"path": "admin.py", "start_line": 362, "end_line": 363}]},
            {"id": "FP-03", "title": "p", "wrong_min_severity": "medium", "locations": [{"path": "s.py", "start_line": 92, "end_line": 98}]},
        ],
    }
    ev = [{"path": "admin.py", "start_line": 363, "end_line": 363}]
    findings = [
        {"id": "A", "title": "t", "status": "confirmed", "severity": "high", "category": "injection", "evidence": ev},
        {"id": "B", "title": "t", "status": "confirmed", "severity": "medium", "category": "csrf", "evidence": ev},
        {"id": "C", "title": "t", "status": "needs_review", "severity": "high", "category": "deserialization", "evidence": [{"path": "s.py", "start_line": 95, "end_line": 95}]},
        {"id": "D", "title": "t", "status": "confirmed", "severity": "info", "category": "deserialization", "evidence": [{"path": "s.py", "start_line": 95, "end_line": 95}]},
    ]
    rows = {row["id"]: row["verdict"] for row in score(findings, truth)["findings"]}
    assert rows == {"A": "false_positive_trap", "B": "true_positive", "C": "false_positive_trap", "D": "true_positive_optional"}


def test_evaluate_groups_and_review(tmp_path: Path):
    from audit_agent.evaluate import main

    truth = {
        "target": "t",
        "issues": [
            {"id": "GT-1", "title": "a", "severity": "high", "locations": [{"path": "a.py", "start_line": 10, "end_line": 12}]},
            {"id": "GT-2", "title": "b", "severity": "low", "locations": [{"path": "b.py", "start_line": 1, "end_line": 1}]},
        ],
    }
    truth_path = tmp_path / "truth.json"
    truth_path.write_text(json.dumps(truth), encoding="utf-8")
    hit_a = {"id": "F1", "title": "t", "status": "confirmed", "severity": "high", "category": "xss", "evidence": [{"path": "a.py", "start_line": 11, "end_line": 11}]}
    hit_b = dict(hit_a, id="F2", evidence=[{"path": "b.py", "start_line": 1, "end_line": 1}])
    dirs = []
    for name, findings in (("r1", [hit_a]), ("r2", [hit_a, hit_b])):
        run = tmp_path / name
        run.mkdir()
        (run / "findings.json").write_text(json.dumps(findings), encoding="utf-8")
        dirs.append(run)
    out = tmp_path / "EVAL.md"
    assert main([], truth_path, out, {"rep": dirs}) == 0
    text = out.read_text(encoding="utf-8")
    assert "0.75 ± 0.354" in text and "| GT-1 | high | a | 2/2 |" in text and "| GT-2 | low | b | 1/2 |" in text
    review = (dirs[0] / "REVIEW.md").read_text(encoding="utf-8")
    assert "命中真值" in review and "GT-2 [low] b（b.py:1）" in review
