import json
from pathlib import Path

import pytest

from audit_agent.agent import run_loop
from audit_agent.llm import LLMResponse, ToolCall
from audit_agent.sandbox import Sandbox, SandboxError
from audit_agent.scanner import scan
from audit_agent.state import AuditState
from audit_agent.tools import ToolContext, execute_tool
from audit_agent.verifier import check_quote


class ScriptedModel:
    """Returns tool calls in whatever order the test supplies.

    The production loop does not know this order. A second script with the
    opposite order is the regression check that the runner is not a fixed pipeline.
    """

    def __init__(self, rounds: list[list[tuple[str, dict]]]):
        self.rounds = rounds
        self.seen_tool_names: list[str] = []
        self.model = "scripted"

    def complete(self, messages, tools):
        for message in messages:
            if message.get("role") == "tool":
                payload = json.loads(message["content"])
                if "matches" in payload:
                    self.seen_tool_names.append("observed-search")
                if "content" in payload and "path" in payload:
                    self.seen_tool_names.append("observed-read")
        calls = self.rounds.pop(0)
        tool_calls = []
        for index, (name, arguments) in enumerate(calls, start=1):
            raw = json.dumps(arguments)
            tool_calls.append(ToolCall(id=f"call-{name}-{index}-{len(tool_calls)}", name=name, arguments=arguments, raw_arguments=raw))
        return LLMResponse(content="", tool_calls=tool_calls)


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
    (app / "models.py").write_text("class Post(object):\n    pass\n", encoding="utf-8")
    (app / "utils.py").write_text("def noop():\n    return None\n", encoding="utf-8")
    (tmp_path / "outside.txt").write_text("nope\n", encoding="utf-8")
    return Sandbox(tmp_path)


def test_loop_follows_two_different_model_orders(tmp_path: Path):
    sandbox = _repo(tmp_path)
    first = ScriptedModel(
        [
            [("search_code", {"pattern": "execute", "path": "app", "glob": "*.py"})],
            [("read_file", {"path": "app/views.py"})],
        ]
    )
    state = AuditState()
    trace_path = tmp_path / "trace.jsonl"
    from audit_agent.agent import Trace

    run_loop(
        first,
        ToolContext(sandbox, state, "auditor"),
        [{"role": "system", "content": "sys"}, {"role": "user", "content": "go"}],
        max_steps=2,
        trace=Trace(trace_path),
        usage={"prompt_tokens": 0, "completion_tokens": 0},
        state_path=tmp_path / "state.json",
    )
    assert [event["name"] for event in _tools(trace_path)] == ["search_code", "read_file"]

    second = ScriptedModel(
        [
            [("read_file", {"path": "settings.py"})],
            [("pattern_scan", {"categories": ["config"]})],
        ]
    )
    trace_path_2 = tmp_path / "trace2.jsonl"
    run_loop(
        second,
        ToolContext(sandbox, AuditState(), "auditor"),
        [{"role": "system", "content": "sys"}, {"role": "user", "content": "go"}],
        max_steps=2,
        trace=Trace(trace_path_2),
        usage={"prompt_tokens": 0, "completion_tokens": 0},
        state_path=tmp_path / "state2.json",
    )
    assert [event["name"] for event in _tools(trace_path_2)] == ["read_file", "pattern_scan"]


def test_quote_must_match_source(tmp_path: Path):
    sandbox = _repo(tmp_path)
    ok, _excerpt = check_quote(sandbox, "app/views.py", 3, 4, "cursor.execute(sql)")
    assert ok
    bad, actual = check_quote(sandbox, "app/views.py", 3, 4, "os.system(q)")
    assert not bad
    assert "SELECT" in actual


def test_upsert_rejects_invented_quote_and_accepts_real_one(tmp_path: Path):
    sandbox = _repo(tmp_path)
    ctx = ToolContext(sandbox, AuditState(), "auditor")
    rejected = execute_tool(
        "upsert_finding",
        {
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
            "evidence": [
                {"path": "app/views.py", "start_line": 3, "end_line": 4, "quote": "this quote is not in the file at all"}
            ],
        },
        ctx,
    )
    body = json.loads(rejected.content)
    assert body["ok"] is False
    assert "SQLI-001" not in ctx.state.findings

    accepted = execute_tool(
        "upsert_finding",
        {
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
            "evidence": [
                {
                    "path": "app/views.py",
                    "start_line": 3,
                    "end_line": 4,
                    "quote": 'sql = "SELECT * FROM posts WHERE title = \'%s\'" % q\n    cursor.execute(sql)',
                }
            ],
        },
        ctx,
    )
    assert json.loads(accepted.content)["ok"] is True
    assert ctx.state.findings["SQLI-001"].status == "confirmed"


def test_finalize_gate_requires_coverage(tmp_path: Path):
    sandbox = _repo(tmp_path)
    ctx = ToolContext(sandbox, AuditState(), "auditor")
    early = execute_tool(
        "finalize_report",
        {
            "executive_summary": "还没有完成阅读和取证，这里只是一段足够长的占位综述文本。",
            "risk_overview": "风险还没有建立在已经阅读的代码之上，所以不能结束。",
            "scope": "范围尚未覆盖配置、路由和视图。",
            "limitations": "静态阅读不能代替运行时验证。",
        },
        ctx,
    )
    problems = json.loads(early.content)["problems"]
    assert any("settings.py" in item for item in problems)
    assert json.loads(early.content)["ok"] is False


def test_path_escape_is_rejected(tmp_path: Path):
    sandbox = _repo(tmp_path)
    with pytest.raises(SandboxError):
        sandbox.resolve("../secret.txt")
    ctx = ToolContext(sandbox, AuditState(), "auditor")
    result = execute_tool("read_file", {"path": "../secret.txt"}, ctx)
    assert json.loads(result.content)["ok"] is False


def test_scanner_flags_fixture_sql_and_secret(tmp_path: Path):
    sandbox = _repo(tmp_path)
    hits, _truncated = scan(sandbox, ".", None, False)
    ids = {hit.rule_id for hit in hits}
    assert "sql-execute-format" in ids or "sql-statement-format" in ids
    assert "secret-key" in ids
    assert "debug-true" in ids


def test_critic_must_reread_high_finding(tmp_path: Path):
    sandbox = _repo(tmp_path)
    state = AuditState()
    auditor = ToolContext(sandbox, state, "auditor")
    execute_tool("read_file", {"path": "app/views.py"}, auditor)
    execute_tool(
        "upsert_finding",
        {
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
            "evidence": [
                {"path": "app/views.py", "start_line": 4, "end_line": 4, "quote": "cursor.execute(sql)"}
            ],
        },
        auditor,
    )
    critic = ToolContext(sandbox, state, "critic")
    blocked = execute_tool("accept_report", {"notes": "我还没有重新打开证据文件就想接受。"}, critic)
    assert json.loads(blocked.content)["ok"] is False
    early = execute_tool("review_finding", {"id": "SQLI-001", "weakest_point": "来源 q 是否真来自请求参数：已读第 2 行确认来自 request.GET", "verdict": "agree", "reason": "还没读文件就想同意这条发现。"}, critic)
    assert json.loads(early.content)["ok"] is False
    execute_tool("read_file", {"path": "app/views.py"}, critic)
    reviewed = execute_tool("review_finding", {"id": "SQLI-001", "weakest_point": "来源 q 是否真来自请求参数：已读第 2 行确认来自 request.GET", "verdict": "agree", "reason": "q 来自 request.GET，直接拼进 SQL 后执行。"}, critic)
    assert json.loads(reviewed.content)["ok"] is True
    accepted = execute_tool("accept_report", {"notes": "已重读 views.py，引用和数据流成立。"}, critic)
    assert json.loads(accepted.content)["ok"] is True
    assert accepted.stop is True


def _tools(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        if event.get("kind") == "tool":
            rows.append(event)
    return rows
