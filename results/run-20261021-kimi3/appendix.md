# ylinux_old 审计附录

## A. 运行统计

- 阅读过的文件：59
- pattern_scan 线索：29（关联发现 21，判为无害 8，重复 0，未处理 0）
- pattern_scan 次数：1；search_code / find_references 次数：7；list_endpoints：用过
- prompt tokens：6009998（缓存命中 5829888）
- completion tokens：73569（其中推理 43382）
- 复核：9 次 review_finding，其中否决 2 次

## B. 扫描线索处置

| 线索 | 规则 | 文件:行 | 处置 | 说明 |
| --- | --- | --- | --- | --- |
| L1 | `debug-true` | `settings.py:18` | finding:CONFIG-001 | DEBUG=True 且 urls.py 在 DEBUG 下开放 ymedia 目录浏览。 |
| L2 | `db-password` | `settings.py:49` | finding:CONFIG-003 | 数据库口令 123456 提交进仓库，sqlite 引擎下暂不生效。 |
| L3 | `secret-key` | `settings.py:79` | finding:CONFIG-002 | SECRET_KEY 硬编码公开，用于会话签名（SESSION-001 一并引用）。 |
| L4 | `sql-statement-format` | `app/account/backends.py:44` | benign | SQL 标识符经 connection.ops.quote_name 引用，用户 id 走 cursor.execute 的参数列表（%%s + [user_obj.id]），不是注入。 |
| L5 | `weak-hash` | `app/account/models.py:63,65,364,367,427,430` | finding:CRYPTO-001 | get_hexdigest 为单轮 md5/sha1，无迭代成本。 |
| L6 | `insecure-random` | `app/account/models.py:232,364,427` | finding:CRYPTO-001 | 232 行口令盐由 random.random() 派生 5 字符盐（CRYPTO-001）；364/427 行令牌盐见 CRYPTO-002。 |
| L7 | `weak-hash` | `app/account/tokens.py:54` | benign | account/tokens.py 的 default_token_generator 是标准 Django 模式且实际密码重置流程不使用它（用 Register.activation_key），属死代码。 |
| L8 | `open-redirect` | `app/account/views.py:38,60` | finding:REDIRECT-001 | login/logout 的 next 与 admin 的 previous_url/HTTP_REFERER 直接作为重定向目标。 |
| L9 | `open-redirect` | `app/admin/views.py:62,134,192,257,354` | finding:REDIRECT-001 | login/logout 的 next 与 admin 的 previous_url/HTTP_REFERER 直接作为重定向目标。 |
| L10 | `redirect-referer` | `app/admin/views.py:65,134,192,257,354` | finding:REDIRECT-001 | login/logout 的 next 与 admin 的 previous_url/HTTP_REFERER 直接作为重定向目标。 |
| L11 | `cmd-popen` | `app/admin/views.py:362` | benign | os.system 的参数来自 whoami 输出（服务器用户名），非请求输入，且视图受 permission_required 保护，不构成命令注入。 |
| L12 | `cmd-os-system` | `app/admin/views.py:363` | benign | os.system 的参数来自 whoami 输出（服务器用户名），非请求输入，且视图受 permission_required 保护，不构成命令注入。 |
| L13 | `http-response-format` | `app/admin/views.py:400,481` | benign | admin 的 form.errors 是 Django 生成的固定错误文案不回声用户原始值，ret 是邮件发送数；robots 为静态文案；ylab time 输出服务器时间戳。均无攻击者可控内容。 |
| L14 | `http-response-format` | `app/home/views.py:77` | benign | admin 的 form.errors 是 Django 生成的固定错误文案不回声用户原始值，ret 是邮件发送数；robots 为静态文案；ylab time 输出服务器时间戳。均无攻击者可控内容。 |
| L15 | `weak-hash` | `app/sessions/models.py:18,63` | finding:SESSION-001 | 会话编码/解码使用 pickle + MD5(SECRET_KEY) 校验，密钥已公开。 |
| L16 | `pickle-load` | `app/sessions/models.py:67` | finding:SESSION-001 | 会话编码/解码使用 pickle + MD5(SECRET_KEY) 校验，密钥已公开。 |
| L17 | `weak-hash` | `app/sessions/backends/base.py:89,95,141` | finding:SESSION-001 | 会话编码/解码使用 pickle + MD5(SECRET_KEY) 校验，密钥已公开。 |
| L18 | `pickle-load` | `app/sessions/backends/base.py:98` | finding:SESSION-001 | 会话编码/解码使用 pickle + MD5(SECRET_KEY) 校验，密钥已公开。 |
| L19 | `template-safe` | `app/wiki/utils.py:18` | finding:XSS-002 | post.body_html 经 \|safe 输出，markup='none' 渲染无 safe_mode。 |
| L20 | `upload-handling` | `app/ydata/views.py:40` | finding:FILE-001 | 上传文件名直接拼接路径写盘，存在穿越。 |
| L21 | `weak-hash` | `app/ydata/views.py:52` | benign | sha1 仅用于附件内容去重比对，不参与安全决策。 |
| L22 | `http-response-format` | `app/ylab/views.py:21` | benign | admin 的 form.errors 是 Django 生成的固定错误文案不回声用户原始值，ret 是邮件发送数；robots 为静态文案；ylab time 输出服务器时间戳。均无攻击者可控内容。 |
| L23 | `upload-handling` | `app/ylab/views.py:31` | finding:XSS-004 | ylab 上传端点把文件名未转义拼入 JS 响应，匿名可达。 |
| L24 | `csrf-exempt` | `lib/django_xmlrpc/views.py:50,52,73` | finding:CSRF-001 | 全站未启用 CSRF 中间件，xmlrpc 的 csrf_exempt 只是装饰；真正的缺口是 MIDDLEWARE_CLASSES 里没有任何 CSRF 防护。 |
| L25 | `template-safe` | `templates/bbs/topic.html:23,30` | finding:XSS-001 | topic.body_html\|safe（L25 第 23 行、L29 第 54 行）；L25 第 30 行与 L29 第 59 行的 post body 输出归入 XSS-002。 |
| L26 | `template-safe` | `templates/wiki/editPostAJAX.html:19` | finding:XSS-002 | post.body_html 经 \|safe 输出，markup='none' 渲染无 safe_mode。 |
| L27 | `template-safe` | `templates/wiki/post.html:12` | finding:XSS-002 | post.body_html 经 \|safe 输出，markup='none' 渲染无 safe_mode。 |
| L28 | `template-safe` | `templates/wiki/replayAJAX.html:16` | finding:XSS-002 | post.body_html 经 \|safe 输出，markup='none' 渲染无 safe_mode。 |
| L29 | `template-safe` | `templates/wiki/topic.html:54,59` | finding:XSS-001 | topic.body_html\|safe（L25 第 23 行、L29 第 54 行）；L25 第 30 行与 L29 第 59 行的 post body 输出归入 XSS-002。 |

## C. 阶段记录

- `recon`：老式 Django 项目（django.conf.urls.defaults），自定义 session/auth 中间件，XML-RPC 暴露在 /xmlrpc/，DEBUG=True、硬编码 SECRET_KEY。已用 list_endpoints 映射 104 个路由。接下来读 session 存储、认证后端和 XML-RPC。
- `investigate`：已读 session 存储（cPickle+MD5(SECRET_KEY)）、认证后端（无迭代 SHA1 口令）、注册/重置令牌（20bit 熵）、XML-RPC、wiki/ydata/ylab/home/bbs/blog/me/admin 视图。发现多个 XSS/上传/越权线索，待 pattern_scan 系统化核对。
- `verify`：已写入 17 条 finding 并关闭全部 29 条 pattern_scan 线索（finding/benign）。确认了存储型 XSS（主题/回复）、匿名反射 XSS、上传路径穿越、XML-RPC 授权缺失、越权编辑、CSRF 全局缺失、弱口令哈希与弱令牌、公开密钥、开放重定向等。
- `hunt`：hunt 阶段：运行了 pattern_scan（29 条线索）+ 多次 search_code（|safe、SESSION_ENGINE、bbmarkup、ylinux_text_filter、safe_mode），并逐一读取上下文核对，全部线索已 triage 关闭。

## D. 读过的文件

- `settings.py`
- `urls.py`
- `app/sessions/middleware.py`
- `app/account/middleware.py`
- `app/sessions/models.py`
- `__init__.py`
- `app/ydata/settings.py`
- `app/sessions/__init__.py`
- `app/sessions/backends/db.py`
- `app/sessions/backends/base.py`
- `lib/ylinux_xmlrpc.py`
- `lib/django_xmlrpc/views.py`
- `lib/django_xmlrpc/dispatcher.py`
- `app/account/views.py`
- `app/account/tokens.py`
- `app/account/backends.py`
- `app/account/models.py`
- `app/account/__init__.py`
- `app/account/forms.py`
- `app/account/decorators.py`
- `app/wiki/views.py`
- `app/wiki/utils.py`
- `app/ydata/util.py`
- `app/ydata/models.py`
- `app/ydata/forms.py`
- `app/ydata/views.py`
- `app/home/views.py`
- `app/ylab/views.py`
- `app/admin/views.py`
- `app/bbs/views.py`
- `app/blog/views.py`
- `app/me/views.py`
- `templates/wiki/topic.html`
- `lib/markdown/preprocessors.py`
- `app/syndication/views.py`
- `app/syndication/feeds.py`
- `app/home/forms.py`
- `app/account/urls.py`
- `app/wiki/urls.py`
- `app/ylab/urls.py`
- `app/account/context_processors.py`
- `app/admin/forms.py`
- `app/home/urls.py`
- `app/ydata/urls.py`
- `README`
- `scripts/.htaccess`
- `scripts/ylinux.fcgi`
- `templates/bbs/topic.html`
- `templates/wiki/post.html`
- `templates/wiki/editPostAJAX.html`
- `templates/wiki/replayAJAX.html`
- `lib/django_xmlrpc/decorators.py`
- `lib/django_xmlrpc/__init__.py`
- `lib/markdown/__init__.py`
- `templates/wiki/ajax_show_update.html`
- `app/bbs/urls.py`
- `app/blog/urls.py`
- `app/me/urls.py`
- `app/admin/urls.py`

## E. 工具调用序列

完整参数和返回见 `trajectory.md` 和 `trace.jsonl`。顺序就是模型每次返回的 tool call，代码里没有预设。a = 审计员，c = 复核员。

`a:set_stage` → `a:list_files` → `a:read_file` → `a:read_file` → `a:list_endpoints` → `a:read_file` → `a:read_file` → `a:set_stage` → `a:read_file` → `a:search_code` → `a:list_files` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:search_code` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:search_code` → `a:read_file` → `a:list_files` → `a:search_code` → `a:read_file` → `a:search_code` → `a:read_file` → `a:read_file` → `a:read_file` → `a:set_stage` → `a:pattern_scan` → `a:search_code` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:set_stage` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:mark_reviewed` → `a:mark_reviewed` → `a:mark_reviewed` → `a:finalize_report` → `a:set_stage` → `a:finalize_report` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:list_files` → `c:read_file` → `c:read_file` → `c:search_code` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:read_file` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:read_file` → `c:read_file` → `c:read_file`

## F. 引用核对

共核对 38 条引用，未通过 0 条。

- 通过 `XSS-001` `app/ydata/models.py:190-200`
- 通过 `XSS-001` `lib/markdown/__init__.py:185-189`
- 通过 `XSS-001` `templates/wiki/topic.html:54-54`
- 通过 `XSS-001` `templates/bbs/topic.html:23-23`
- 通过 `XSS-002` `app/wiki/views.py:432-435`
- 通过 `XSS-002` `app/ydata/models.py:258-260`
- 通过 `XSS-002` `app/wiki/utils.py:18-18`
- 通过 `XSS-002` `templates/bbs/topic.html:30-30`
- 通过 `XSS-003` `app/account/views.py:96-102`
- 通过 `XSS-003` `app/account/views.py:205-208`
- 通过 `XSS-004` `app/ylab/views.py:24-34`
- 通过 `FILE-001` `app/ydata/views.py:78-84`
- 通过 `FILE-001` `app/ydata/views.py:125-132`
- 通过 `FILE-001` `lib/ylinux_xmlrpc.py:119-124`
- 通过 `XSS-005` `app/ydata/models.py:407-408`
- 通过 `XSS-005` `app/ydata/models.py:443-444`
- 通过 `ACCESS-001` `app/wiki/views.py:447-451`
- 通过 `ACCESS-001` `app/wiki/views.py:456-460`
- 通过 `ACCESS-002` `lib/ylinux_xmlrpc.py:39-45`
- 通过 `ACCESS-002` `lib/ylinux_xmlrpc.py:60-69`
- 通过 `ACCESS-002` `lib/ylinux_xmlrpc.py:168-176`
- 通过 `ACCESS-003` `app/ylab/views.py:37-48`
- 通过 `ACCESS-003` `app/ylab/urls.py:8-8`
- 通过 `CSRF-001` `settings.py:98-104`
- 通过 `CRYPTO-001` `app/account/models.py:62-66`
- 通过 `CRYPTO-001` `app/account/models.py:228-234`
- 通过 `CRYPTO-002` `app/account/models.py:361-369`
- 通过 `CRYPTO-002` `app/account/models.py:424-430`
- 通过 `CRYPTO-002` `app/account/views.py:205-219`
- 通过 `SESSION-001` `app/sessions/backends/base.py:86-102`
- 通过 `SESSION-001` `settings.py:79-79`
- 通过 `CONFIG-001` `settings.py:18-19`
- 通过 `CONFIG-001` `urls.py:59-63`
- 通过 `CONFIG-002` `settings.py:79-79`
- 通过 `CONFIG-003` `settings.py:42-52`
- 通过 `REDIRECT-001` `app/account/views.py:42-44`
- 通过 `REDIRECT-001` `app/account/views.py:55-60`
- 通过 `REDIRECT-001` `app/admin/views.py:62-65`
