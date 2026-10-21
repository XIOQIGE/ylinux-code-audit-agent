import json
from pathlib import Path

from audit_agent.agent import run_audit
from audit_agent.cli import _replay
from audit_agent.endpoints import list_endpoints
from audit_agent.llm import RecordingLLM
from audit_agent.sandbox import Sandbox
from audit_agent.state import AuditState
from audit_agent.tools import ToolContext, execute_tool

from test_gates import SQLI, _repo, _Script

WEAK = "来源 q 是否真来自请求参数：已读第 2 行确认来自 request.GET"


def _django(tmp_path: Path) -> Sandbox:
    site = tmp_path / "site"
    site.mkdir()
    (site / "settings.py").write_text("ROOT_URLCONF = 'site.urls'\nSESSION_ENGINE = 'x'\n", encoding="utf-8")
    (site / "urls.py").write_text(
        "from django.conf.urls import url, include\n"
        "# url(r'^dead/$', 'shop.views.dead'),\n"
        "urlpatterns = [\n"
        "    url(r'^shop/', include('shop.urls')),\n"
        "]\n",
        encoding="utf-8",
    )
    shop = tmp_path / "shop"
    shop.mkdir()
    (shop / "urls.py").write_text(
        "from django.conf.urls import url\n"
        "from shop import views\n"
        "urlpatterns = [\n"
        "    url(r'^item/(?P<item_id>\\d+)/delete/$', views.delete_item),\n"
        "    url(r'^list/$', views.listing),\n"
        "]\n",
        encoding="utf-8",
    )
    (shop / "views.py").write_text(
        "from django.views.decorators.csrf import csrf_exempt\n"
        "\n"
        "@csrf_exempt\n"
        "def delete_item(request, item_id):\n"
        "    Item.objects.get(pk=item_id).delete()\n"
        "\n"
        "def listing(request):\n"
        "    if not request.user.is_authenticated():\n"
        "        return None\n"
        "    return request.GET.get('page')\n",
        encoding="utf-8",
    )
    static = shop / "static"
    static.mkdir()
    (static / "jquery.py").write_text("SESSION_ENGINE = 'vendored'\n", encoding="utf-8")
    return Sandbox(tmp_path)


def test_list_endpoints_follows_includes_and_flags(tmp_path: Path):
    result = list_endpoints(_django(tmp_path))
    assert result["root_urlconf"] == "site/urls.py"
    by_view = {item.view: item for item in result["endpoints"]}
    assert set(by_view) == {"shop.views.delete_item", "shop.views.listing"}
    delete = by_view["shop.views.delete_item"]
    assert delete.route == "^shop/item/(?P<item_id>\\d+)/delete/$"
    assert (delete.file, delete.line) == ("shop/views.py", 4)
    assert {"writes_without_auth_check", "writes_on_any_method", "object_id_without_owner_check", "csrf_exempt"} <= set(delete.flags)
    listing = by_view["shop.views.listing"]
    assert "is_authenticated" in listing.auth and listing.inputs == ["GET"] and not listing.flags


def test_list_endpoints_tool_counts_as_recon(tmp_path: Path):
    ctx = ToolContext(_django(tmp_path), AuditState(), "auditor")
    body = json.loads(execute_tool("list_endpoints", {}, ctx).content)
    assert body["ok"] and body["count"] == 2
    assert ctx.state.endpoints_listed


def test_find_references_buckets_and_skips_vendor(tmp_path: Path):
    ctx = ToolContext(_django(tmp_path), AuditState(), "auditor")
    body = json.loads(execute_tool("find_references", {"symbol": "settings.SESSION_ENGINE"}, ctx).content)
    assert body["ok"] and body["matched_name"] == "SESSION_ENGINE"
    assert [row["path"] for row in body["definitions"]] == ["site/settings.py"]
    vendored = json.loads(execute_tool("find_references", {"symbol": "SESSION_ENGINE", "include_vendor": True}, ctx).content)
    assert "shop/static/jquery.py" in [row["path"] for row in vendored["definitions"]]
    bad = json.loads(execute_tool("find_references", {"symbol": "a; rm -rf"}, ctx).content)
    assert not bad["ok"]


def test_vendor_dirs_are_skipped_by_listing(tmp_path: Path):
    sandbox = _django(tmp_path)
    files = {sandbox.rel(path) for path in sandbox.iter_files(".", False, "*.py", 12)}
    assert "shop/views.py" in files and "shop/static/jquery.py" not in files
    custom = Sandbox(tmp_path, ["shop"])
    assert not any(sandbox_rel.startswith("shop/") for sandbox_rel in (custom.rel(p) for p in custom.iter_files(".", False, "*.py", 12)))


def test_reported_finding_requires_entry_role(tmp_path: Path):
    ctx = ToolContext(_repo(tmp_path), AuditState(), "auditor")
    execute_tool("read_file", {"path": "app/views.py"}, ctx)
    missing = {key: value for key, value in SQLI.items() if key != "entry_role"}
    assert not json.loads(execute_tool("upsert_finding", missing, ctx).content)["ok"]
    wrong = dict(SQLI, entry_role="everyone")
    assert not json.loads(execute_tool("upsert_finding", wrong, ctx).content)["ok"]
    assert json.loads(execute_tool("upsert_finding", dict(missing, status="candidate"), ctx).content)["ok"]
    assert json.loads(execute_tool("upsert_finding", SQLI, ctx).content)["ok"]
    assert ctx.state.findings["SQLI-001"].entry_role == "anonymous"


def test_review_requires_weakest_point(tmp_path: Path):
    sandbox = _repo(tmp_path)
    state = AuditState()
    auditor = ToolContext(sandbox, state, "auditor")
    execute_tool("read_file", {"path": "app/views.py"}, auditor)
    execute_tool("upsert_finding", SQLI, auditor)
    critic = ToolContext(sandbox, state, "critic")
    execute_tool("read_file", {"path": "app/views.py"}, critic)
    review = {"id": "SQLI-001", "verdict": "agree", "reason": "q 来自 request.GET，直接拼进 SQL 后执行。"}
    assert not json.loads(execute_tool("review_finding", review, critic).content)["ok"]
    assert not json.loads(execute_tool("review_finding", dict(review, weakest_point="没问题"), critic).content)["ok"]
    assert json.loads(execute_tool("review_finding", dict(review, weakest_point=WEAK), critic).content)["ok"]
    assert state.findings["SQLI-001"].critic_weakest_point == WEAK


def _plan():
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
        [("set_stage", {"stage": "verify", "note": "re-read the evidence"}), ("finalize_report", summary)],
    ]
    critic = [
        [("read_file", {"path": "app/views.py"})],
        [
            ("review_finding", {"id": "SQLI-001", "weakest_point": WEAK, "verdict": "agree", "reason": "q 来自 request.GET，直接拼进 SQL 后执行"}),
            ("accept_report", {"notes": "所有发现都已逐条复核并读过上下文，接受报告"}),
        ],
    ]
    return {"auditor": auditor, "critic": critic}


def test_run_writes_appendix_decisions_and_replays(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    sandbox = _repo(repo)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    recording = run_dir / "llm_responses.jsonl"
    script = _Script(_plan())
    state = run_audit(
        sandbox,
        RecordingLLM(script, recording, "auditor"),
        run_dir,
        "abc",
        "https://example.invalid",
        auditor_steps=5,
        critic_steps=4,
        resume_steps=4,
        max_rounds=3,
        critic_llm=RecordingLLM(script, recording, "critic"),
        extra_meta={"target_dir": repo.as_posix(), "vendor": []},
    )
    assert state.finalized and state.critic_accepted
    for name in ("report.md", "appendix.md", "decisions.md", "findings.json", "meta.json"):
        assert (run_dir / name).is_file(), name
    report = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "发现总表" in report and "SQLI-001" in report
    assert "最弱一环" in (run_dir / "decisions.md").read_text(encoding="utf-8")
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["critic_reviews"] == 1 and meta["critic_disputes"] == 0
    assert _replay(run_dir, repo, str(tmp_path / "replay")) == 0
    assert json.loads((tmp_path / "replay" / "findings.json").read_text(encoding="utf-8"))[0]["id"] == "SQLI-001"
