# ylinux_old 审计附录

## A. 运行统计

- 阅读过的文件：61
- pattern_scan 线索：29（关联发现 18，判为无害 10，重复 1，未处理 0）
- pattern_scan 次数：1；search_code / find_references 次数：23；list_endpoints：用过
- prompt tokens：7390085（缓存命中 6980352）
- completion tokens：106777（其中推理 62809）
- 复核：21 次 review_finding，其中否决 2 次

## B. 扫描线索处置

| 线索 | 规则 | 文件:行 | 处置 | 说明 |
| --- | --- | --- | --- | --- |
| L1 | `debug-true` | `settings.py:18` | finding:CONFIG-001 | DEBUG=True 随仓库提交并导致 /ymedia/ 以 show_indexes 静态服务 |
| L2 | `db-password` | `settings.py:49` | finding:CONFIG-003 | 数据库口令 123456 提交进仓库 |
| L3 | `secret-key` | `settings.py:79` | finding:CONFIG-002 | SECRET_KEY 硬编码且用于 MD5 会话签名 |
| L4 | `sql-statement-format` | `app/account/backends.py:44` | benign | backends.get_group_permissions 的 SQL 全部标识符经 connection.ops.quote_name 引用，用户值走 cursor.execute(sql, [user_obj.id]) 参数列表，不是字符串拼接注入 |
| L5 | `weak-hash` | `app/account/models.py:63,65,364,367,427,430` | finding:CRYPTO-002 | 单轮 MD5/SHA1 口令哈希（models.py:63,65），364/367 的弱盐问题另见 CRYPTO-001 |
| L6 | `insecure-random` | `app/account/models.py:232,364,427` | finding:CRYPTO-001 | random.random() 派生的 5 字符盐用于激活/重置密钥，20 位熵可枚举；232 行口令盐已由 CRYPTO-002 覆盖 |
| L7 | `weak-hash` | `app/account/tokens.py:54` | benign | tokens.py 的 default_token_generator 只被 forms.PasswordResetForm.save 的默认参数引用，该 Form 未被任何视图实例化调用（find_references 确认），实际重置流程走 Register.activation_key（已由 CRYPTO-001 记录） |
| L8 | `open-redirect` | `app/account/views.py:38,60` | finding:REDIRECT-001 | login/logout 的 next 参数直接作为重定向目标 |
| L9 | `open-redirect` | `app/admin/views.py:62,134,192,257,354` | benign | admin 视图的跳转目标取自 HTTP_REFERER（仅受害者自己浏览器会携带，攻击者不能为受害者设置），且这些端点都有 permission_required；真正的风险是这些端点 GET 即触发写操作，已由 CSRF-001 覆盖 |
| L10 | `redirect-referer` | `app/admin/views.py:65,134,192,257,354` | duplicate | 与 L9 同源（admin/views.py 同一批 HTTP_REFERER 行），结论相同 |
| L11 | `cmd-popen` | `app/admin/views.py:362` | benign | reboot 端点的命令参数来自 os.popen('whoami') 的固定系统输出，非用户输入；该端点是 permission_required 保护下有意设计的“重启 fastcgi”维护动作，不构成命令注入 |
| L12 | `cmd-os-system` | `app/admin/views.py:363` | benign | reboot 端点的命令参数来自 os.popen('whoami') 的固定系统输出，非用户输入；该端点是 permission_required 保护下有意设计的“重启 fastcgi”维护动作，不构成命令注入 |
| L13 | `http-response-format` | `app/admin/views.py:400,481` | benign | L13：form.errors 中这些字段的校验消息为固定文本，不回显用户输入，且端点有 permission_required。L14：robots 响应是固定字符串 |
| L14 | `http-response-format` | `app/home/views.py:77` | benign | L13：form.errors 中这些字段的校验消息为固定文本，不回显用户输入，且端点有 permission_required。L14：robots 响应是固定字符串 |
| L15 | `weak-hash` | `app/sessions/models.py:18,63` | finding:CONFIG-002 | SECRET_KEY 硬编码且用于 MD5 会话签名 |
| L16 | `pickle-load` | `app/sessions/models.py:67` | finding:DESER-001 | 会话 pickle 反序列化依赖 MD5+公开 SECRET_KEY 签名 |
| L17 | `weak-hash` | `app/sessions/backends/base.py:89,95,141` | finding:DESER-001 | 会话 pickle 反序列化依赖 MD5+公开 SECRET_KEY 签名 |
| L18 | `pickle-load` | `app/sessions/backends/base.py:98` | finding:DESER-001 | 会话 pickle 反序列化依赖 MD5+公开 SECRET_KEY 签名 |
| L19 | `template-safe` | `app/wiki/utils.py:18` | finding:XSS-001 | body_html 由无 safe_mode 的 Markdown 生成后经 \|safe 输出的存储型 XSS（Post/Topic 两条链路） |
| L20 | `upload-handling` | `app/ydata/views.py:40` | finding:FILE-001 | ydata 上传接口将用户文件名直接拼入磁盘保存路径且自身无穿越防护，是否可利用取决于运行时 Django 对 UploadedFile.name 的清洗 |
| L21 | `weak-hash` | `app/ydata/views.py:52` | benign | SHA1 仅用于附件内容去重哈希，不参与认证或完整性保护 |
| L22 | `http-response-format` | `app/ylab/views.py:21` | benign | `current` 是 datetime 对象的固定 repr，非用户输入 |
| L23 | `upload-handling` | `app/ylab/views.py:31` | finding:XSS-004 | ylab 上传接口把文件名未转义拼进响应 HTML/JS（self-XSS），ydata 同源问题一并记录在该 finding |
| L24 | `csrf-exempt` | `lib/django_xmlrpc/views.py:50,52,73` | benign | XML-RPC 端点逐请求携带用户名密码、不依赖 Cookie 会话，csrf_exempt 合理；全站缺少 CSRF 的问题已由 CSRF-001 记录 |
| L25 | `template-safe` | `templates/bbs/topic.html:23,30` | finding:XSS-001 | body_html 由无 safe_mode 的 Markdown 生成后经 \|safe 输出的存储型 XSS（Post/Topic 两条链路） |
| L26 | `template-safe` | `templates/wiki/editPostAJAX.html:19` | finding:XSS-001 | body_html 由无 safe_mode 的 Markdown 生成后经 \|safe 输出的存储型 XSS（Post/Topic 两条链路） |
| L27 | `template-safe` | `templates/wiki/post.html:12` | finding:XSS-001 | body_html 由无 safe_mode 的 Markdown 生成后经 \|safe 输出的存储型 XSS（Post/Topic 两条链路） |
| L28 | `template-safe` | `templates/wiki/replayAJAX.html:16` | finding:XSS-001 | body_html 由无 safe_mode 的 Markdown 生成后经 \|safe 输出的存储型 XSS（Post/Topic 两条链路） |
| L29 | `template-safe` | `templates/wiki/topic.html:54,59` | finding:XSS-001 | body_html 由无 safe_mode 的 Markdown 生成后经 \|safe 输出的存储型 XSS（Post/Topic 两条链路） |

## C. 阶段记录

- `recon`：Django 1.3 时代项目：自定义会话/认证中间件、XML-RPC、DEBUG=True、硬编码 SECRET_KEY。已用 list_endpoints 标出 104 个端点，33 个待查（多处 writes_on_any_method、csrf_exempt、无鉴权写入）
- `hunt`：已读完 settings/urls/sessions/account/XML-RPC 等核心文件。确认：MD5+SECRET_KEY 签名 pickle 会话、20bit 激活码、markdown 无 safe_mode 的 body_html、XML-RPC 任意删帖、无 CSRF 中间件。用 pattern_scan 查漏
- `investigate`：沿数据流读完 account/views/models/forms/tokens、sessions 全部后端、wiki/ydata/ylab/me/bbs/blog/home/admin 视图与表单、XML-RPC 层、markdown 库 safe_mode 行为、关键模板 |safe 落点；确认多条可达漏洞链
- `verify`：已写入 16 条 finding（4 XSS、2 access_control、1 CSRF、2 crypto、3 config、1 file、1 redirect、1 email、1 deserialization 待复核），29 条 pattern_scan 线索全部关闭

## D. 读过的文件

- `settings.py`
- `urls.py`
- `app/sessions/middleware.py`
- `app/account/middleware.py`
- `app/sessions/models.py`
- `app/ydata/settings.py`
- `app/account/tokens.py`
- `app/account/backends.py`
- `app/account/views.py`
- `app/account/models.py`
- `app/wiki/views.py`
- `app/wiki/utils.py`
- `app/ydata/models.py`
- `app/ydata/util.py`
- `app/ydata/forms.py`
- `app/ydata/views.py`
- `app/ylab/views.py`
- `app/account/decorators.py`
- `app/account/__init__.py`
- `app/admin/views.py`
- `lib/django_xmlrpc/views.py`
- `lib/django_xmlrpc/dispatcher.py`
- `lib/ylinux_xmlrpc.py`
- `app/bbs/views.py`
- `app/home/views.py`
- `app/blog/views.py`
- `app/account/forms.py`
- `app/me/views.py`
- `lib/django_xmlrpc/decorators.py`
- `lib/markdown/inlinepatterns.py`
- `lib/markdown/__init__.py`
- `app/sessions/backends/base.py`
- `app/sessions/backends/db.py`
- `app/sessions/backends/cached_db.py`
- `manage.py`
- `scripts/ylinux.fcgi`
- `app/home/forms.py`
- `app/syndication/feeds.py`
- `app/syndication/views.py`
- `app/wiki/urls.py`
- `templates/ydata/attachment.html`
- `templates/wiki/topic.html`
- `app/account/urls.py`
- `app/account/context_processors.py`
- `app/ydata/urls.py`
- `app/ylab/urls.py`
- `app/me/urls.py`
- `app/admin/urls.py`
- `app/sessions/backends/file.py`
- `app/sessions/backends/cache.py`
- `app/admin/forms.py`
- `templates/account/user.html`
- `lib/django_xmlrpc/__init__.py`
- `templates/me/index.html`
- `templates/account/index.html`
- `templates/wiki/ajax_add_topic.html`
- `app/home/urls.py`
- `app/bbs/urls.py`
- `app/blog/urls.py`
- `templates/xmlrpc_get.html`
- `scripts/ylinux-client.py`

## E. 工具调用序列

完整参数和观察见 `trajectory.md` 与 `trace.jsonl`。顺序是模型每次返回的 tool call，不是脚本写死的。前缀 a = 审计员，c = 复核员。

`a:set_stage` → `a:list_files` → `a:read_file` → `a:read_file` → `a:list_endpoints` → `a:search_code` → `a:set_stage` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:search_code` → `a:read_file` → `a:list_files` → `a:read_file` → `a:search_code` → `a:search_code` → `a:read_file` → `a:read_file` → `a:set_stage` → `a:pattern_scan` → `a:list_files` → `a:read_file` → `a:find_references` → `a:read_file` → `a:read_file` → `a:list_files` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:search_code` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:search_code` → `a:search_code` → `a:read_file` → `a:find_references` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:set_stage` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:set_stage` → `a:get_audit_state` → `a:read_file` → `a:read_file` → `a:read_file` → `a:finalize_report` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:search_code` → `c:read_file` → `c:search_code` → `c:read_file` → `c:search_code` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:search_code` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:search_code` → `c:read_file` → `c:search_code` → `c:read_file` → `c:read_file` → `c:search_code` → `c:read_file` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:read_file` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:read_file` → `c:read_file` → `c:review_finding` → `c:review_finding` → `c:read_file` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:note_gap` → `c:note_gap` → `c:accept_report` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:search_code` → `a:read_file` → `a:read_file` → `a:read_file` → `a:upsert_finding` → `a:upsert_finding` → `a:resolve_gap` → `a:resolve_gap` → `a:finalize_report` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:search_code` → `c:read_file` → `c:read_file` → `c:search_code` → `c:search_code` → `c:read_file` → `c:read_file` → `c:review_finding` → `c:review_finding` → `c:accept_report` → `a:read_file` → `a:read_file` → `a:search_code` → `a:upsert_finding` → `a:upsert_finding` → `a:finalize_report` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:search_code` → `c:read_file` → `c:read_file` → `c:read_file` → `c:search_code` → `c:review_finding` → `c:review_finding` → `c:accept_report`

## F. 引用核对

共核对 48 条引用，未通过 0 条。

- 通过 `XSS-001` `app/ydata/models.py:258-260`
- 通过 `XSS-001` `app/ydata/models.py:198-200`
- 通过 `XSS-001` `lib/markdown/__init__.py:185-189`
- 通过 `XSS-001` `app/wiki/views.py:432-436`
- 通过 `XSS-001` `app/wiki/utils.py:18-18`
- 通过 `XSS-001` `templates/wiki/topic.html:53-55`
- 通过 `XSS-001` `templates/wiki/topic.html:58-60`
- 通过 `XSS-002` `app/ydata/views.py:86-86`
- 通过 `XSS-002` `app/ydata/models.py:407-408`
- 通过 `XSS-002` `app/ydata/models.py:443-444`
- 通过 `XSS-002` `app/wiki/utils.py:18-18`
- 通过 `XSS-003` `app/account/urls.py:8-8`
- 通过 `XSS-003` `app/account/views.py:100-102`
- 通过 `XSS-003` `app/account/views.py:205-208`
- 通过 `AUTHZ-001` `settings.py:164-166`
- 通过 `AUTHZ-001` `lib/ylinux_xmlrpc.py:39-45`
- 通过 `AUTHZ-001` `lib/ylinux_xmlrpc.py:60-69`
- 通过 `AUTHZ-001` `lib/ylinux_xmlrpc.py:168-181`
- 通过 `ACCESS-001` `app/wiki/views.py:447-460`
- 通过 `ACCESS-001` `app/wiki/views.py:277-278`
- 通过 `ACCESS-002` `app/ylab/urls.py:8-8`
- 通过 `ACCESS-002` `app/ylab/views.py:37-48`
- 通过 `CSRF-001` `settings.py:98-104`
- 通过 `CSRF-001` `app/wiki/views.py:421-436`
- 通过 `CRYPTO-001` `app/account/models.py:364-369`
- 通过 `CRYPTO-001` `app/account/models.py:424-430`
- 通过 `CRYPTO-001` `app/account/views.py:210-219`
- 通过 `CRYPTO-002` `app/account/models.py:62-65`
- 通过 `CRYPTO-002` `app/account/models.py:228-234`
- 通过 `CONFIG-001` `settings.py:18-19`
- 通过 `CONFIG-001` `urls.py:59-63`
- 通过 `CONFIG-002` `settings.py:78-79`
- 通过 `CONFIG-002` `app/sessions/backends/base.py:86-90`
- 通过 `CONFIG-003` `settings.py:42-49`
- 通过 `FILE-001` `app/ydata/views.py:78-84`
- 通过 `REDIRECT-001` `app/account/views.py:42-45`
- 通过 `REDIRECT-001` `app/account/views.py:58-60`
- 通过 `EMAIL-001` `app/home/views.py:34-48`
- 通过 `DESER-001` `app/sessions/backends/base.py:86-90`
- 通过 `DESER-001` `app/sessions/backends/base.py:92-102`
- 通过 `XSS-004` `app/ylab/views.py:31-34`
- 通过 `XSS-004` `app/ydata/views.py:91-95`
- 通过 `ACCESS-003` `app/ydata/views.py:101-105`
- 通过 `ACCESS-003` `app/ydata/views.py:117-126`
- 通过 `ACCESS-004` `app/ydata/models.py:51-52`
- 通过 `ACCESS-004` `app/ydata/models.py:91-101`
- 通过 `ACCESS-004` `app/wiki/views.py:81-90`
- 通过 `ACCESS-004` `app/bbs/views.py:44-56`
