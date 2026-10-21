# ylinux_old 审计附录

## A. 运行统计

- 阅读过的文件：54
- pattern_scan 线索：29（关联发现 19，判为无害 10，重复 0，未处理 0）
- pattern_scan 次数：1；search_code / find_references 次数：20；list_endpoints：用过
- prompt tokens：7861615（缓存命中 7623168）
- completion tokens：84453（其中推理 47253）
- 复核：15 次 review_finding，其中否决 0 次

## B. 扫描线索处置

| 线索 | 规则 | 文件:行 | 处置 | 说明 |
| --- | --- | --- | --- | --- |
| L1 | `debug-true` | `settings.py:18` | finding:CONFIG-001 | settings.py:18 DEBUG=True 且 TEMPLATE_DEBUG=DEBUG，并触发 urls.py 中 /ymedia/ 的目录列表，记为配置泄露 finding。 |
| L2 | `db-password` | `settings.py:49` | finding:CONFIG-003 | settings.py:49 硬编码数据库口令 123456；当前 ENGINE 为 sqlite3 故未生效，作为配置问题记录。 |
| L3 | `secret-key` | `settings.py:79` | finding:CONFIG-002 | settings.py:79 SECRET_KEY 硬编码提交，是会话 pickle 完整性校验的唯一密钥。 |
| L4 | `sql-statement-format` | `app/account/backends.py:44` | benign | backends.py:43-57 中所有插入内容均为 connection.ops.quote_name 引用的固定标识符，用户值经 cursor.execute(sql, [user_obj.id]) 参数化传入，不存在注入。 |
| L5 | `weak-hash` | `app/account/models.py:63,65,364,367,427,430` | finding:CRYPTO-001 | account/models.py:50-66/228-234 的口令哈希为单轮 md5/sha1 + 5 字符盐，记为弱口令哈希。 |
| L6 | `insecure-random` | `app/account/models.py:232,364,427` | finding:CRYPTO-002 | account/models.py:427 重置 activation_key 的盐仅为 sha1(random.random()) 的 5 个 hex 字符（20 位熵），可暴力枚举；:232 的口令盐问题已并入 CRYPTO-001。 |
| L7 | `weak-hash` | `app/account/tokens.py:54` | benign | tokens.py 的 default_token_generator 未被任何视图调用（PasswordResetForm 无引用，实际重置流程使用 Register.activation_key），属死代码。 |
| L8 | `open-redirect` | `app/account/views.py:38,60` | finding:REDIR-001 | account/views.py:58-60 logout 将 next 直接作为重定向目标。 |
| L9 | `open-redirect` | `app/admin/views.py:62,134,192,257,354` | finding:REDIR-001 | admin/views.py:62-65 登录后按 session 中的 HTTP_REFERER 重定向，及 del_* 视图的 Referer 回跳，同属未校验重定向目标。 |
| L10 | `redirect-referer` | `app/admin/views.py:65,134,192,257,354` | finding:REDIR-001 | admin/views.py:62-65 登录后按 session 中的 HTTP_REFERER 重定向，及 del_* 视图的 Referer 回跳，同属未校验重定向目标。 |
| L11 | `cmd-popen` | `app/admin/views.py:362` | benign | os.popen('whoami')/os.system('killall -u %s') 的参数来自 whoami 输出而非请求输入，属固定命令；且 reboot 视图有 permission_required('ydata.delete_catalog') 保护，不构成注入。 |
| L12 | `cmd-os-system` | `app/admin/views.py:363` | benign | os.popen('whoami')/os.system('killall -u %s') 的参数来自 whoami 输出而非请求输入，属固定命令；且 reboot 视图有 permission_required('ydata.delete_catalog') 保护，不构成注入。 |
| L13 | `http-response-format` | `app/admin/views.py:400,481` | benign | admin/views.py:400 将 form.errors 原样返回，端点虽需权限（已并入 CSRF/GET 写问题），但 Django 1.x 表单错误信息不直接回显用户输入值，无法构成可利用的反射 XSS；因该 GET 写端点问题已由 CSRF-001 覆盖，此处按 benign 处理 XSS 线索。 |
| L14 | `http-response-format` | `app/home/views.py:77` | benign | home/views.py:77 robots 返回固定字符串，无用户输入。 |
| L15 | `weak-hash` | `app/sessions/models.py:18,63` | finding:CONFIG-002 | 会话 pickle 数据以 md5(pickled+SECRET_KEY) 做完整性校验并 pickle.loads 反序列化；SECRET_KEY 已公开（L3），校验可伪造，同根因并入 CONFIG-002。 |
| L16 | `pickle-load` | `app/sessions/models.py:67` | finding:CONFIG-002 | 会话 pickle 数据以 md5(pickled+SECRET_KEY) 做完整性校验并 pickle.loads 反序列化；SECRET_KEY 已公开（L3），校验可伪造，同根因并入 CONFIG-002。 |
| L17 | `weak-hash` | `app/sessions/backends/base.py:89,95,141` | finding:CONFIG-002 | 会话 pickle 数据以 md5(pickled+SECRET_KEY) 做完整性校验并 pickle.loads 反序列化；SECRET_KEY 已公开（L3），校验可伪造，同根因并入 CONFIG-002。 |
| L18 | `pickle-load` | `app/sessions/backends/base.py:98` | finding:CONFIG-002 | 会话 pickle 数据以 md5(pickled+SECRET_KEY) 做完整性校验并 pickle.loads 反序列化；SECRET_KEY 已公开（L3），校验可伪造，同根因并入 CONFIG-002。 |
| L19 | `template-safe` | `app/wiki/utils.py:18` | finding:XSS-001 | wiki/utils.py POST_MAIN 及 bbs/wiki 各模板以 \|safe 渲染未经转义的 body_html（Markdown safe_mode=False 生成），同属存储型 XSS。 |
| L20 | `upload-handling` | `app/ydata/views.py:40` | finding:FILE-001 | ydata/views.py:40/78-82 将 f.name 直接拼入保存路径，路径穿越任意文件写入。 |
| L21 | `weak-hash` | `app/ydata/views.py:52` | benign | ydata/views.py:52-55 的 SHA1 仅用于文件去重（相同内容不重复存储），不用于完整性/认证，弱哈希不构成风险。 |
| L22 | `http-response-format` | `app/ylab/views.py:21` | benign | ylab time 视图用反引号输出 datetime 的 repr，无任何用户输入。 |
| L23 | `upload-handling` | `app/ylab/views.py:31` | benign | ylab/views.py:31-34 回显的文件名只能来自受害者本机上传的文件，属 self-XSS，无法跨用户触发；且该端点不保存文件，仅调试用途。 |
| L24 | `csrf-exempt` | `lib/django_xmlrpc/views.py:50,52,73` | benign | XML-RPC 接口以方法参数携带用户名口令认证、不依赖 Cookie 会话，csrf_exempt 合理；全站缺少 CSRF 中间件的问题已由 CSRF-001 记录。 |
| L25 | `template-safe` | `templates/bbs/topic.html:23,30` | finding:XSS-001 | wiki/utils.py POST_MAIN 及 bbs/wiki 各模板以 \|safe 渲染未经转义的 body_html（Markdown safe_mode=False 生成），同属存储型 XSS。 |
| L26 | `template-safe` | `templates/wiki/editPostAJAX.html:19` | finding:XSS-001 | wiki/utils.py POST_MAIN 及 bbs/wiki 各模板以 \|safe 渲染未经转义的 body_html（Markdown safe_mode=False 生成），同属存储型 XSS。 |
| L27 | `template-safe` | `templates/wiki/post.html:12` | finding:XSS-001 | wiki/utils.py POST_MAIN 及 bbs/wiki 各模板以 \|safe 渲染未经转义的 body_html（Markdown safe_mode=False 生成），同属存储型 XSS。 |
| L28 | `template-safe` | `templates/wiki/replayAJAX.html:16` | finding:XSS-001 | wiki/utils.py POST_MAIN 及 bbs/wiki 各模板以 \|safe 渲染未经转义的 body_html（Markdown safe_mode=False 生成），同属存储型 XSS。 |
| L29 | `template-safe` | `templates/wiki/topic.html:54,59` | finding:XSS-001 | wiki/utils.py POST_MAIN 及 bbs/wiki 各模板以 \|safe 渲染未经转义的 body_html（Markdown safe_mode=False 生成），同属存储型 XSS。 |

## C. 阶段记录

- `recon`：已读 settings.py/urls.py/manage.py：老式 Django 1.x 项目，自定义 session/认证，DEBUG=True，硬编码 SECRET_KEY，XML-RPC 接口公开。接下来用 list_endpoints 规划视图阅读。
- `hunt`：已覆盖账户/会话/权限/上传/XML-RPC 等核心文件，发现多个可疑点（|safe 渲染、raw SQL 拼接、pickle 会话、os.system）。现在运行 pattern_scan 并检索模板中的 |safe 与危险函数。
- `investigate`：已逐个阅读 account/wiki/ydata/ylab/admin/bbs/me/blog/syndication/sessions 视图、模型、表单、模板及 vendored markdown 库，确认了 XSS、上传路径穿越、越权、CSRF、弱密码存储、重置令牌弱熵等多条数据流。开始写入 findings 并做线索关单。
- `verify`：已写入 14 条 findings（XSS-001/002、FILE-001/002、ACCESS-001/002、CSRF-001、CRYPTO-001/002、CONFIG-001/002/003、REDIR-001、MISC-001），现在开始对 pattern_scan 的 29 条线索逐一关单。

## D. 读过的文件

- `settings.py`
- `urls.py`
- `manage.py`
- `app/sessions/middleware.py`
- `app/sessions/models.py`
- `app/account/backends.py`
- `app/account/middleware.py`
- `app/sessions/__init__.py`
- `app/account/models.py`
- `app/account/tokens.py`
- `app/sessions/backends/file.py`
- `app/account/views.py`
- `app/account/__init__.py`
- `app/wiki/views.py`
- `app/wiki/utils.py`
- `app/ydata/models.py`
- `app/ydata/views.py`
- `app/ylab/views.py`
- `app/admin/views.py`
- `lib/ylinux_xmlrpc.py`
- `lib/django_xmlrpc/views.py`
- `lib/django_xmlrpc/dispatcher.py`
- `app/account/forms.py`
- `app/account/decorators.py`
- `app/home/views.py`
- `app/home/forms.py`
- `app/ydata/util.py`
- `app/ydata/settings.py`
- `app/sessions/backends/base.py`
- `app/sessions/backends/db.py`
- `app/bbs/views.py`
- `app/me/views.py`
- `app/blog/views.py`
- `app/syndication/views.py`
- `templates/wiki/topic.html`
- `lib/markdown/__init__.py`
- `app/ydata/forms.py`
- `app/admin/forms.py`
- `templates/ydata/attachment.html`
- `app/account/context_processors.py`
- `app/wiki/urls.py`
- `app/ylab/urls.py`
- `app/account/urls.py`
- `app/ydata/urls.py`
- `app/admin/urls.py`
- `scripts/ylinux-client.py`
- `lib/django_xmlrpc/decorators.py`
- `scripts/.htaccess`
- `templates/bbs/topic.html`
- `templates/wiki/replayAJAX.html`
- `templates/wiki/editPostAJAX.html`
- `templates/account/user.html`
- `templates/wiki/post.html`
- `lib/markdown/postprocessors.py`

## E. 工具调用序列

完整参数和返回见 `trajectory.md` 和 `trace.jsonl`。顺序就是模型每次返回的 tool call，代码里没有预设。a = 审计员，c = 复核员。

`a:set_stage` → `a:list_files` → `a:read_file` → `a:read_file` → `a:read_file` → `a:set_stage` → `a:list_endpoints` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:search_code` → `a:list_files` → `a:search_code` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:search_code` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:set_stage` → `a:pattern_scan` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:search_code` → `a:read_file` → `a:list_files` → `a:read_file` → `a:search_code` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:search_code` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:find_references` → `a:find_references` → `a:read_file` → `a:set_stage` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:set_stage` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:mark_reviewed` → `a:mark_reviewed` → `a:mark_reviewed` → `a:mark_reviewed` → `a:mark_reviewed` → `a:mark_reviewed` → `a:mark_reviewed` → `a:mark_reviewed` → `a:mark_reviewed` → `a:finalize_report` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:search_code` → `c:read_file` → `c:read_file` → `c:read_file` → `c:search_code` → `c:read_file` → `c:read_file` → `c:read_file` → `c:search_code` → `c:read_file` → `c:search_code` → `c:search_code` → `c:search_code` → `c:read_file` → `c:read_file` → `c:search_code` → `c:read_file` → `c:read_file` → `c:search_code` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:search_code` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:search_code` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:note_gap` → `c:accept_report` → `a:find_references` → `a:read_file` → `a:read_file` → `a:read_file` → `a:upsert_finding` → `a:resolve_gap` → `a:finalize_report` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:search_code` → `c:read_file` → `c:read_file` → `c:read_file` → `c:review_finding` → `c:accept_report`

## F. 引用核对

共核对 39 条引用，未通过 0 条。

- 通过 `XSS-001` `app/wiki/views.py:432-436`
- 通过 `XSS-001` `app/ydata/models.py:251-260`
- 通过 `XSS-001` `lib/markdown/__init__.py:185-189`
- 通过 `XSS-001` `app/wiki/utils.py:17-19`
- 通过 `XSS-001` `templates/wiki/topic.html:53-54`
- 通过 `XSS-001` `templates/bbs/topic.html:22-23`
- 通过 `XSS-002` `app/account/urls.py:8-8`
- 通过 `XSS-002` `app/account/views.py:99-102`
- 通过 `XSS-002` `app/account/views.py:205-208`
- 通过 `FILE-001` `app/ydata/views.py:37-44`
- 通过 `FILE-001` `app/ydata/views.py:78-86`
- 通过 `FILE-001` `settings.py:74-75`
- 通过 `ACCESS-002` `app/wiki/views.py:447-460`
- 通过 `ACCESS-002` `app/wiki/views.py:213-218`
- 通过 `ACCESS-001` `lib/ylinux_xmlrpc.py:39-58`
- 通过 `ACCESS-001` `lib/ylinux_xmlrpc.py:60-69`
- 通过 `ACCESS-001` `settings.py:164-175`
- 通过 `CSRF-001` `settings.py:98-104`
- 通过 `CSRF-001` `app/wiki/views.py:271-283`
- 通过 `CSRF-001` `app/sessions/middleware.py:36-41`
- 通过 `CRYPTO-001` `app/account/models.py:50-66`
- 通过 `CRYPTO-001` `app/account/models.py:228-234`
- 通过 `CRYPTO-002` `app/account/models.py:424-430`
- 通过 `CRYPTO-002` `app/account/views.py:201-223`
- 通过 `CONFIG-001` `settings.py:18-19`
- 通过 `CONFIG-001` `urls.py:59-63`
- 通过 `CONFIG-002` `settings.py:78-79`
- 通过 `CONFIG-002` `app/sessions/models.py:13-19`
- 通过 `CONFIG-002` `app/sessions/backends/base.py:92-98`
- 通过 `REDIR-001` `app/account/views.py:55-60`
- 通过 `REDIR-001` `app/admin/views.py:62-66`
- 通过 `FILE-002` `app/ydata/views.py:117-127`
- 通过 `FILE-002` `app/ydata/urls.py:9-9`
- 通过 `MISC-001` `app/ylab/views.py:37-48`
- 通过 `MISC-001` `app/ylab/urls.py:5-8`
- 通过 `CONFIG-003` `settings.py:42-53`
- 通过 `ACCESS-003` `app/ydata/models.py:91-101`
- 通过 `ACCESS-003` `app/wiki/views.py:81-96`
- 通过 `ACCESS-003` `app/wiki/views.py:368-388`
