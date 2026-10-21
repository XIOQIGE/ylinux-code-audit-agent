# ylinux_old 审计附录

## A. 运行统计

- 阅读过的文件：58
- pattern_scan 线索：29（关联发现 15，判为无害 10，重复 4，未处理 0）
- pattern_scan 次数：1；search_code / find_references 次数：9；list_endpoints：用过
- prompt tokens：6735137（缓存命中 6418304）
- completion tokens：73854（其中推理 37079）
- 复核：13 次 review_finding，其中否决 2 次

## B. 扫描线索处置

| 线索 | 规则 | 文件:行 | 处置 | 说明 |
| --- | --- | --- | --- | --- |
| L1 | `debug-true` | `settings.py:18` | finding:CONFIG-001 | DEBUG=True 硬编码且 DEBUG 下静态目录 show_indexes=True 的配置泄露问题。 |
| L2 | `db-password` | `settings.py:49` | finding:CONFIG-003 | 数据库口令 123456 明文写入 settings.py，切换 MySQL 后即为可直连的弱凭据。 |
| L3 | `secret-key` | `settings.py:79` | finding:CONFIG-002 | SECRET_KEY 硬编码进仓库。 |
| L4 | `sql-statement-format` | `app/account/backends.py:44` | benign | backends.py 中 SQL 的 %s 仅用于拼接 quote_name 后的标识符，用户值通过 cursor.execute(sql, [user_obj.id]) 参数化传入，不构成注入。 |
| L5 | `weak-hash` | `app/account/models.py:63,65,364,367,427,430` | finding:CRYPTO-002 | md5/sha1 单轮弱口令哈希。 |
| L6 | `insecure-random` | `app/account/models.py:232,364,427` | finding:CRYPTO-001 | random.random() 派生的 5 字符 salt 生成激活/重置密钥，熵值不足。 |
| L7 | `weak-hash` | `app/account/tokens.py:54` | benign | tokens.py 的 PasswordResetTokenGenerator 未被实际重置流程使用（视图走 Register.activation_key）；其依赖的 SECRET_KEY 泄露已在 CONFIG-002 记录。 |
| L8 | `open-redirect` | `app/account/views.py:38,60` | finding:REDIRECT-001 | 登录/退出 next 参数开放重定向。 |
| L9 | `open-redirect` | `app/admin/views.py:62,134,192,257,354` | duplicate | admin 登录后按 session 中 previous_url（来自 Referer）重定向，与 REDIRECT-001 同一根因。 |
| L10 | `redirect-referer` | `app/admin/views.py:65,134,192,257,354` | duplicate | admin 视图把 HTTP_REFERER 存入 session 作为跳转目标，与 REDIRECT-001 同属开放重定向根因。 |
| L11 | `cmd-popen` | `app/admin/views.py:362` | benign | reboot 视图的命令字符串来自固定字符串拼接 whoami 的返回（系统用户名），不含任何请求输入，不构成命令注入；仅权限面（需要 ydata.delete_catalog）值得注意。 |
| L12 | `cmd-os-system` | `app/admin/views.py:363` | benign | reboot 视图的命令字符串来自固定字符串拼接 whoami 的返回（系统用户名），不含任何请求输入，不构成命令注入；仅权限面（需要 ydata.delete_catalog）值得注意。 |
| L13 | `http-response-format` | `app/admin/views.py:400,481` | benign | HttpResponse 输出的 form.errors 是 Django 校验消息（固定文案）、邮件发送返回值等，且该接口需 ydata.delete_catalog 权限，不构成可被利用的反射型 XSS。 |
| L14 | `http-response-format` | `app/home/views.py:77` | benign | robots.txt 输出为固定字符串，无任何用户输入。 |
| L15 | `weak-hash` | `app/sessions/models.py:18,63` | finding:DESER-001 | Session 模型 encode/decode 用 cPickle + 公开密钥的 MD5 校验，反序列化风险已在 DESER-001 记录。 |
| L16 | `pickle-load` | `app/sessions/models.py:67` | finding:DESER-001 | Session 模型 encode/decode 用 cPickle + 公开密钥的 MD5 校验，反序列化风险已在 DESER-001 记录。 |
| L17 | `weak-hash` | `app/sessions/backends/base.py:89,95,141` | duplicate | SessionBase.encode/decode 与 Session 模型是同一套 pickle+MD5(SECRET_KEY) 实现，同属 DESER-001。 |
| L18 | `pickle-load` | `app/sessions/backends/base.py:98` | duplicate | SessionBase.encode/decode 与 Session 模型是同一套 pickle+MD5(SECRET_KEY) 实现，同属 DESER-001。 |
| L19 | `template-safe` | `app/wiki/utils.py:18` | finding:XSS-001 | render_post 模板对 body_html 使用 \|safe，是存储型 XSS 的输出点。 |
| L20 | `upload-handling` | `app/ydata/views.py:40` | finding:FILE-001 | 上传文件名直接进 open() 路径，路径穿越写文件。 |
| L21 | `weak-hash` | `app/ydata/views.py:52` | benign | sha1 仅用于计算上传文件内容的去重指纹，不承担安全职责。 |
| L22 | `http-response-format` | `app/ylab/views.py:21` | benign | ylab.time 用反引号输出服务器时间加固定脚本片段，无用户输入。 |
| L23 | `upload-handling` | `app/ylab/views.py:31` | benign | ylab 上传测试端点把文件名反射进响应，但响应只返回给上传者本人（自反射型 XSS），且该端点只是实验代码不落盘，无跨用户影响。 |
| L24 | `csrf-exempt` | `lib/django_xmlrpc/views.py:50,52,73` | benign | XML-RPC 端点按协议需要 csrf_exempt 且每个方法自带账号密码参数认证；其权限缺失已在 ACCESS-002、明文传输风险在 ACCESS-002 的修复建议中提及。 |
| L25 | `template-safe` | `templates/bbs/topic.html:23,30` | finding:XSS-001 | bbs/wiki 各模板对 body_html 与 POST_HTML 使用 \|safe 输出，是存储型 XSS 的渲染点。 |
| L26 | `template-safe` | `templates/wiki/editPostAJAX.html:19` | finding:XSS-001 | bbs/wiki 各模板对 body_html 与 POST_HTML 使用 \|safe 输出，是存储型 XSS 的渲染点。 |
| L27 | `template-safe` | `templates/wiki/post.html:12` | finding:XSS-001 | bbs/wiki 各模板对 body_html 与 POST_HTML 使用 \|safe 输出，是存储型 XSS 的渲染点。 |
| L28 | `template-safe` | `templates/wiki/replayAJAX.html:16` | finding:XSS-001 | bbs/wiki 各模板对 body_html 与 POST_HTML 使用 \|safe 输出，是存储型 XSS 的渲染点。 |
| L29 | `template-safe` | `templates/wiki/topic.html:54,59` | finding:XSS-001 | bbs/wiki 各模板对 body_html 与 POST_HTML 使用 \|safe 输出，是存储型 XSS 的渲染点。 |

## C. 阶段记录

- `recon`：开始勘察仓库目录结构，确定 Django 项目布局
- `hunt`：已读 settings/urls/中间件/会话/认证后端/账户视图/表单/wiki/ydata/admin/xmlrpc 等核心文件，确认了自定义 pickle 会话、无 CSRF 中间件、markdown 无 safe_mode + |safe 渲染、上传文件名拼接路径、开放注册等面
- `investigate`：沿数据流确认了 XSS（markdown 无 safe_mode + |safe）、上传路径穿越、editPostAJAX 越权、密码重置弱随机、XML-RPC 越权、无 CSRF 中间件、开放重定向等问题的完整链路
- `verify`：已写入 13 条发现（XSS、路径穿越、越权、弱随机重置、CSRF、配置、弱哈希、开放重定向、pickle 会话），29 条 pattern_scan 线索全部关账

## D. 读过的文件

- `settings.py`
- `urls.py`
- `manage.py`
- `app/sessions/middleware.py`
- `app/sessions/models.py`
- `app/account/backends.py`
- `app/account/middleware.py`
- `app/account/models.py`
- `app/account/tokens.py`
- `app/account/views.py`
- `app/account/decorators.py`
- `app/sessions/backends/db.py`
- `app/sessions/backends/file.py`
- `app/sessions/__init__.py`
- `app/sessions/backends/base.py`
- `app/ydata/views.py`
- `app/ydata/settings.py`
- `app/ydata/models.py`
- `app/ydata/util.py`
- `app/wiki/views.py`
- `app/wiki/utils.py`
- `app/ydata/forms.py`
- `templates/wiki/topic.html`
- `templates/wiki/post.html`
- `app/home/views.py`
- `app/home/forms.py`
- `app/home/models.py`
- `app/bbs/views.py`
- `app/me/views.py`
- `app/ylab/views.py`
- `app/blog/views.py`
- `app/admin/views.py`
- `lib/ylinux_xmlrpc.py`
- `lib/django_xmlrpc/views.py`
- `lib/django_xmlrpc/dispatcher.py`
- `lib/django_xmlrpc/decorators.py`
- `app/account/__init__.py`
- `app/account/forms.py`
- `app/account/context_processors.py`
- `app/syndication/views.py`
- `app/syndication/feeds.py`
- `app/admin/forms.py`
- `app/me/models.py`
- `templates/ydata/attachment.html`
- `templates/account/user.html`
- `app/wiki/urls.py`
- `app/account/urls.py`
- `app/ydata/urls.py`
- `app/admin/urls.py`
- `templates/bbs/topic.html`
- `app/wiki/models.py`
- `app/bbs/models.py`
- `scripts/ylinux-client.py`
- `app/home/urls.py`
- `app/bbs/urls.py`
- `app/blog/urls.py`
- `app/me/urls.py`
- `app/ylab/urls.py`

## E. 工具调用序列

完整参数和返回见 `trajectory.md` 和 `trace.jsonl`。顺序就是模型每次返回的 tool call，代码里没有预设。a = 审计员，c = 复核员。

`a:list_files` → `a:set_stage` → `a:read_file` → `a:read_file` → `a:read_file` → `a:list_endpoints` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:search_code` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:list_files` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:search_code` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:search_code` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:search_code` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:set_stage` → `a:pattern_scan` → `a:list_files` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:set_stage` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:read_file` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:triage_leads` → `a:set_stage` → `a:mark_reviewed` → `a:mark_reviewed` → `a:finalize_report` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:find_references` → `c:read_file` → `c:read_file` → `c:read_file` → `c:search_code` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:search_code` → `c:list_files` → `c:read_file` → `c:list_files` → `c:read_file` → `c:read_file` → `c:read_file` → `c:search_code` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:read_file` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:read_file` → `c:read_file` → `c:review_finding` → `c:review_finding` → `c:review_finding` → `c:note_gap` → `c:accept_report` → `a:read_file` → `a:read_file` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:upsert_finding` → `a:resolve_gap` → `a:read_file` → `a:read_file` → `a:read_file` → `a:resolve_gap` → `a:search_code` → `a:resolve_gap` → `a:get_audit_state` → `a:upsert_finding` → `a:finalize_report` → `c:read_file` → `c:read_file` → `c:read_file` → `c:read_file`

## F. 引用核对

共核对 34 条引用，未通过 0 条。

- 通过 `XSS-001` `app/ydata/models.py:251-260`
- 通过 `XSS-001` `app/ydata/models.py:198-200`
- 通过 `XSS-001` `app/ydata/forms.py:45-46`
- 通过 `XSS-001` `app/wiki/utils.py:17-18`
- 通过 `XSS-001` `templates/wiki/topic.html:53-54`
- 通过 `XSS-001` `app/wiki/views.py:432-436`
- 通过 `FILE-001` `app/ydata/views.py:78-84`
- 通过 `ACCESS-001` `app/wiki/views.py:447-451`
- 通过 `ACCESS-001` `app/wiki/views.py:456-460`
- 通过 `ACCESS-001` `app/wiki/views.py:271-278`
- 通过 `CRYPTO-001` `app/account/models.py:424-430`
- 通过 `CRYPTO-001` `app/account/views.py:182-194`
- 通过 `CRYPTO-001` `app/account/views.py:215-221`
- 通过 `ACCESS-002` `lib/ylinux_xmlrpc.py:39-45`
- 通过 `ACCESS-002` `lib/ylinux_xmlrpc.py:47-58`
- 通过 `ACCESS-002` `lib/ylinux_xmlrpc.py:60-67`
- 通过 `CSRF-001` `settings.py:98-104`
- 通过 `CSRF-001` `app/wiki/urls.py:34-38`
- 通过 `CSRF-001` `templates/wiki/topic.html:44-48`
- 通过 `ACCESS-003` `app/ylab/views.py:37-48`
- 通过 `ACCESS-003` `app/ylab/urls.py:5-8`
- 通过 `CONFIG-001` `settings.py:18-19`
- 通过 `CONFIG-001` `urls.py:59-62`
- 通过 `CONFIG-002` `settings.py:78-79`
- 通过 `CONFIG-002` `app/sessions/backends/base.py:140-143`
- 通过 `CONFIG-003` `settings.py:42-49`
- 通过 `CRYPTO-002` `app/account/models.py:228-234`
- 通过 `CRYPTO-002` `app/account/models.py:62-65`
- 通过 `REDIRECT-001` `app/account/views.py:42-45`
- 通过 `REDIRECT-001` `app/account/views.py:55-60`
- 通过 `DESER-001` `app/sessions/backends/base.py:86-98`
- 通过 `XSS-002` `app/ydata/views.py:77-84`
- 通过 `XSS-002` `urls.py:59-62`
- 通过 `XSS-002` `app/ydata/views.py:91-95`
