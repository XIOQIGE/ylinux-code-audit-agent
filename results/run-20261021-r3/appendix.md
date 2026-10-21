# ylinux_old 审计附录

## A. 运行统计

- 阅读过的文件：56
- pattern_scan 线索：29（关联发现 15，判为无害 12，重复 2，未处理 0）
- pattern_scan 次数：1；search_code / find_references 次数：19；list_endpoints：用过
- prompt tokens：7172101（缓存命中 6826496）
- completion tokens：94300（其中推理 54467）
- 复核：16 次 review_finding，其中否决 0 次

## B. 扫描线索处置

| 线索 | 规则 | 文件:行 | 处置 | 说明 |
| --- | --- | --- | --- | --- |
| L1 | `debug-true` | `settings.py:18` | finding:CONFIG-001 | DEBUG=True 提交进仓库并开启 /ymedia/ 目录浏览，见 CONFIG-001 |
| L2 | `db-password` | `settings.py:49` | finding:CONFIG-003 | 数据库弱口令明文提交，见 CONFIG-003 |
| L3 | `secret-key` | `settings.py:79` | finding:CONFIG-002 | SECRET_KEY 硬编码，用于会话签名和密码重置令牌，见 CONFIG-002 |
| L4 | `sql-statement-format` | `app/account/backends.py:44` | benign | backends.py 的 SQL 只用 %s 拼接 quote_name() 处理过的表/列名，用户值通过 cursor.execute(sql, [user_obj.id]) 参数化传入，不存在注入 |
| L5 | `weak-hash` | `app/account/models.py:63,65,364,367,427,430` | finding:CRYPTO-001 | 弱哈希与弱随机盐同属密码存储问题，见 CRYPTO-001 |
| L6 | `insecure-random` | `app/account/models.py:232,364,427` | finding:CRYPTO-001 | 弱哈希与弱随机盐同属密码存储问题，见 CRYPTO-001 |
| L7 | `weak-hash` | `app/account/tokens.py:54` | finding:CONFIG-002 | SECRET_KEY 硬编码，用于会话签名和密码重置令牌，见 CONFIG-002 |
| L8 | `open-redirect` | `app/account/views.py:38,60` | finding:REDIRECT-001 | logout 的 next 参数开放重定向，见 REDIRECT-001 |
| L9 | `open-redirect` | `app/admin/views.py:62,134,192,257,354` | duplicate | admin 视图的 Referer 跳转与 REDIRECT-001 同根因（攻击者可控重定向目标未校验），但仅限已授权管理员，影响更低 |
| L10 | `redirect-referer` | `app/admin/views.py:65,134,192,257,354` | duplicate | admin 视图的 Referer 跳转与 REDIRECT-001 同根因（攻击者可控重定向目标未校验），但仅限已授权管理员，影响更低 |
| L11 | `cmd-popen` | `app/admin/views.py:362` | benign | reboot 视图中 os.popen('whoami')/os.system('killall -u %s') 的命令串不含任何请求参数，whoami 输出是固定服务账户名，非注入；且该视图有 permission_required 保护 |
| L12 | `cmd-os-system` | `app/admin/views.py:363` | benign | reboot 视图中 os.popen('whoami')/os.system('killall -u %s') 的命令串不含任何请求参数，whoami 输出是固定服务账户名，非注入；且该视图有 permission_required 保护 |
| L13 | `http-response-format` | `app/admin/views.py:400,481` | benign | email_to_all 输出的 form.errors 经 Django ErrorList 渲染（该版本对错误消息做条件转义），ret 为 send_mail 返回值（数字），无原始用户输入直接进入响应 HTML |
| L14 | `http-response-format` | `app/home/views.py:77` | benign | robots 视图输出固定字符串，无用户输入 |
| L15 | `weak-hash` | `app/sessions/models.py:18,63` | benign | 会话数据存于数据库（ylinux_session 表），客户端只持有 session_key，pickle.loads 的输入来自 DB 且带 MD5(SECRET_KEY) 校验；未发现任何从请求到会话数据的写路径（无 SQL 注入），无法远程投毒反序列化。SECRET_KEY 泄露的影响单独记录在 CONFIG-002 |
| L16 | `pickle-load` | `app/sessions/models.py:67` | benign | 会话数据存于数据库（ylinux_session 表），客户端只持有 session_key，pickle.loads 的输入来自 DB 且带 MD5(SECRET_KEY) 校验；未发现任何从请求到会话数据的写路径（无 SQL 注入），无法远程投毒反序列化。SECRET_KEY 泄露的影响单独记录在 CONFIG-002 |
| L17 | `weak-hash` | `app/sessions/backends/base.py:89,95,141` | benign | 会话数据存于数据库（ylinux_session 表），客户端只持有 session_key，pickle.loads 的输入来自 DB 且带 MD5(SECRET_KEY) 校验；未发现任何从请求到会话数据的写路径（无 SQL 注入），无法远程投毒反序列化。SECRET_KEY 泄露的影响单独记录在 CONFIG-002 |
| L18 | `pickle-load` | `app/sessions/backends/base.py:98` | benign | 会话数据存于数据库（ylinux_session 表），客户端只持有 session_key，pickle.loads 的输入来自 DB 且带 MD5(SECRET_KEY) 校验；未发现任何从请求到会话数据的写路径（无 SQL 注入），无法远程投毒反序列化。SECRET_KEY 泄露的影响单独记录在 CONFIG-002 |
| L19 | `template-safe` | `app/wiki/utils.py:18` | finding:XSS-001 | 所有 \|safe 渲染 body_html 的模板汇聚到存储型 XSS 发现 XSS-001 |
| L20 | `upload-handling` | `app/ydata/views.py:40` | finding:FILE-001 | 上传文件名拼接路径导致穿越写入，见 FILE-001 |
| L21 | `weak-hash` | `app/ydata/views.py:52` | benign | sha1 仅用于附件去重（按内容哈希比较），不承担安全职能，不是漏洞 |
| L22 | `http-response-format` | `app/ylab/views.py:21` | benign | ylab time 视图回显的是服务器当前时间 repr（反引号），不含请求输入，非 XSS |
| L23 | `upload-handling` | `app/ylab/views.py:31` | finding:XSS-003 | ylab 上传视图把文件名未转义嵌入响应脚本，见 XSS-003 |
| L24 | `csrf-exempt` | `lib/django_xmlrpc/views.py:50,52,73` | benign | /xmlrpc/ 的 csrf_exempt 合理：XML-RPC 客户端凭据在每次调用中传递，不依赖会话 Cookie，豁免 CSRF 不会带来跨站伪造风险；该接口的鉴权缺失另记录在 ACCESS-002 |
| L25 | `template-safe` | `templates/bbs/topic.html:23,30` | finding:XSS-001 | 所有 \|safe 渲染 body_html 的模板汇聚到存储型 XSS 发现 XSS-001 |
| L26 | `template-safe` | `templates/wiki/editPostAJAX.html:19` | finding:XSS-001 | 所有 \|safe 渲染 body_html 的模板汇聚到存储型 XSS 发现 XSS-001 |
| L27 | `template-safe` | `templates/wiki/post.html:12` | finding:XSS-001 | 所有 \|safe 渲染 body_html 的模板汇聚到存储型 XSS 发现 XSS-001 |
| L28 | `template-safe` | `templates/wiki/replayAJAX.html:16` | finding:XSS-001 | 所有 \|safe 渲染 body_html 的模板汇聚到存储型 XSS 发现 XSS-001 |
| L29 | `template-safe` | `templates/wiki/topic.html:54,59` | finding:XSS-001 | 所有 \|safe 渲染 body_html 的模板汇聚到存储型 XSS 发现 XSS-001 |

## C. 阶段记录

- `recon`：已读 settings.py/urls.py：旧版 Django（django.conf.urls.defaults），DEBUG=True，硬编码 SECRET_KEY，自定义 session/auth 中间件，XML-RPC 接口
- `hunt`：已读 settings、会话/认证中间件与后端、XML-RPC 库、account/wiki/ydata/admin/home/bbs/blog/me/ylab 视图和模型。发现候选：无 CSRF 中间件、markdown 无 safe_mode 的 |safe 渲染、上传文件名路径穿越、XML-RPC 越权删除、logout 开放重定向、激活 key 反射 XSS
- `investigate`：已读全部 views.py（home/admin/account/wiki/ydata/bbs/blog/me/ylab/syndication/xmlrpc）、会话与认证实现、ydata 模型与 forms、markdown 2.0.3 库源码。确认数据流：回复/主题正文 → Markdown 无 safe_mode 转换 → |safe 渲染；上传文件名 → 路径拼接与 JS 响应；激活 key → 未转义 HTML
- `verify`：已写入 13 条 finding（XSS-001/002/003、FILE-001、ACCESS-001/002/003、CSRF-001、REDIRECT-001、CONFIG-001/002/003、CRYPTO-001、SENSITIVE-001），pattern_scan 全部 29 条线索已 triage 关闭，证据引用与行号已核对

## D. 读过的文件

- `settings.py`
- `urls.py`
- `app/sessions/middleware.py`
- `app/account/middleware.py`
- `lib/ylinux_xmlrpc.py`
- `app/sessions/models.py`
- `app/sessions/backends/db.py`
- `app/sessions/backends/base.py`
- `app/account/views.py`
- `app/account/tokens.py`
- `app/account/models.py`
- `app/account/forms.py`
- `app/account/__init__.py`
- `app/account/backends.py`
- `app/account/decorators.py`
- `app/ydata/util.py`
- `app/wiki/views.py`
- `app/ydata/views.py`
- `app/wiki/utils.py`
- `app/ydata/models.py`
- `app/ydata/forms.py`
- `templates/wiki/topic.html`
- `lib/markdown/__init__.py`
- `lib/markdown/postprocessors.py`
- `app/admin/views.py`
- `app/ylab/views.py`
- `app/home/views.py`
- `app/ydata/settings.py`
- `app/bbs/views.py`
- `app/blog/views.py`
- `app/me/views.py`
- `app/syndication/views.py`
- `lib/django_xmlrpc/views.py`
- `lib/django_xmlrpc/dispatcher.py`
- `app/account/urls.py`
- `app/home/forms.py`
- `app/admin/forms.py`
- `scripts/.htaccess`
- `app/account/context_processors.py`
- `templates/bbs/topic.html`
- `lib/django_xmlrpc/decorators.py`
- `scripts/ylinux-client.py`
- `manage.py`
- `templates/wiki/replayAJAX.html`
- `templates/wiki/editPostAJAX.html`
- `templates/wiki/post.html`
- `app/me/models.py`
- `app/wiki/urls.py`
- `app/ydata/urls.py`
- `app/admin/urls.py`
- `app/home/urls.py`
- `app/syndication/feeds.py`
- `app/bbs/urls.py`
- `app/blog/urls.py`
- `app/me/urls.py`
- `app/ylab/urls.py`

## E. 工具调用序列

完整参数和返回见 `trajectory.md` 和 `trace.jsonl`。顺序就是模型每次返回的 tool call，代码里没有预设。a = 审计员，c = 复核员。

`a:set_stage` → `a:list_files` → `a:read_file` → `a:read_file` → `a:set_stage` → `a:list_endpoints` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:find_references` → `a:find_references` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:search_code` → `a:read_file` → `a:search_code` → `a:search_code` → `a:read_file` → `a:list_files` → `a:search_code` → `a:list_files` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:search_code` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:set_stage` → `a:pattern_scan` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:set_stage` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:set_stage` → `a:mark_reviewed` → `a:mark_reviewed` → `a:mark_reviewed` → `a:finalize_report` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:search_code` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:search_code` → `c:read_file` → `c:search_code` → `c:search_code` → `c:search_code` → `c:read_file` → `c:read_file` → `c:read_file` → `c:search_code` → `c:search_code` → `c:search_code` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:search_code` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:search_code` → `c:read_file` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:note_gap` → `c:note_gap` → `c:accept_report` → `a:read_file` → `a:read_file` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:resolve_gap` → `a:resolve_gap` → `a:search_code` → `a:read_file` → `a:read_file` → `a:resolve_gap` → `a:resolve_gap` → `a:finalize_report` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:search_code` → `c:read_file` → `c:read_file` → `c:read_file` → `c:review_finding` → `c:review_finding` → `c:accept_report`

## F. 引用核对

共核对 46 条引用，未通过 0 条。

- 通过 `XSS-001` `app/wiki/views.py:432-436`
- 通过 `XSS-001` `app/ydata/models.py:258-260`
- 通过 `XSS-001` `app/ydata/models.py:198-200`
- 通过 `XSS-001` `lib/markdown/postprocessors.py:54-57`
- 通过 `XSS-001` `templates/wiki/topic.html:53-60`
- 通过 `XSS-001` `app/wiki/utils.py:17-19`
- 通过 `XSS-001` `templates/bbs/topic.html:22-31`
- 通过 `XSS-002` `app/account/urls.py:8-13`
- 通过 `XSS-002` `app/account/views.py:96-102`
- 通过 `XSS-002` `app/account/views.py:202-208`
- 通过 `XSS-003` `app/ydata/views.py:91-95`
- 通过 `XSS-003` `app/ylab/views.py:30-34`
- 通过 `FILE-001` `app/ydata/views.py:40-41`
- 通过 `FILE-001` `app/ydata/views.py:77-84`
- 通过 `FILE-001` `app/ydata/models.py:373-375`
- 通过 `ACCESS-001` `app/wiki/views.py:447-460`
- 通过 `ACCESS-001` `app/wiki/views.py:213-218`
- 通过 `ACCESS-002` `lib/ylinux_xmlrpc.py:39-45`
- 通过 `ACCESS-002` `lib/ylinux_xmlrpc.py:60-69`
- 通过 `ACCESS-002` `lib/ylinux_xmlrpc.py:173-181`
- 通过 `ACCESS-002` `settings.py:164-171`
- 通过 `CSRF-001` `settings.py:98-104`
- 通过 `CSRF-001` `app/admin/views.py:250-257`
- 通过 `CSRF-001` `app/wiki/views.py:237-250`
- 通过 `REDIRECT-001` `app/account/views.py:55-60`
- 通过 `REDIRECT-001` `app/account/views.py:42-45`
- 通过 `REDIRECT-001` `app/account/views.py:36-38`
- 通过 `ACCESS-003` `app/ylab/views.py:37-48`
- 通过 `ACCESS-003` `app/ylab/urls.py:6-8`
- 通过 `CONFIG-001` `settings.py:18-19`
- 通过 `CONFIG-001` `urls.py:59-63`
- 通过 `CONFIG-002` `settings.py:78-79`
- 通过 `CONFIG-002` `app/account/tokens.py:53-57`
- 通过 `CONFIG-002` `app/sessions/models.py:13-19`
- 通过 `CRYPTO-001` `app/account/models.py:62-66`
- 通过 `CRYPTO-001` `app/account/models.py:228-234`
- 通过 `SENSITIVE-001` `app/admin/forms.py:84-91`
- 通过 `SENSITIVE-001` `app/admin/forms.py:108-116`
- 通过 `CONFIG-003` `settings.py:42-49`
- 通过 `CONFIG-003` `settings.py:29-34`
- 通过 `CRYPTO-002` `app/account/models.py:361-369`
- 通过 `CRYPTO-002` `app/account/models.py:424-430`
- 通过 `CRYPTO-002` `app/account/views.py:205-219`
- 通过 `FILE-002` `app/ydata/views.py:77-90`
- 通过 `FILE-002` `settings.py:74-75`
- 通过 `FILE-002` `urls.py:59-63`
