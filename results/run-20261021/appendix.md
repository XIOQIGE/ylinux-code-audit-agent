# ylinux_old 审计附录

## A. 运行统计

- 阅读过的文件：53
- pattern_scan 线索：29（关联发现 22，判为无害 7，重复 0，未处理 0）
- pattern_scan 次数：1；search_code / find_references 次数：15；list_endpoints：没用
- prompt tokens：5765015（缓存命中 5563008）
- completion tokens：82331（其中推理 45189）
- 复核：0 次 review_finding，其中否决 0 次

## B. 扫描线索处置

| 线索 | 规则 | 文件:行 | 处置 | 说明 |
| --- | --- | --- | --- | --- |
| L1 | `debug-true` | `settings.py:18` | finding:CONFIG-001 | DEBUG=True 与 DEBUG 下 MEDIA 目录浏览归入同一配置问题。 |
| L2 | `db-password` | `settings.py:49` | finding:CONFIG-002 | 明文弱口令入库；当前 sqlite3 ENGINE 不生效，故低危。 |
| L3 | `secret-key` | `settings.py:79` | finding:CRYPTO-001 | 硬编码 SECRET_KEY 使会话 pickle 防篡改 MD5 校验与重置令牌失去保密性，同一根因。 |
| L4 | `sql-statement-format` | `app/account/backends.py:44` | benign | SQL 仅用 % 拼接经 quote_name 的固定表/列名，用户值走 cursor.execute(sql, [user_obj.id]) 参数列表，不构成注入。 |
| L5 | `weak-hash` | `app/account/models.py:63,65,364,367,427,430` | finding:CRYPTO-002 | 单轮 md5/sha1 口令哈希与 random.random() 派生的 5 字符盐同属弱口令存储问题。 |
| L6 | `insecure-random` | `app/account/models.py:232,364,427` | finding:CRYPTO-002 | 单轮 md5/sha1 口令哈希与 random.random() 派生的 5 字符盐同属弱口令存储问题。 |
| L7 | `weak-hash` | `app/account/tokens.py:54` | finding:CRYPTO-001 | 硬编码 SECRET_KEY 使会话 pickle 防篡改 MD5 校验与重置令牌失去保密性，同一根因。 |
| L8 | `open-redirect` | `app/account/views.py:38,60` | finding:REDIRECT-001 | next 参数与 HTTP_REFERER 直接作为重定向目标，三处同一根因。 |
| L9 | `open-redirect` | `app/admin/views.py:62,134,192,257,354` | finding:REDIRECT-001 | next 参数与 HTTP_REFERER 直接作为重定向目标，三处同一根因。 |
| L10 | `redirect-referer` | `app/admin/views.py:65,134,192,257,354` | finding:REDIRECT-001 | next 参数与 HTTP_REFERER 直接作为重定向目标，三处同一根因。 |
| L11 | `cmd-popen` | `app/admin/views.py:362` | benign | os.popen('whoami') 与 os.system('killall -u %s' % user) 中的 user 取自 whoami 输出（服务进程身份），不是请求数据，无命令注入；仅管理员权限可调用，且是固定命令。 |
| L12 | `cmd-os-system` | `app/admin/views.py:363` | benign | os.popen('whoami') 与 os.system('killall -u %s' % user) 中的 user 取自 whoami 输出（服务进程身份），不是请求数据，无命令注入；仅管理员权限可调用，且是固定命令。 |
| L13 | `http-response-format` | `app/admin/views.py:400,481` | finding:XSS-002 | form.errors 直接 HttpResponse 输出未转义，属反射型 XSS（需管理员权限，已在 finding 中降权说明）。 |
| L14 | `http-response-format` | `app/home/views.py:77` | benign | robots 响应为固定字符串，无用户输入。 |
| L15 | `weak-hash` | `app/sessions/models.py:18,63` | finding:CRYPTO-001 | 硬编码 SECRET_KEY 使会话 pickle 防篡改 MD5 校验与重置令牌失去保密性，同一根因。 |
| L16 | `pickle-load` | `app/sessions/models.py:67` | finding:CRYPTO-001 | 硬编码 SECRET_KEY 使会话 pickle 防篡改 MD5 校验与重置令牌失去保密性，同一根因。 |
| L17 | `weak-hash` | `app/sessions/backends/base.py:89,95,141` | finding:CRYPTO-001 | 硬编码 SECRET_KEY 使会话 pickle 防篡改 MD5 校验与重置令牌失去保密性，同一根因。 |
| L18 | `pickle-load` | `app/sessions/backends/base.py:98` | finding:CRYPTO-001 | 硬编码 SECRET_KEY 使会话 pickle 防篡改 MD5 校验与重置令牌失去保密性，同一根因。 |
| L19 | `template-safe` | `app/wiki/utils.py:18` | finding:XSS-001 | \|safe 输出点与无 safe_mode 的 Markdown 渲染共同构成存储型 XSS。 |
| L20 | `upload-handling` | `app/ydata/views.py:40` | finding:FILE-001 | 上传文件名未清洗，拼入路径/JS/响应头；穿越被数字前缀恰好挡住，其余风险成立。 |
| L21 | `weak-hash` | `app/ydata/views.py:52` | benign | sha1 仅用于附件去重哈希，非安全用途。 |
| L22 | `http-response-format` | `app/ylab/views.py:21` | benign | `current` 是 datetime.now() 的 repr，非用户输入，拼接固定 JS 无注入。 |
| L23 | `upload-handling` | `app/ylab/views.py:31` | finding:FILE-001 | 上传文件名未清洗，拼入路径/JS/响应头；穿越被数字前缀恰好挡住，其余风险成立。 |
| L24 | `csrf-exempt` | `lib/django_xmlrpc/views.py:50,52,73` | benign | XML-RPC 方法凭据随每次调用在请求体内传递，不依赖 Cookie 会话，csrf_exempt 无 CSRF 风险；站点整体 CSRF 缺失已由 CSRF-001 覆盖。 |
| L25 | `template-safe` | `templates/bbs/topic.html:23,30` | finding:XSS-001 | \|safe 输出点与无 safe_mode 的 Markdown 渲染共同构成存储型 XSS。 |
| L26 | `template-safe` | `templates/wiki/editPostAJAX.html:19` | finding:XSS-001 | \|safe 输出点与无 safe_mode 的 Markdown 渲染共同构成存储型 XSS。 |
| L27 | `template-safe` | `templates/wiki/post.html:12` | finding:XSS-001 | \|safe 输出点与无 safe_mode 的 Markdown 渲染共同构成存储型 XSS。 |
| L28 | `template-safe` | `templates/wiki/replayAJAX.html:16` | finding:XSS-001 | \|safe 输出点与无 safe_mode 的 Markdown 渲染共同构成存储型 XSS。 |
| L29 | `template-safe` | `templates/wiki/topic.html:54,59` | finding:XSS-001 | \|safe 输出点与无 safe_mode 的 Markdown 渲染共同构成存储型 XSS。 |

## C. 阶段记录

- `recon`：已读 settings.py（Django 1.3 风格、DEBUG=True、SECRET_KEY 硬编码、自定义会话/认证）、urls.py、会话存储（pickle+MD5(SECRET_KEY)）、认证后端与密码哈希实现。发现：SECRET_KEY 入库、单轮 SHA1 密码、pickle 会话。
- `hunt`：pattern_scan 共 29 条线索：DEBUG、DB 口令、硬编码 SECRET_KEY、SQL 拼接、弱哈希、pickle 反序列化、开放重定向、os.popen/os.system、文件上传、|safe 模板、csrf_exempt XML-RPC。下一步沿数据流验证。
- `investigate`：已读 XML-RPC 全套（删除/编辑无归属校验、任意用户可删全站 topic、new_media 上传任意内容到 MEDIA_ROOT）、account 认证/注册/重置流程（激活 key 弱熵、反射 XSS、open redirect）。继续读 admin/wiki/bbs/ydata/ylab 视图。
- `verify`：已写 13 条 finding（XSS-001/002、REDIRECT-001、CRYPTO-001/002/003、CSRF-001、CONFIG-001/002、ACCESS-001/002/003、FILE-001），全部 29 条线索已 triage（finding/benign）。

## D. 读过的文件

- `settings.py`
- `urls.py`
- `app/sessions/middleware.py`
- `app/sessions/models.py`
- `app/account/middleware.py`
- `app/account/backends.py`
- `app/account/tokens.py`
- `app/sessions/__init__.py`
- `app/account/models.py`
- `app/sessions/backends/db.py`
- `lib/ylinux_xmlrpc.py`
- `lib/django_xmlrpc/views.py`
- `lib/django_xmlrpc/dispatcher.py`
- `app/account/__init__.py`
- `app/account/views.py`
- `app/admin/views.py`
- `app/account/decorators.py`
- `app/wiki/utils.py`
- `app/wiki/views.py`
- `app/ydata/models.py`
- `app/ydata/util.py`
- `app/ydata/views.py`
- `app/ydata/forms.py`
- `app/ydata/settings.py`
- `app/bbs/views.py`
- `app/ylab/views.py`
- `app/home/views.py`
- `app/ylab/urls.py`
- `app/wiki/urls.py`
- `app/account/urls.py`
- `app/me/views.py`
- `app/account/forms.py`
- `app/admin/forms.py`
- `app/admin/urls.py`
- `app/blog/views.py`
- `app/home/forms.py`
- `app/home/urls.py`
- `app/account/context_processors.py`
- `lib/markdown/__init__.py`
- `app/syndication/views.py`
- `templates/bbs/topic.html`
- `templates/wiki/topic.html`
- `app/sessions/backends/base.py`
- `app/sessions/tests.py`
- `app/me/urls.py`
- `templates/wiki/editPostAJAX.html`
- `templates/wiki/replayAJAX.html`
- `templates/wiki/post.html`
- `scripts/ylinux-client.py`
- `app/home/models.py`
- `app/wiki/models.py`
- `app/bbs/models.py`
- `app/admin/models.py`

## E. 工具调用序列

完整参数和观察见 `trajectory.md` 与 `trace.jsonl`。顺序是模型每次返回的 tool call，不是脚本写死的。前缀 a = 审计员，c = 复核员。

`a:set_stage` → `a:list_files` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:search_code` → `a:list_files` → `a:read_file` → `a:set_stage` → `a:pattern_scan` → `a:set_stage` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:set_stage` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:search_code` → `a:search_code` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:search_code` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:set_stage` → `a:mark_reviewed` → `a:finalize_report` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:search_code` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:search_code` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:search_code` → `c:read_file` → `c:read_file` → `c:read_file` → `c:search_code` → `c:search_code` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:search_code` → `c:list_files` → `c:search_code` → `c:read_file` → `c:read_file` → `c:search_code` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:note_gap` → `c:note_gap` → `c:accept_report` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:upsert_finding` → `a:upsert_finding` → `a:resolve_gap` → `a:resolve_gap` → `a:read_file` → `a:read_file` → `a:search_code` → `a:resolve_gap` → `a:resolve_gap` → `a:finalize_report` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:search_code` → `c:read_file` → `c:read_file` → `c:search_code` → `c:review_finding` → `c:review_finding` → `c:accept_report`

## F. 引用核对

共核对 48 条引用，未通过 0 条。

- 通过 `XSS-001` `app/ydata/forms.py:46-46`
- 通过 `XSS-001` `app/ydata/models.py:258-260`
- 通过 `XSS-001` `app/ydata/models.py:194-200`
- 通过 `XSS-001` `lib/markdown/__init__.py:185-189`
- 通过 `XSS-001` `app/wiki/utils.py:18-18`
- 通过 `XSS-001` `templates/wiki/topic.html:54-54`
- 通过 `XSS-001` `templates/bbs/topic.html:23-23`
- 通过 `XSS-002` `app/account/views.py:100-102`
- 通过 `XSS-002` `app/account/views.py:206-208`
- 通过 `XSS-002` `app/admin/views.py:400-400`
- 通过 `REDIRECT-001` `app/account/views.py:44-44`
- 通过 `REDIRECT-001` `app/account/views.py:38-38`
- 通过 `REDIRECT-001` `app/account/views.py:58-60`
- 通过 `REDIRECT-001` `app/admin/views.py:62-65`
- 通过 `CRYPTO-001` `settings.py:79-79`
- 通过 `CRYPTO-001` `app/sessions/models.py:13-19`
- 通过 `CRYPTO-001` `app/sessions/models.py:62-67`
- 通过 `CRYPTO-001` `app/account/tokens.py:54-54`
- 通过 `CRYPTO-002` `app/account/models.py:63-65`
- 通过 `CRYPTO-002` `app/account/models.py:231-234`
- 通过 `CRYPTO-003` `app/account/models.py:364-367`
- 通过 `CRYPTO-003` `app/account/models.py:427-430`
- 通过 `CRYPTO-003` `app/account/views.py:206-206`
- 通过 `CRYPTO-003` `app/account/views.py:215-219`
- 通过 `CSRF-001` `settings.py:98-104`
- 通过 `CSRF-001` `app/admin/views.py:250-257`
- 通过 `CONFIG-001` `settings.py:18-18`
- 通过 `CONFIG-001` `urls.py:59-63`
- 通过 `CONFIG-002` `settings.py:45-50`
- 通过 `CONFIG-002` `settings.py:29-33`
- 通过 `ACCESS-001` `app/wiki/views.py:447-460`
- 通过 `ACCESS-001` `app/wiki/views.py:271-283`
- 通过 `FILE-001` `app/ydata/views.py:78-84`
- 通过 `FILE-001` `app/ydata/views.py:91-95`
- 通过 `FILE-001` `app/ydata/views.py:140-147`
- 通过 `FILE-001` `lib/ylinux_xmlrpc.py:119-125`
- 通过 `FILE-001` `app/ylab/views.py:31-34`
- 通过 `ACCESS-002` `lib/ylinux_xmlrpc.py:39-45`
- 通过 `ACCESS-002` `lib/ylinux_xmlrpc.py:47-58`
- 通过 `ACCESS-002` `lib/ylinux_xmlrpc.py:60-69`
- 通过 `ACCESS-002` `lib/ylinux_xmlrpc.py:168-185`
- 通过 `ACCESS-002` `settings.py:164-174`
- 通过 `ACCESS-003` `app/ylab/urls.py:8-8`
- 通过 `ACCESS-003` `app/ylab/views.py:37-48`
- 通过 `COOKIE-001` `app/sessions/middleware.py:37-41`
- 通过 `AUTH-001` `app/account/views.py:26-40`
- 通过 `AUTH-001` `app/admin/views.py:51-62`
- 通过 `AUTH-001` `lib/ylinux_xmlrpc.py:39-45`
