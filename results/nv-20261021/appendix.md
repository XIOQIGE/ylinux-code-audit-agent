# django.nV 审计附录

## A. 运行统计

- 阅读过的文件：32
- pattern_scan 线索：16（关联发现 10，判为无害 6，重复 0，未处理 0）
- pattern_scan 次数：1；search_code / find_references 次数：8；list_endpoints：用过
- prompt tokens：3460065（缓存命中 3313280）
- completion tokens：90747（其中推理 53207）
- 复核：22 次 review_finding，其中否决 0 次

## B. 扫描线索处置

| 线索 | 规则 | 文件:行 | 处置 | 说明 |
| --- | --- | --- | --- | --- |
| L1 | `autoescape-off` | `fixtures/taskManagerNotes.json:96,107` | benign | fixtures/taskManagerNotes.json 中的 <script> 与 {% autoescape off %} 只是演示种子数据；task_details.html 第 81/84 行用普通 {{ }}（自动转义）渲染 Notes.title/text，不会执行，不构成 XSS。 |
| L2 | `cmd-os-system` | `taskManager/misc.py:33` | finding:CMDI-001 | os.system 拼接用户 title，已读 misc.py 与 upload/profile_by_id 调用链，确认为未认证命令注入。 |
| L3 | `secret-key` | `taskManager/settings.py:24` | finding:CONFIG-002 | SECRET_KEY 硬编码在 settings.py:24，独立记为配置问题，并与 SESSION-001 关联。 |
| L4 | `debug-true` | `taskManager/settings.py:28` | finding:CONFIG-001 | DEBUG=True 且 TEMPLATE_DEBUG=True 提交进仓库。 |
| L5 | `csrf-exempt` | `taskManager/views.py:26,710,739,779,813` | finding:CSRF-001 | profile_by_id 的 @csrf_exempt 覆盖敏感改密操作；reset_password/forgot_password/change_password 虽也豁免，但分别需要一次性令牌/旧密码才能完成敏感操作，CSRF 无法单独利用，判为良性。 |
| L6 | `upload-handling` | `taskManager/views.py:175,179,715,728,730` | finding:FILE-002 | 上传文件名与存储位置无校验；命令注入与 SQL 注入分别记在 CMDI-001/SQLI-001。 |
| L7 | `template-safe` | `taskManager/templates/taskManager/base_backend.html:58` | finding:XSS-004 | base_backend.html:58 与 tutorials/base.html:54 均以 \|safe 渲染用户名，同根因（用户名可被 profile_by_id 越权写入任意值）。 |
| L8 | `template-safe` | `taskManager/templates/taskManager/search.html:14` | finding:XSS-001 | search.html 第 14 行 {{q\|safe}}，q 来自 GET 且 search 视图无鉴权。 |
| L9 | `template-safe` | `taskManager/templates/taskManager/settings.html:28` | finding:XSS-002 | settings.html 第 28 行 {{v\|safe}} 渲染 request.META，含攻击者可控请求头。 |
| L10 | `template-safe` | `taskManager/templates/taskManager/task_details.html:12,48` | finding:XSS-003 | task_details.html 第 12/48 行以 \|safe 渲染任务标题与正文，来源 task_create/task_edit 无鉴权。 |
| L11 | `template-safe` | `taskManager/templates/taskManager/tutorials/base.html:54` | finding:XSS-004 | base_backend.html:58 与 tutorials/base.html:54 均以 \|safe 渲染用户名，同根因（用户名可被 profile_by_id 越权写入任意值）。 |
| L12 | `template-safe` | `taskManager/templates/taskManager/tutorials/partials/base.html:39` | benign | 已读 tutorials/partials/base.html、csrf.html、injection.html、xss.html：均为教程说明文档，代码片段以 &lt;/&#123; 等 HTML 实体转义后展示，不是可注入的模板输出，与真实漏洞无关。 |
| L13 | `csrf-exempt` | `taskManager/templates/taskManager/tutorials/partials/csrf.html:35,49` | benign | 已读 tutorials/partials/base.html、csrf.html、injection.html、xss.html：均为教程说明文档，代码片段以 &lt;/&#123; 等 HTML 实体转义后展示，不是可注入的模板输出，与真实漏洞无关。 |
| L14 | `upload-handling` | `taskManager/templates/taskManager/tutorials/partials/injection.html:48,52` | benign | 已读 tutorials/partials/base.html、csrf.html、injection.html、xss.html：均为教程说明文档，代码片段以 &lt;/&#123; 等 HTML 实体转义后展示，不是可注入的模板输出，与真实漏洞无关。 |
| L15 | `cmd-os-system` | `taskManager/templates/taskManager/tutorials/partials/injection.html:74,99` | benign | 已读 tutorials/partials/base.html、csrf.html、injection.html、xss.html：均为教程说明文档，代码片段以 &lt;/&#123; 等 HTML 实体转义后展示，不是可注入的模板输出，与真实漏洞无关。 |
| L16 | `template-safe` | `taskManager/templates/taskManager/tutorials/partials/xss.html:38` | benign | 已读 tutorials/partials/base.html、csrf.html、injection.html、xss.html：均为教程说明文档，代码片段以 &lt;/&#123; 等 HTML 实体转义后展示，不是可注入的模板输出，与真实漏洞无关。 |

## C. 阶段记录

- `recon`：已读 settings.py（Django 1.7 风格配置，DEBUG=True、MD5 密码哈希、signed_cookies+PicleSerializer 会话、SECRET_KEY 硬编码）与两级 urls；接下来深入 views/forms/models
- `investigate`：已读完全部 views.py（841 行）、misc.py、forms.py、models.py、settings.py、两级 urls、fixtures 及关键模板（settings/search/task_details/base_backend/profile/upload/manage_groups/register 等）。确认命令注入、SQL 注入、会话 pickle RCE、超级用户注册、IDOR 等数据流完整
- `verify`：已写入 17 条 finding（CMDI/SQLI/SESSION/AUTH×2/ACCESS×2/XSS×4/CSRF/CRYPTO/CONFIG×3/REDIRECT/FILE×2/COMP），16 条 pattern_scan 线索全部完成 triage（finding 或 benign），证据引用已通过行号核对
- `hunt`：已运行 pattern_scan（16 条线索）并辅以 search_code 检索 |safe/csrf_token/csrf_exempt/os.system/admin_g/has_perm/权限定义等危险点，全部线索已 triage

## D. 读过的文件

- `taskManager/settings.py`
- `taskManager/urls.py`
- `taskManager/taskManager_urls.py`
- `taskManager/views.py`
- `taskManager/misc.py`
- `taskManager/forms.py`
- `taskManager/models.py`
- `taskManager/templates/taskManager/settings.html`
- `taskManager/templates/taskManager/search.html`
- `taskManager/templates/taskManager/task_details.html`
- `taskManager/templates/taskManager/base_backend.html`
- `taskManager/templates/taskManager/profile.html`
- `taskManager/templates/taskManager/index.html`
- `taskManager/templates/taskManager/upload.html`
- `fixtures/users.json`
- `requirements.txt`
- `taskManager/templates/taskManager/reset_password.html`
- `taskManager/templates/taskManager/manage_groups.html`
- `taskManager/templates/taskManager/register.html`
- `fixtures/usersProfiles.json`
- `taskManager/templates/taskManager/profile_view.html`
- `taskManager/templates/taskManager/tutorials/injection.html`
- `taskManager/templates/taskManager/tutorials/base.html`
- `taskManager/wsgi.py`
- `reset_db.sh`
- `runapp.sh`
- `fixtures/taskManagerNotes.json`
- `taskManager/templates/taskManager/tutorials/partials/base.html`
- `taskManager/templates/taskManager/tutorials/partials/csrf.html`
- `taskManager/templates/taskManager/tutorials/partials/xss.html`
- `taskManager/templates/taskManager/tutorials/partials/injection.html`
- `README.md`

## E. 工具调用序列

完整参数和观察见 `trajectory.md` 与 `trace.jsonl`。顺序是模型每次返回的 tool call，不是脚本写死的。前缀 a = 审计员，c = 复核员。

`a:set_stage` → `a:list_files` → `a:read_file` → `a:read_file` → `a:read_file` → `a:set_stage` → `a:list_endpoints` → `a:set_stage` → `a:pattern_scan` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:list_files` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:search_code` → `a:read_file` → `a:read_file` → `a:search_code` → `a:search_code` → `a:search_code` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:search_code` → `a:read_file` → `a:search_code` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:set_stage` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:read_file` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:triage_leads` → `a:triage_leads` → `a:set_stage` → `a:mark_reviewed` → `a:mark_reviewed` → `a:mark_reviewed` → `a:finalize_report` → `a:set_stage` → `a:finalize_report` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:search_code` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:search_code` → `c:read_file` → `c:read_file` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:note_gap` → `c:note_gap` → `c:accept_report` → `a:read_file` → `a:read_file` → `a:read_file` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:resolve_gap` → `a:resolve_gap` → `a:finalize_report` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:review_finding` → `c:review_finding` → `c:accept_report`

## F. 引用核对

共核对 41 条引用，未通过 0 条。

- 通过 `CMDI-001` `taskManager/views.py:177-179`
- 通过 `CMDI-001` `taskManager/misc.py:31-41`
- 通过 `SQLI-001` `taskManager/views.py:181-185`
- 通过 `FILE-001` `taskManager/views.py:206-217`
- 通过 `FILE-001` `taskManager/misc.py:41-41`
- 通过 `SESSION-001` `taskManager/settings.py:23-24`
- 通过 `SESSION-001` `taskManager/settings.py:103-109`
- 通过 `AUTH-001` `taskManager/forms.py:71-75`
- 通过 `AUTH-001` `taskManager/views.py:429-434`
- 通过 `AUTH-002` `taskManager/views.py:710-712`
- 通过 `AUTH-002` `taskManager/views.py:718-727`
- 通过 `ACCESS-001` `taskManager/views.py:116-138`
- 通过 `ACCESS-001` `taskManager/views.py:154-163`
- 通过 `ACCESS-002` `taskManager/views.py:299-306`
- 通过 `ACCESS-002` `taskManager/views.py:376-380`
- 通过 `XSS-003` `taskManager/views.py:246-261`
- 通过 `XSS-003` `taskManager/templates/taskManager/task_details.html:11-12`
- 通过 `XSS-003` `taskManager/templates/taskManager/task_details.html:47-48`
- 通过 `XSS-004` `taskManager/templates/taskManager/base_backend.html:57-58`
- 通过 `XSS-004` `taskManager/templates/taskManager/tutorials/base.html:53-54`
- 通过 `XSS-004` `taskManager/views.py:718-719`
- 通过 `XSS-002` `taskManager/views.py:837-841`
- 通过 `XSS-002` `taskManager/templates/taskManager/settings.html:22-29`
- 通过 `XSS-001` `taskManager/views.py:661-675`
- 通过 `XSS-001` `taskManager/templates/taskManager/search.html:13-14`
- 通过 `CSRF-001` `taskManager/views.py:710-712`
- 通过 `CSRF-001` `taskManager/views.py:726-727`
- 通过 `CRYPTO-001` `taskManager/settings.py:100-101`
- 通过 `CRYPTO-001` `fixtures/users.json:8-9`
- 通过 `CONFIG-002` `taskManager/settings.py:23-24`
- 通过 `CONFIG-001` `taskManager/settings.py:26-29`
- 通过 `CONFIG-003` `taskManager/settings.py:108-110`
- 通过 `REDIRECT-001` `taskManager/views.py:385-387`
- 通过 `FILE-002` `taskManager/misc.py:24-39`
- 通过 `COMP-001` `requirements.txt:1-1`
- 通过 `RESET-001` `taskManager/views.py:788-794`
- 通过 `RESET-001` `taskManager/views.py:739-747`
- 通过 `RESET-001` `README.md:8-8`
- 通过 `ACCESS-003` `taskManager/views.py:593-604`
- 通过 `ACCESS-003` `taskManager/views.py:605-625`
- 通过 `ACCESS-003` `taskManager/views.py:491-508`
