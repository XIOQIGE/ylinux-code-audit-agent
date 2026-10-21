# django.nV 审计附录

## A. 运行统计

- 阅读过的文件：32
- pattern_scan 线索：15（关联发现 10，判为无害 5，重复 0，未处理 0）
- pattern_scan 次数：1；search_code / find_references 次数：11；list_endpoints：没用
- prompt tokens：3137412（缓存命中 2977408）
- completion tokens：70951（其中推理 39254）
- 复核：16 次 review_finding，其中否决 0 次

## B. 扫描线索处置

| 线索 | 规则 | 文件:行 | 处置 | 说明 |
| --- | --- | --- | --- | --- |
| L1 | `cmd-os-system` | `taskManager/misc.py:33` | finding:RCE-001 | os.system 拼接用户 title，已确认为命令注入并写入 RCE-001 |
| L2 | `secret-key` | `taskManager/settings.py:24` | finding:DESER-001 | SECRET_KEY 硬编码配合 signed_cookies+PickleSerializer，已写入 DESER-001 |
| L3 | `debug-true` | `taskManager/settings.py:28` | finding:CONFIG-001 | DEBUG=True 已写入 CONFIG-001 |
| L4 | `csrf-exempt` | `taskManager/views.py:26,710,739,779,813` | finding:AUTHZ-001 | csrf_exempt 命中 profile_by_id（账户接管，见 AUTHZ-001）与 reset_password（弱令牌暴力枚举，见 AUTH-001），forgot_password/change_password 见 CSRF-001 |
| L5 | `upload-handling` | `taskManager/views.py:175,179,715,728,730` | finding:RCE-001 | 上传处理进入 store_uploaded_file，与命令注入同一根因；profile_by_id 的头像上传（728-730 行）同样把 username 拼进 shell，已并入 RCE-001 |
| L6 | `template-safe` | `taskManager/templates/taskManager/base_backend.html:58` | finding:XSS-002 | base_backend.html 与 tutorials/base.html 均为 {{ user.username\|safe }}，同一根因，已写入 XSS-002 |
| L7 | `template-safe` | `taskManager/templates/taskManager/search.html:14` | finding:XSS-003 | 搜索 q 参数 \|safe 渲染，已写入 XSS-003 |
| L8 | `template-safe` | `taskManager/templates/taskManager/settings.html:28` | finding:XSS-004 | settings.html 对 request.META 值使用 \|safe，已写入 XSS-004 |
| L9 | `template-safe` | `taskManager/templates/taskManager/task_details.html:12,48` | finding:XSS-001 | task.title/text \|safe 渲染，已写入 XSS-001 |
| L10 | `template-safe` | `taskManager/templates/taskManager/tutorials/base.html:54` | finding:XSS-002 | base_backend.html 与 tutorials/base.html 均为 {{ user.username\|safe }}，同一根因，已写入 XSS-002 |
| L11 | `template-safe` | `taskManager/templates/taskManager/tutorials/partials/base.html:39` | benign | 均为 tutorials/partials/*.html 教程页面内的说明文字与 HTML 转义后的代码示例（如 &#123;&#123; user.username\|safe &#125;&#125;），不接收用户输入也不是模板表达式，不构成可触发漏洞 |
| L12 | `csrf-exempt` | `taskManager/templates/taskManager/tutorials/partials/csrf.html:35,49` | benign | 均为 tutorials/partials/*.html 教程页面内的说明文字与 HTML 转义后的代码示例（如 &#123;&#123; user.username\|safe &#125;&#125;），不接收用户输入也不是模板表达式，不构成可触发漏洞 |
| L13 | `upload-handling` | `taskManager/templates/taskManager/tutorials/partials/injection.html:48,52` | benign | 均为 tutorials/partials/*.html 教程页面内的说明文字与 HTML 转义后的代码示例（如 &#123;&#123; user.username\|safe &#125;&#125;），不接收用户输入也不是模板表达式，不构成可触发漏洞 |
| L14 | `cmd-os-system` | `taskManager/templates/taskManager/tutorials/partials/injection.html:74,99` | benign | 均为 tutorials/partials/*.html 教程页面内的说明文字与 HTML 转义后的代码示例（如 &#123;&#123; user.username\|safe &#125;&#125;），不接收用户输入也不是模板表达式，不构成可触发漏洞 |
| L15 | `template-safe` | `taskManager/templates/taskManager/tutorials/partials/xss.html:38` | benign | 均为 tutorials/partials/*.html 教程页面内的说明文字与 HTML 转义后的代码示例（如 &#123;&#123; user.username\|safe &#125;&#125;），不接收用户输入也不是模板表达式，不构成可触发漏洞 |

## C. 阶段记录

- `recon`：开始摸底仓库结构，计划先看目录、settings 和路由
- `hunt`：pattern_scan 命中 15 条线索，模板 |safe 均已定位上下文；正在沿数据流验证各项候选
- `investigate`：沿数据流核对了 views/misc/forms/models/settings 与模板，开始把确认的问题写入 finding
- `verify`：已写入 14 条 finding（RCE/SQLi/反序列化/越权/XSS/重定向/弱令牌/弱哈希/配置/枚举/CSRF），进入线索关闭与收尾

## D. 读过的文件

- `taskManager/settings.py`
- `taskManager/urls.py`
- `taskManager/taskManager_urls.py`
- `requirements.txt`
- `taskManager/views.py`
- `taskManager/misc.py`
- `taskManager/forms.py`
- `taskManager/models.py`
- `taskManager/templates/taskManager/base_backend.html`
- `taskManager/templates/taskManager/task_details.html`
- `taskManager/templates/taskManager/settings.html`
- `taskManager/templates/taskManager/search.html`
- `taskManager/templates/taskManager/profile_view.html`
- `taskManager/templates/taskManager/dashboard.html`
- `taskManager/templates/taskManager/upload.html`
- `taskManager/templates/taskManager/login.html`
- `taskManager/templates/taskManager/base.html`
- `taskManager/templates/taskManager/messages.html`
- `taskManager/templates/taskManager/manage_groups.html`
- `taskManager/templates/taskManager/index.html`
- `taskManager/templates/taskManager/register.html`
- `taskManager/templates/taskManager/profile.html`
- `taskManager/wsgi.py`
- `runapp.sh`
- `reset_db.sh`
- `fixtures/users.json`
- `fixtures/usersProfiles.json`
- `taskManager/tests.py`
- `taskManager/templates/taskManager/tutorials/partials/base.html`
- `taskManager/templates/taskManager/tutorials/partials/csrf.html`
- `taskManager/templates/taskManager/tutorials/partials/injection.html`
- `taskManager/templates/taskManager/tutorials/partials/xss.html`

## E. 工具调用序列

完整参数和返回见 `trajectory.md` 和 `trace.jsonl`。顺序就是模型每次返回的 tool call，代码里没有预设。a = 审计员，c = 复核员。

`a:list_files` → `a:set_stage` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:set_stage` → `a:pattern_scan` → `a:search_code` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:find_references` → `a:find_references` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:set_stage` → `a:read_file` → `a:read_file` → `a:set_stage` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:read_file` → `a:set_stage` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:triage_leads` → `a:mark_reviewed` → `a:get_audit_state` → `a:finalize_report` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:search_code` → `c:read_file` → `c:read_file` → `c:search_code` → `c:search_code` → `c:note_gap` → `c:note_gap` → `c:note_gap` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:accept_report` → `a:read_file` → `a:read_file` → `a:read_file` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:resolve_gap` → `a:resolve_gap` → `a:resolve_gap` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:resolve_gap` → `a:resolve_gap` → `a:resolve_gap` → `a:search_code` → `a:search_code` → `a:search_code` → `a:read_file` → `a:resolve_gap` → `a:resolve_gap` → `a:resolve_gap` → `a:finalize_report` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:search_code` → `c:search_code` → `c:read_file` → `c:read_file` → `c:read_file`

## F. 引用核对

共核对 43 条引用，未通过 0 条。

- 通过 `RCE-001` `taskManager/misc.py:31-39`
- 通过 `RCE-001` `taskManager/views.py:178-179`
- 通过 `SQLI-001` `taskManager/views.py:182-185`
- 通过 `DESER-001` `taskManager/settings.py:24-24`
- 通过 `DESER-001` `taskManager/settings.py:104-104`
- 通过 `DESER-001` `taskManager/settings.py:109-110`
- 通过 `AUTHZ-001` `taskManager/views.py:710-712`
- 通过 `AUTHZ-001` `taskManager/views.py:718-719`
- 通过 `AUTHZ-001` `taskManager/views.py:726-727`
- 通过 `AUTHZ-002` `taskManager/views.py:120-124`
- 通过 `AUTHZ-002` `taskManager/views.py:130-138`
- 通过 `AUTHZ-002` `taskManager/views.py:155-155`
- 通过 `AUTHZ-003` `taskManager/views.py:275-276`
- 通过 `AUTHZ-003` `taskManager/views.py:286-289`
- 通过 `AUTHZ-003` `taskManager/views.py:376-380`
- 通过 `AUTHZ-003` `taskManager/views.py:206-213`
- 通过 `XSS-001` `taskManager/views.py:246-247`
- 通过 `XSS-001` `taskManager/views.py:254-261`
- 通过 `XSS-001` `taskManager/templates/taskManager/task_details.html:12-12`
- 通过 `XSS-001` `taskManager/templates/taskManager/task_details.html:48-48`
- 通过 `XSS-002` `taskManager/views.py:718-719`
- 通过 `XSS-002` `taskManager/templates/taskManager/base_backend.html:57-58`
- 通过 `XSS-002` `taskManager/views.py:491-493`
- 通过 `XSS-003` `taskManager/views.py:661-662`
- 通过 `XSS-003` `taskManager/templates/taskManager/search.html:14-14`
- 通过 `XSS-004` `taskManager/views.py:837-841`
- 通过 `XSS-004` `taskManager/templates/taskManager/settings.html:27-28`
- 通过 `REDIR-001` `taskManager/views.py:385-387`
- 通过 `AUTH-001` `taskManager/views.py:788-796`
- 通过 `AUTH-001` `taskManager/views.py:739-740`
- 通过 `AUTH-001` `taskManager/views.py:744-747`
- 通过 `CRYPTO-001` `taskManager/settings.py:100-101`
- 通过 `CONFIG-001` `taskManager/settings.py:27-31`
- 通过 `INFO-001` `taskManager/views.py:391-395`
- 通过 `INFO-001` `taskManager/templates/taskManager/login.html:6-15`
- 通过 `CSRF-001` `taskManager/views.py:779-780`
- 通过 `CSRF-001` `taskManager/views.py:813-814`
- 通过 `AUTHZ-004` `taskManager/forms.py:71-75`
- 通过 `AUTHZ-004` `taskManager/views.py:429-434`
- 通过 `FILE-001` `taskManager/misc.py:26-27`
- 通过 `FILE-001` `taskManager/misc.py:41-41`
- 通过 `FILE-001` `taskManager/forms.py:78-81`
- 通过 `AUTH-002` `taskManager/views.py:390-401`
