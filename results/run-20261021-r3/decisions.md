# 关键决策

从 `trace.jsonl` 里抽出来的关键节点，完整过程见 `trajectory.md`。

## 门禁

- auditor step 53 `finalize_report` 通过
- critic step 27 `accept_report` 通过
- auditor step 7 `finalize_report` 通过
- critic step 5 `accept_report` 通过

## 发现的写入被拒与改判

- auditor step 45 `CONFIG-003` 写入被拒：evidence quote did not match the file
- auditor step 2 `FILE-002` 写入被拒：confirmed findings in flow categories need data_flow: name the untrusted source (request param, header, stored user content, upload name...), each hop, and the sink. If you cannot name the source from code you read, use needs_review or rejected.

## 复核

- critic step 23 `XSS-001` 同意。最弱一环：最站不住的一环是"中间是否可能被 ylinux_text_filter 消毒"。我核实了 app/ydata/models.py:396-452：该过滤器只做 [A:ID]/[W:ID]/[I:ID] 宏替换，完全不清理 <script> 等原始 HTML；lib/markdown/__init__.py:188 确认 Markdown 构造器默认 safe_mode=False，Post.save 的 markup='none' 分支（models.py:258-260）和 Topic.save_file 的 convertFile（198-200）都没传 safe_mode，postpro
- critic step 23 `XSS-002` 复核被拒：read_file each evidence location with at least 10 lines of context on both sides before judging it
- critic step 23 `XSS-003` 同意。最弱一环：最站不住的一环是"拼接进 <script> 的响应是否真的会执行"。核实：两个视图都返回默认 content_type=text/html 的整页 HttpResponse，ylab 把文件名拼进 innerHTML 再内联进脚本参数（ylab/views.py:32-33），文件名含 </script> 即可提前闭合脚本标签注入新脚本；ydata 文件名位于双引号 JS 字符串内（ydata/views.py:91-95），引号即可闭合，无需 </script>。ylab 视图无任何登录/权限装饰器（匿名可达），ydata 为 @login_required。
- critic step 23 `FILE-001` 同意。最弱一环：最站不住的一环是"Django 是否会对 f.name 做 basename 消毒"。核实：ydata/views.py:78 直接用客户端文件名 f.name 拼 local_name，未经过 FileSystemStorage.get_valid_name 等任何归一化；Django 1.x 的 UploadedFile 对 name 不做路径剥离；79-84 行 open(save_path,'wb+') 前无 realpath 前缀校验，追加 ../ 段即可越出 MEDIA_ROOT/ydata/attachments。
- critic step 23 `ACCESS-001` 复核被拒：read_file each evidence location with at least 10 lines of context on both sides before judging it
- critic step 23 `ACCESS-002` 复核被拒：read_file each evidence location with at least 10 lines of context on both sides before judging it
- critic step 23 `CSRF-001` 复核被拒：read_file each evidence location with at least 10 lines of context on both sides before judging it
- critic step 23 `REDIRECT-001` 复核被拒：read_file each evidence location with at least 10 lines of context on both sides before judging it
- critic step 23 `ACCESS-003` 同意。最弱一环：最站不住的一环是"是否真的匿名可达且写全表"。核实 app/ylab/urls.py:8 无装饰器直接映射到 update_post_profile，视图（ylab/views.py:37-48）遍历 Post.objects.all() 并对每行 save() 重写 updated/touser，无方法限制无鉴权。
- critic step 23 `CONFIG-001` 复核被拒：read_file each evidence location with at least 10 lines of context on both sides before judging it
- critic step 23 `CONFIG-002` 复核被拒：read_file each evidence location with at least 10 lines of context on both sides before judging it
- critic step 23 `CRYPTO-001` 复核被拒：read_file each evidence location with at least 10 lines of context on both sides before judging it
- critic step 23 `SENSITIVE-001` 复核被拒：read_file each evidence location with at least 10 lines of context on both sides before judging it
- critic step 23 `CONFIG-003` 复核被拒：read_file each evidence location with at least 10 lines of context on both sides before judging it
- critic step 25 `XSS-002` 同意。最弱一环：最站不住的一环是"百分号解码后的 <script> 能否匹配 (?P<key>.+)/ 并原样回显"。核实：WSGI 规范下服务器对 PATH_INFO 做 URL 解码（wsgiref/mod_wsgi 均如此），解码后 /account/register/<script>alert(1)</script>/ 中 .+ 匹配任意字符含尖括号且满足尾斜杠；views.py:96-102 与 202-208 在 Register 查找失败分支把 key 直接 % 拼进 HttpResponseForbidden（默认 text/html），无任何转义。
- critic step 25 `ACCESS-001` 同意。最弱一环：最站不住的一环是"是否真的没有归属校验"。核实 app/wiki/views.py:447-467：editPostAJAX 仅有 @login_required，GET 返回任意 post，POST 直接 post.body=post_body 后 save()，全文无 post.user==request.user 检查；对比同文件 edit_topic:217-218 与 del_post:277-278 均有所有权检查，差异属实。
- critic step 25 `ACCESS-002` 同意。最弱一环：最站不住的一环是"has_auth 是否仅认证不鉴权"。核实 lib/ylinux_xmlrpc.py:39-45 has_auth 只调用 authenticate 判断凭据有效；delete_topic（47-58）、delete_all_topic（60-69）、edit_topic（168-185）均无权限码或对象归属检查；settings.py:164-174 把这些方法注册为公开 XML-RPC 方法，urls.py:45-48 /xmlrpc/ 无登录要求。
- critic step 25 `CSRF-001` 同意。最弱一环：最站不住的一环是"是否真的全站无 CSRF 防护"。全仓搜索 csrf 仅命中 lib/django_xmlrpc/views.py 的 csrf_exempt；settings.py:98-104 MIDDLEWARE_CLASSES 无 CsrfViewMiddleware；app 代码无 csrf_protect 装饰器；del_user（admin/views.py:250-257）、manage_topic 删除（wiki/views.py:237-250）等写操作可 GET 触发，均只依赖会话 Cookie。
- critic step 25 `REDIRECT-001` 同意。最弱一环：最站不住的一环是"跳转目标是否真的无校验"。核实 account/views.py:55-60 logout 直接 HttpResponseRedirect(request.GET.get('next'))；login 将 GET 的 next 存入 session 并在成功后跳转（42-45、36-38）；admin login 用 HTTP_REFERER 存 session 并在登录后跳转（admin/views.py:62,65）；三处均无 is_safe_url/前缀校验。
- critic step 25 `CONFIG-001` 同意。最弱一环：最站不住的一环是"配置是否真的生效（取决于部署）"。核实 settings.py:18-19 DEBUG=True 确已提交，urls.py:59-63 在 DEBUG 下挂载 django.views.static.serve 且 show_indexes=True 暴露 MEDIA_ROOT 目录树；发现本身已注明"部署未覆盖时生效"的条件，medium 定级与条件性相符。
- critic step 25 `CONFIG-002` 同意。最弱一环：最站不住的一环是"影响是否被夸大（能否直接伪造会话）"。核实：会话签名 MD5(pickle+KEY)（sessions/models.py:13-19）但会话数据存 DB、客户端只有 session_key，密钥泄露本身不能直接远程伪造会话；密码重置令牌 SHA1(KEY+uid+password+last_login)（tokens.py:53-57）在同时获得口令哈希与 last_login 时可离线伪造——发现已如实表述这一前置条件，未夸大。
- critic step 25 `CRYPTO-001` 同意。最弱一环：最站不住的一环是"是否真是单轮 SHA1 + 弱盐"。核实 app/account/models.py:62-66 get_hexdigest 为 md5/sha1 单轮拼接；set_password（228-234）盐 = sha1(str(random.random()))[:5] 仅 5 个十六进制字符，随机源为 Mersenne Twister 伪随机，描述准确。
- critic step 25 `SENSITIVE-001` 同意。最弱一环：最站不住的一环是"表单是否真有 password 字段、save 是否真的忽略它"。核实 app/admin/forms.py:75-96：AddUserForm.Meta.fields 含 'password'，但 save() 构造 User 时未处理密码，User.password 为无默认 CharField（account/models.py:165-166）→ 入库空串；对比 EditUserForm.save() 在 115 行显式调用 set_password，差异属实。
- critic step 25 `CONFIG-003` 同意。最弱一环：最站不住的一环是"凭据当前是否生效"。核实 settings.py:42-49 当前 ENGINE 为 sqlite3（46 行），USER 'ylinux'/PASSWORD '123456' 确实未被使用；发现已如实限定为"切换 mysql 时生效"且邮件口令为诱导填写位置，low 定级恰当。
- critic step 4 `CRYPTO-002` 同意。最弱一环：最站不住的一环是"password_reset 是否真的既无时效校验又无速率限制、且命中后就能保存新口令"。我核实了 app/account/views.py:201-223：password_reset 仅有 @render_to 装饰器（无登录要求），按 activation_key 查库（205-206），错误 key 返回可区分的 403"错误的 Key"（208），正确 key 直接渲染 SetPasswordForm 并在 is_valid 后 form.save()；app/account/forms.py:166-170 确认 save() 调用 user.set_passwo
- critic step 4 `FILE-002` 同意。最弱一环：最站不住的一环是"上传落盘的文件能否被同源以 text/html 服务并执行"。我核实了 urls.py:59-63：DEBUG=True（settings.py:18-19）时 /ymedia/ 由 django.views.static.serve 同源服务（show_indexes=True），static.serve 按扩展名经 mimetypes 猜测 Content-Type，.html 以 text/html 下发即执行；生产侧 scripts/.htaccess:23-24 的 RewriteCond REQUEST_FILENAME !-f 意味着已存在的文件（上传附件）不会

## 缺口

- critic step 26 `note_gap` G1：密码重置/注册激活令牌熵仅约 20 bit 且来自可预测 PRNG：RegisterManager.create_profile 与 Register.reset_activation_key 用 sha1(str(random.random()))[:5] 作盐再对 email 做 sha1（app/account/models.py:361-369、424-430），而 /account/password/reset/<key>/（app/account/views.py:202-208）只按 key 查库、不校验时效、无速率限制——攻击者知道目标邮箱即可在 2^20 空间内枚举出重置链接并接管任意账号。CRYPTO-001/CONFIG-002 只覆盖了口令哈希和 SECRET_KEY，未覆盖该令牌熵问题，属于独立的账号接管路径。
- critic step 26 `note_gap` G2：上传接口对文件类型/扩展名无任何白名单，且文件以客户端文件名原样落盘到 MEDIA_ROOT 下、由同源 /ymedia/ 静态服务（DEBUG 下 django.views.static.serve，生产下若沿用 Web 服务器托管同样生效）：即使不做路径穿越，登录用户也可上传 .html/.svg 等文件获得同源 URL，形成持久的存储型 XSS/钓鱼页面托管。FILE-001 只覆盖了路径穿越写入，未覆盖"合法落盘文件被同源静态服务渲染执行"这一独立风险。
- auditor step 4 `resolve_gap` G1：已重新读取 app/account/models.py:359-430 与 app/account/views.py:166-223 确认实现：create_profile/reset_activation_key 的 salt 为 sha1(str(random.random()))[:5]（20 bit），activation_key=sha1(salt+email)；password_reset 视图只按 key 查库、无时效校验、无速率限制，命中后即可提交新口令。已新增 finding CRYPTO-002（severity=high，CWE-330，entry_role=anonymous）记录该独立账号接管路径，与 CRYPTO-001（口令哈希）/CONFIG-002（SECRET_KEY）区分。（被拒：search_code or read_file the implementation behind this gap before resolving it; do not answer from framework defaults）
- auditor step 4 `resolve_gap` G2：已确认 ydata/views.py:77-90 上传无类型/扩展名白名单（仅大小检查），文件落盘 MEDIA_ROOT（settings.py:74-75 同源 /ymedia/），urls.py:59-63 在 DEBUG 下用 django.views.static.serve 同源服务该目录。已新增 finding FILE-002（CWE-434，medium，registered_open，data_flow 齐全）：登录用户上传 .html/.svg 获得同源 URL 形成持久存储型 XSS/钓鱼托管，与 FILE-001 的路径穿越是同一上传点的两个独立风险（一个靠 ../ 越界，一个靠合法落盘+同源静态服务+无类型白名单），故分别记录。（被拒：search_code or read_file the implementation behind this gap before resolving it; do not answer from framework defaults）
- auditor step 6 `resolve_gap` G1：已通过 search_code + read_file 重新核实实现：app/account/models.py:364,367,427,430 显示 salt = sha_constructor(str(random.random())).hexdigest()[:5]（5 个十六进制字符，约 20 bit），activation_key = sha_constructor(salt+email).hexdigest()；app/account/views.py:205-219 的 password_reset 只按 key 查库、无时效校验、无速率限制，命中即渲染 SetPasswordForm 并可保存新口令。该路径独立于 CRYPTO-001/CONFIG-002，已新增 finding CRYPTO-002（high，CWE-330，anonymous）。
- auditor step 6 `resolve_gap` G2：已 read_file app/ydata/views.py:31-100 核实：上传仅检查大小（41 行），无扩展名/MIME 白名单；78-84 行以客户端文件名写入 MEDIA_ROOT/ydata/attachments，settings.py:74-75 MEDIA_URL='/ymedia/' 同源，urls.py:59-63 在 DEBUG=True 下由 django.views.static.serve（show_indexes=True）同源服务该目录，.html 按 text/html 下发执行。已新增 finding FILE-002（CWE-434，medium，registered_open，data_flow 完整）；与 FILE-001（路径穿越）为同一上传点两个独立风险，故分别记录。

## 判为无害的扫描线索

- auditor step 48 L4 判为无害：backends.py 的 SQL 只用 %s 拼接 quote_name() 处理过的表/列名，用户值通过 cursor.execute(sql, [user_obj.id]) 参数化传入，不存在注入
- auditor step 48 L11, L12 判为无害：reboot 视图中 os.popen('whoami')/os.system('killall -u %s') 的命令串不含任何请求参数，whoami 输出是固定服务账户名，非注入；且该视图有 permission_required 保护
- auditor step 48 L13 判为无害：email_to_all 输出的 form.errors 经 Django ErrorList 渲染（该版本对错误消息做条件转义），ret 为 send_mail 返回值（数字），无原始用户输入直接进入响应 HTML
- auditor step 48 L14 判为无害：robots 视图输出固定字符串，无用户输入
- auditor step 48 L15, L16, L17, L18 判为无害：会话数据存于数据库（ylinux_session 表），客户端只持有 session_key，pickle.loads 的输入来自 DB 且带 MD5(SECRET_KEY) 校验；未发现任何从请求到会话数据的写路径（无 SQL 注入），无法远程投毒反序列化。SECRET_KEY 泄露的影响单独记录在 CONFIG-002
- auditor step 49 L21 判为无害：sha1 仅用于附件去重（按内容哈希比较），不承担安全职能，不是漏洞
- auditor step 49 L22 判为无害：ylab time 视图回显的是服务器当前时间 repr（反引号），不含请求输入，非 XSS
- auditor step 49 L24 判为无害：/xmlrpc/ 的 csrf_exempt 合理：XML-RPC 客户端凭据在每次调用中传递，不依赖会话 Cookie，豁免 CSRF 不会带来跨站伪造风险；该接口的鉴权缺失另记录在 ACCESS-002
