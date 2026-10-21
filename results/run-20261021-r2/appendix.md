# ylinux_old 审计附录

## A. 运行统计

- 阅读过的文件：50
- pattern_scan 线索：29（关联发现 18，判为无害 11，重复 0，未处理 0）
- pattern_scan 次数：1；search_code / find_references 次数：20；list_endpoints：用过
- prompt tokens：5379844（缓存命中 5195776）
- completion tokens：75618（其中推理 46773）
- 复核：12 次 review_finding，其中否决 0 次

## B. 扫描线索处置

| 线索 | 规则 | 文件:行 | 处置 | 说明 |
| --- | --- | --- | --- | --- |
| L1 | `debug-true` | `settings.py:18` | finding:CONFIG-001 | DEBUG=True 硬编码且 urls.py 依赖它暴露 /ymedia/ 目录列举。 |
| L2 | `db-password` | `settings.py:49` | finding:CONFIG-002 | DB 口令与 SECRET_KEY 均硬编码提交进公开仓库。 |
| L3 | `secret-key` | `settings.py:79` | finding:CONFIG-002 | DB 口令与 SECRET_KEY 均硬编码提交进公开仓库。 |
| L4 | `sql-statement-format` | `app/account/backends.py:44` | benign | SQL 仅用 %s 拼接经 connection.ops.quote_name 引用的表/列标识符，user_id 经 cursor.execute 参数列表绑定，不构成注入。 |
| L5 | `weak-hash` | `app/account/models.py:63,65,364,367,427,430` | finding:CRYPTO-001 | md5/sha1 单轮口令哈希无迭代；其中 364/367 行的激活 key 弱哈希由 CRYPTO-002 覆盖。 |
| L6 | `insecure-random` | `app/account/models.py:232,364,427` | finding:CRYPTO-002 | random.random() 派生 5 字符盐用于激活/重置 key（232 行的口令盐由 CRYPTO-001 覆盖）。 |
| L7 | `weak-hash` | `app/account/tokens.py:54` | finding:CONFIG-002 | 重置 token 的 SHA1 以已公开的 SECRET_KEY 为输入，密钥泄露后该机制失去保密性。 |
| L8 | `open-redirect` | `app/account/views.py:38,60` | finding:REDIR-001 | logout/login 的 next 与 admin 登录的 Referer 均未校验即作为跳转目标。 |
| L9 | `open-redirect` | `app/admin/views.py:62,134,192,257,354` | finding:REDIR-001 | logout/login 的 next 与 admin 登录的 Referer 均未校验即作为跳转目标。 |
| L10 | `redirect-referer` | `app/admin/views.py:65,134,192,257,354` | finding:REDIR-001 | logout/login 的 next 与 admin 登录的 Referer 均未校验即作为跳转目标。 |
| L11 | `cmd-popen` | `app/admin/views.py:362` | benign | whoami 为固定命令，killall 参数来自 whoami 输出而非请求输入，无命令注入；该端点 GET 触发且无 CSRF 的问题由 CSRF-001 覆盖。 |
| L12 | `cmd-os-system` | `app/admin/views.py:363` | benign | whoami 为固定命令，killall 参数来自 whoami 输出而非请求输入，无命令注入；该端点 GET 触发且无 CSRF 的问题由 CSRF-001 覆盖。 |
| L13 | `http-response-format` | `app/admin/views.py:400,481` | benign | L13 输出的是框架生成的 form.errors/邮件返回码（非攻击者控制的 HTML 原文），且端点为特权接口；L14 为固定 robots 文本。 |
| L14 | `http-response-format` | `app/home/views.py:77` | benign | L13 输出的是框架生成的 form.errors/邮件返回码（非攻击者控制的 HTML 原文），且端点为特权接口；L14 为固定 robots 文本。 |
| L15 | `weak-hash` | `app/sessions/models.py:18,63` | benign | 会话数据 pickle 存于服务端数据库，客户端只有随机会话 key，无法把可控字节送入 pickle.loads；MD5(SECRET_KEY) 校验是服务端完整性检查，密钥泄露影响已记入 CONFIG-002。 |
| L16 | `pickle-load` | `app/sessions/models.py:67` | benign | 会话数据 pickle 存于服务端数据库，客户端只有随机会话 key，无法把可控字节送入 pickle.loads；MD5(SECRET_KEY) 校验是服务端完整性检查，密钥泄露影响已记入 CONFIG-002。 |
| L17 | `weak-hash` | `app/sessions/backends/base.py:89,95,141` | benign | 会话数据 pickle 存于服务端数据库，客户端只有随机会话 key，无法把可控字节送入 pickle.loads；MD5(SECRET_KEY) 校验是服务端完整性检查，密钥泄露影响已记入 CONFIG-002。 |
| L18 | `pickle-load` | `app/sessions/backends/base.py:98` | benign | 会话数据 pickle 存于服务端数据库，客户端只有随机会话 key，无法把可控字节送入 pickle.loads；MD5(SECRET_KEY) 校验是服务端完整性检查，密钥泄露影响已记入 CONFIG-002。 |
| L19 | `template-safe` | `app/wiki/utils.py:18` | finding:XSS-001 | 所有 body_html\|safe 模板 sink 的输出均来自未启用 safe_mode 的 Markdown 转换，原始 HTML 原样保留。 |
| L20 | `upload-handling` | `app/ydata/views.py:40` | finding:FILE-001 | 上传文件名未经清洗拼入保存路径，可 ../ 穿越。 |
| L21 | `weak-hash` | `app/ydata/views.py:52` | benign | L21 的 SHA1 仅用于附件内容去重指纹；L22 输出为 datetime 的 repr 拼接固定脚本，均不含不可信输入。 |
| L22 | `http-response-format` | `app/ylab/views.py:21` | benign | L21 的 SHA1 仅用于附件内容去重指纹；L22 输出为 datetime 的 repr 拼接固定脚本，均不含不可信输入。 |
| L23 | `upload-handling` | `app/ylab/views.py:31` | finding:LAB-001 | /lab/uploadsf 无认证测试上传且把文件名反射进脚本响应。 |
| L24 | `csrf-exempt` | `lib/django_xmlrpc/views.py:50,52,73` | finding:ACL-001 | XML-RPC 入口 csrf_exempt 属该协议正常设计，真正问题是其写方法只做认证不做授权，见 ACL-001。 |
| L25 | `template-safe` | `templates/bbs/topic.html:23,30` | finding:XSS-001 | 所有 body_html\|safe 模板 sink 的输出均来自未启用 safe_mode 的 Markdown 转换，原始 HTML 原样保留。 |
| L26 | `template-safe` | `templates/wiki/editPostAJAX.html:19` | finding:XSS-001 | 所有 body_html\|safe 模板 sink 的输出均来自未启用 safe_mode 的 Markdown 转换，原始 HTML 原样保留。 |
| L27 | `template-safe` | `templates/wiki/post.html:12` | finding:XSS-001 | 所有 body_html\|safe 模板 sink 的输出均来自未启用 safe_mode 的 Markdown 转换，原始 HTML 原样保留。 |
| L28 | `template-safe` | `templates/wiki/replayAJAX.html:16` | finding:XSS-001 | 所有 body_html\|safe 模板 sink 的输出均来自未启用 safe_mode 的 Markdown 转换，原始 HTML 原样保留。 |
| L29 | `template-safe` | `templates/wiki/topic.html:54,59` | finding:XSS-001 | 所有 body_html\|safe 模板 sink 的输出均来自未启用 safe_mode 的 Markdown 转换，原始 HTML 原样保留。 |

## C. 阶段记录

- `recon`：已读 settings.py 与 urls.py：老版 Django（django.conf.urls.defaults），自定义 Session/Auth 中间件，SECRET_KEY、数据库口令硬编码，DEBUG=True，启用 XML-RPC，MEDIA 目录 serve 且 show_indexes=True。下一步列出全部端点。
- `hunt`：已通读核心认证/会话/账号/维基/上传/后台/XML-RPC 代码。运行 pattern_scan 收拢候选线索（XSS、注入、文件、重定向、CSRF、配置等）。
- `investigate`：已读全部 10 个 app 的 views/forms/models/urls、自定义 session/auth 实现、lib/markdown 渲染链路与 lib/django_xmlrpc、ylinux_xmlrpc。确认：markdown safe_mode 缺失导致存储型 XSS、上传文件名路径穿越、XML-RPC 仅认证无授权、editPostAJAX 无属主校验、全站无 CSRF 中间件、注册/重置 key 反射 XSS、logout/next 开放重定向、弱口令哈希、激活码 20bit 熵、DEBUG+目录列举、硬编码 SECRET_KEY/DB 口令、lab 未授权端点。
- `verify`：已写入 12 条 finding（XSS-001/002、FILE-001、ACL-001/002、CSRF-001、REDIR-001、CRYPTO-001/002、CONFIG-001/002、LAB-001），29 条 pattern_scan 线索全部 triage 关闭（finding/benign），无遗留线索。

## D. 读过的文件

- `settings.py`
- `urls.py`
- `app/sessions/middleware.py`
- `app/sessions/models.py`
- `app/account/middleware.py`
- `app/account/backends.py`
- `app/account/tokens.py`
- `app/account/models.py`
- `app/account/views.py`
- `app/account/forms.py`
- `app/account/decorators.py`
- `app/account/urls.py`
- `app/account/__init__.py`
- `app/ydata/util.py`
- `app/ydata/models.py`
- `app/ydata/settings.py`
- `lib/markdown/__init__.py`
- `app/wiki/views.py`
- `app/ydata/forms.py`
- `app/wiki/utils.py`
- `app/wiki/urls.py`
- `templates/wiki/topic.html`
- `app/ydata/views.py`
- `app/ylab/views.py`
- `app/admin/views.py`
- `app/admin/forms.py`
- `app/home/views.py`
- `app/home/forms.py`
- `app/bbs/views.py`
- `app/blog/views.py`
- `app/me/views.py`
- `app/syndication/views.py`
- `lib/django_xmlrpc/views.py`
- `lib/django_xmlrpc/dispatcher.py`
- `lib/django_xmlrpc/decorators.py`
- `lib/ylinux_xmlrpc.py`
- `app/sessions/__init__.py`
- `app/sessions/backends/db.py`
- `app/sessions/backends/base.py`
- `templates/bbs/topic.html`
- `app/account/context_processors.py`
- `templates/me/posts.html`
- `manage.py`
- `app/syndication/feeds.py`
- `app/admin/urls.py`
- `app/ylab/urls.py`
- `app/ydata/urls.py`
- `app/home/urls.py`
- `lib/markdown/postprocessors.py`
- `lib/markdown/preprocessors.py`

## E. 工具调用序列

完整参数和观察见 `trajectory.md` 与 `trace.jsonl`。顺序是模型每次返回的 tool call，不是脚本写死的。前缀 a = 审计员，c = 复核员。

`a:set_stage` → `a:list_files` → `a:read_file` → `a:read_file` → `a:set_stage` → `a:list_endpoints` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:search_code` → `a:read_file` → `a:search_code` → `a:list_files` → `a:read_file` → `a:search_code` → `a:search_code` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:search_code` → `a:list_files` → `a:read_file` → `a:read_file` → `a:search_code` → `a:set_stage` → `a:pattern_scan` → `a:read_file` → `a:read_file` → `a:search_code` → `a:search_code` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:search_code` → `a:read_file` → `a:set_stage` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:set_stage` → `a:finalize_report` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:search_code` → `c:read_file` → `c:read_file` → `c:read_file` → `c:search_code` → `c:search_code` → `c:read_file` → `c:search_code` → `c:search_code` → `c:find_references` → `c:search_code` → `c:search_code` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:search_code` → `c:search_code` → `c:read_file` → `c:read_file` → `c:search_code` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:read_file` → `c:read_file` → `c:read_file` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:accept_report`

## F. 引用核对

共核对 39 条引用，未通过 0 条。

- 通过 `XSS-001` `app/ydata/models.py:198-200`
- 通过 `XSS-001` `app/ydata/models.py:258-260`
- 通过 `XSS-001` `lib/markdown/postprocessors.py:43-55`
- 通过 `XSS-001` `templates/wiki/topic.html:53-55`
- 通过 `XSS-001` `app/wiki/utils.py:17-19`
- 通过 `XSS-001` `app/wiki/views.py:432-436`
- 通过 `FILE-001` `app/ydata/views.py:31-40`
- 通过 `FILE-001` `app/ydata/views.py:78-84`
- 通过 `ACL-001` `lib/ylinux_xmlrpc.py:39-45`
- 通过 `ACL-001` `lib/ylinux_xmlrpc.py:47-58`
- 通过 `ACL-001` `lib/ylinux_xmlrpc.py:60-69`
- 通过 `ACL-001` `lib/ylinux_xmlrpc.py:168-183`
- 通过 `ACL-001` `settings.py:164-174`
- 通过 `CSRF-001` `settings.py:98-104`
- 通过 `CSRF-001` `app/wiki/urls.py:34-38`
- 通过 `CSRF-001` `app/wiki/views.py:237-243`
- 通过 `CSRF-001` `app/admin/views.py:358-365`
- 通过 `ACL-002` `app/wiki/views.py:447-452`
- 通过 `ACL-002` `app/wiki/views.py:456-460`
- 通过 `ACL-002` `app/wiki/views.py:271-278`
- 通过 `XSS-002` `app/account/views.py:96-102`
- 通过 `XSS-002` `app/account/views.py:202-208`
- 通过 `XSS-002` `app/account/urls.py:8-13`
- 通过 `REDIR-001` `app/account/views.py:55-60`
- 通过 `REDIR-001` `app/account/views.py:36-45`
- 通过 `REDIR-001` `app/admin/views.py:62-66`
- 通过 `CRYPTO-001` `app/account/models.py:62-66`
- 通过 `CRYPTO-001` `app/account/models.py:228-234`
- 通过 `CRYPTO-001` `app/account/models.py:241-250`
- 通过 `CRYPTO-002` `app/account/models.py:361-369`
- 通过 `CRYPTO-002` `app/account/models.py:424-430`
- 通过 `CRYPTO-002` `app/account/views.py:205-219`
- 通过 `CONFIG-001` `settings.py:18-20`
- 通过 `CONFIG-001` `urls.py:59-63`
- 通过 `CONFIG-002` `settings.py:42-49`
- 通过 `CONFIG-002` `settings.py:78-79`
- 通过 `LAB-001` `app/ylab/urls.py:5-8`
- 通过 `LAB-001` `app/ylab/views.py:37-48`
- 通过 `LAB-001` `app/ylab/views.py:24-34`
