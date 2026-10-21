# 关键决策

从 `trace.jsonl` 自动抽取。完整上下文见 `trajectory.md`。

## 门禁

- auditor step 49 `finalize_report` 通过
- critic step 23 `accept_report` 通过
- auditor step 7 `finalize_report` 通过
- critic step 6 `accept_report` 通过
- auditor step 3 `finalize_report` 通过
- critic step 4 `accept_report` 通过

## 发现的写入被拒与改判

无。

## 复核

- critic step 15 `XSS-001` 同意。最弱一环：最弱一环是“Markdown 未开 safe_mode 时原始 HTML 是否真的原样透传”——如果库里另有转义，整条链就断了。我核实了 lib/markdown/__init__.py:188（构造函数默认 safe_mode=False，docstring 明确 safe_mode 作用是 "Disallow raw html"）、convertFile(428-459 行，应用 myfilter 后直接 convert，无任何 safe 处理）、ylinux_text_filter（models.py:396-452，只做 [A:id]/[wiki:id]/[img:id] 替换，不转义
- critic step 15 `XSS-002` 同意。最弱一环：最弱一环是“文件名是否会被运行时框架清洗掉尖括号/引号”——即使 Django 对 UploadedFile.name 做 os.path.basename，也只剥路径分隔符；不含 `/` 的 payload（如 `x"><img src=y onerror=alert(1)>`）完整保留，而拼接点在 <a> 文本位和 <img alt> 属性位，引号/尖括号足以注入。我核实了 models.py:407-408 与 443-444 确为 % 直接拼接 a.name/img.name，无任何 escape。
- critic step 15 `XSS-003` 同意。最弱一环：最弱一环是“URL 里的尖括号能否真的进入 key 并到达回显”。我核实了 account/urls.py:8/13 使用 `(?P<key>.+)`，`.` 匹配除换行外任意字符，且 Django 在匹配前对路径做 URL 解码，`%3Cscript%3E` 会变成 `<script>` 进入 key；account/views.py:102 与 208 用 % 直接拼进 HttpResponseForbidden 的 HTML 字符串，全程无 escape，响应为 text/html。
- critic step 15 `AUTHZ-001` 复核被拒：read_file each evidence location with at least 10 lines of context on both sides before judging it
- critic step 15 `ACCESS-001` 同意。最弱一环：最弱一环是“是否存在审计员漏看的属主/权限校验”。我把 editPostAJAX 全文（wiki/views.py:447-467）读完：只有 @login_required，get_object_or_404 后直接 post.body=post_body; post.save()，没有任何 post.user 判断；对比同文件 del_post(277-278) 明确有 `post.user != request.user` 检查，证明属主校验模式存在而该视图缺失。
- critic step 15 `ACCESS-002` 同意。最弱一环：最弱一环是“端点是否真的匿名可触发任意方法”。核实 ylab/urls.py:8 路由存在，ylab/views.py:37-48 函数无任何装饰器、无 method 判断、无参数，GET 即遍历 Post.objects.all() 逐条改 touser/updated 并 save()（每次 save 还会重渲染 Markdown 写库）。
- critic step 15 `CSRF-001` 同意。最弱一环：最弱一环是“是否确实没有任何 CSRF 防护生效”。核实 settings.py:98-104 MIDDLEWARE_CLASSES 只有 CommonMiddleware 与自研 Session/Auth 中间件，无 CsrfViewMiddleware；模板上下文处理器（120-130）也无 csrf 处理器，个别模板即便有 {% csrf_token %} 也不会被校验。认证完全依赖 Cookie 会话（sessions/middleware.py:37-41）。
- critic step 17 `AUTHZ-001` 同意。最弱一环：最弱一环是“这些方法是否真的在网络层注册暴露，而非死代码”。我核实了 lib/django_xmlrpc/views.py:122-149 在 import 时把 settings.XMLRPC_METHODS 注册进 dispatcher，urls.py:47 挂载 /xmlrpc/，handle_xmlrpc(81-92) 对 POST 的 raw_post_data 直接 _marshaled_dispatch；settings.py:164-175 确实暴露 delete_topic/delete_all_topic/metaWeblog.*。
- critic step 17 `CRYPTO-001` 复核被拒：read_file each evidence location with at least 10 lines of context on both sides before judging it
- critic step 17 `CRYPTO-002` 复核被拒：read_file each evidence location with at least 10 lines of context on both sides before judging it
- critic step 17 `CONFIG-001` 同意。最弱一环：最弱一环是“DEBUG=True 是否真的会生效而非被覆盖”。settings.py 全文（1-177）无 local_settings 导入或环境覆盖逻辑，DEBUG=True 为仓库内硬编码默认值；urls.py:59-63 的 show_indexes 静态服务直接以 settings.DEBUG 为条件，配置即代码。
- critic step 17 `CONFIG-002` 同意。最弱一环：最弱一环是“该密钥是否真被安全敏感路径使用”。核实 sessions/backends/base.py:89/95 与 sessions/models.py:18/63 均用 md5(pickled + settings.SECRET_KEY) 作为会话数据防篡改签名，密钥随仓库公开后任何读者都能为任意 pickle 生成合法签名，完整性保护确实失效。
- critic step 17 `CONFIG-003` 同意。最弱一环：最弱一环是“该口令当前是否生效”——核实 settings.py:42-53，ENGINE 为 sqlite3，口令字段对 sqlite 无认证作用，所以现实影响确实有限；审计也如实标注了这一点并定 low，无夸大。
- critic step 19 `CRYPTO-001` 同意。最弱一环：最弱一环是“20 位熵可在线枚举”的可达性——攻击者必须能让系统对目标邮箱生成 key 并无限速地试。我核实了 password_reset_request（views.py:173-187）对任意已注册邮箱即 get-or-create Register 并 reset_activation_key；password_reset（201-223）对 /account/password/reset/<key>/ 无任何限速、锁定或过期检查；salt 只有 sha1(random.random())[:5] 即 5 个十六进制字符（2^20≈105 万候选），email 已知时全部候选可离线预计
- critic step 19 `CRYPTO-002` 同意。最弱一环：最弱一环是“哈希强度描述是否与代码一致”。核实 account/models.py:62-65 确为单轮 md5/sha1，set_password(228-234) 盐 = sha1(random.random() 派生)[:5] 即 5 字符小盐，check_password(243-244) 还兼容无盐 md5。
- critic step 21 `FILE-001` 否决，建议 low。最弱一环：最弱一环是可利用性：finding 自己也承认“是否可携带 ../ 取决于运行时 Django 版本”。但代码使用的 `req.FILES['single_file']` + `f.chunks()` API 形态决定了运行时必然是 Django≥1.0，而 Django 自 1.0 引入该上传 API 起，UploadedFile._set_name 就对 name 做 os.path.basename 清洗：POSIX 下任何含 `/` 的 ../ 路径会被剥成最后一段；Windows 风格 `..\` 在 POSIX 服务器上只是普通文件名字符不构成穿越，在 Windows 上 ntpa
- critic step 21 `REDIRECT-001` 同意。最弱一环：最弱一环是“跳转目标是否真为用户可控且无校验”。核实 account/views.py:38 跳转目标来自 session['login_redirect_url']，而该值在 44 行由 request.GET.get('next') 直接写入；logout 的 58-60 行更直接，GET next 原样进 HttpResponseRedirect。两处均无 is_safe_url。
- critic step 21 `EMAIL-001` 同意。最弱一环：最弱一环是“sender 是否真为用户可控的合法邮箱并被加入收件人”。核实 ContactForm（home/forms.py:8）sender 是 EmailField，只要求格式合法；views.py:42-46 把它 append 进 recipients 并作为发件人发出。匿名、无验证码、无限速确认。
- critic step 21 `DESER-001` 同意。最弱一环：最弱一环是“是否存在可直接控制会话数据入口”——若没有，RCE 就只是潜在风险。我核实了：会话中间件仅从 Cookie 读取 session_key（middleware.py），数据经服务端后端（db/file/cache 系）存取，decode 的输入是服务端存储的 session_data（sessions/models.py:60-67 与 base.py:92-102）；仓库未发现任何 HTTP 入口能写入会话行。finding 本身也如实声明“暂未发现可直接控制会话行的请求入口”并定 low，无夸大。
- critic step 21 `XSS-004` 同意。最弱一环：最弱一环是“响应是否真为可执行 HTML/JS 上下文且文件名未被框架清洗”。核实 ylab/views.py:31-34 与 ydata/views.py:91-95：HttpResponse 默认 text/html，文件名直接 % 拼进 <script> 片段；即便 Django 对 name 做 basename，也只剥路径分隔符，`");alert(1);//` 或 `<img src=x onerror=...>`（不含 `/`）原样保留。
- critic step 5 `FILE-001` 同意，建议 low。最弱一环：最弱一环仍是"是否存在能运行此代码又不做 basename 清洗的运行时"。我核实了 app/ydata/views.py:31-40：视图使用 @login_required、req.FILES['single_file'] 和 f.chunks()，这套上传 API 仅存在于 Django ≥1.0，而这些版本的 UploadedFile._set_name 一律执行 os.path.basename——不存在"能运行此代码又不清洗文件名"的受支持运行时，POSIX 下 `/` 被剥除、Windows 下由 ntpath.basename 处理反斜杠。审计员已采纳上轮 dispute，将可
- critic step 5 `ACCESS-003` 否决，建议 low。最弱一环：最弱一环是"附件所属主题的阅读受版块组权限保护、附件端点绕过了这一保护"这一前提。我核实了：search_code 全仓库 has_access 仅 5 处——ydata/models.py:91（定义）与 wiki/views.py:141/172/192/423，全部是回复/发主题等写操作视图；而主题阅读视图 wiki/views.py:82-103（topic）与 bbs/views.py:45-56（topic）、版块列表 bbs/views.py:31-42 全部没有任何 has_access 调用，匿名用户本就可完整阅读受限版块的主题内容（含经 ylinux_text_filter
- critic step 3 `ACCESS-003` 同意，建议 low。最弱一环：最弱一环是"降级后的影响表述是否与代码事实一致"——上一轮 dispute 指出其原始影响声明（绕过主题侧 has_access 泄露私有版块内容）不成立，因为阅读路径根本不强制 has_access；本轮需核实改写后的表述是否如实。我核实了：show_attachment（ydata/views.py:101-105，仅 @render_to）与 download_attachment（117-149，完全无装饰器，a.dtimes += 1 后 open 文件返回内容）确实无登录与权限校验；ydata/urls.py:7,9 路由存在且 id 为 \d+ 可枚举；Attachment.to
- critic step 3 `ACCESS-004` 同意，建议 medium。最弱一环：最弱一环是"组权限是否真在阅读路径整体失效，而非存在我漏看的全局强制"。我用 search_code 全仓搜索 has_access：仅 5 处匹配——定义（models.py:91）加 4 个调用点，且逐一读取上下文确认 4 个调用点全部是写操作视图（wiki/views.py:141 add_post 回复、172 ajax_add_topic、192 add_topic 发主题、423 replayAJAX 回帖）；逐一通读阅读视图：wiki topic(81-103)、wiki catalog(55-79)、wiki post(119-128)、ajax_topic(105-117)、

## 缺口

- critic step 22 `note_gap` G1：遗漏：XML-RPC metaWeblog.newMediaObject（lib/ylinux_xmlrpc.py:105-127）是任意内容任意扩展名的文件上传——has_auth 只要求任意注册账号（无授权检查，同 AUTHZ-001），os.path.basename 只防穿越，不校验扩展名与内容，文件写入 MEDIA_ROOT/img/ 后在 DEBUG 下经 urls.py:59-63 的 django.views.static.serve 按猜测 MIME 同源提供；上传 .html/.svg 即获得站点域内的存储型脚本执行/任意内容托管。该向量与 XSS-002（附件名注入帖子 HTML）、FILE-001（路径穿越）、XSS-004（self-XSS）均不同源，审计未覆盖。
- critic step 22 `note_gap` G2：遗漏：附件对象级访问控制缺失。主题阅读有版块权限校验（app/wiki/views.py:141 `topic.catalog.has_access(request.user)`），但附件的 show/download 端点（app/ydata/urls.py:7,9 → app/ydata/views.py:101-105、117-149）既无登录要求也不校验所属版块的 groups 权限，id 自增可枚举；被组权限限制的“私有版块”附件可被匿名用户直接按 id 下载，与主题侧的权限模型不一致（IDOR 信息泄露）。该问题在 DEBUG=False 时依然存在，未被 CONFIG-001 的目录索引问题涵盖。
- auditor step 6 `resolve_gap` G1：已读 lib/ylinux_xmlrpc.py 全文核实：new_media（105-127 行）虽经 settings.py:170 注册为 metaWeblog.newMediaObject，但该模块导入段（1-15 行）从未 import settings，而 122-123 行直接引用 settings.MEDIA_ROOT/MEDIA_URL；search_code 确认全模块仅这两处出现 settings。因此调用该方法在写到磁盘之前（122 行先于 124 行 open(target_path,'w')）即抛 NameError，dispatcher 捕获后只返回 Fault，任意内容上传的文件写入实际上不可达，不成立为可利用漏洞，故不新增 finding。若将来补上该 import，将变成“任意注册用户同源上传任意扩展名内容”的问题，修复时应同时补授权校验与扩展名/内容白名
- auditor step 6 `resolve_gap` G2：已核实并新增 ACCESS-003（confirmed，medium，anonymous）：show_attachment（ydata/views.py:101-105）与 download_attachment（117-126）均无登录/权限校验，而附件所属主题受 Catalog.has_access 组权限保护（ydata/models.py:91-101，主题侧 wiki/views.py:141 调用该校验），自增 id 可枚举，匿名可下载受限版块附件，构成 IDOR 信息泄露；该问题在 DEBUG=False 时依然存在，与 CONFIG-001 的目录索引问题相互独立。

## 判为无害的扫描线索

- auditor step 44 L4 判为无害：backends.get_group_permissions 的 SQL 全部标识符经 connection.ops.quote_name 引用，用户值走 cursor.execute(sql, [user_obj.id]) 参数列表，不是字符串拼接注入
- auditor step 44 L7 判为无害：tokens.py 的 default_token_generator 只被 forms.PasswordResetForm.save 的默认参数引用，该 Form 未被任何视图实例化调用（find_references 确认），实际重置流程走 Register.activation_key（已由 CRYPTO-001 记录）
- auditor step 45 L9 判为无害：admin 视图的跳转目标取自 HTTP_REFERER（仅受害者自己浏览器会携带，攻击者不能为受害者设置），且这些端点都有 permission_required；真正的风险是这些端点 GET 即触发写操作，已由 CSRF-001 覆盖
- auditor step 45 L11, L12 判为无害：reboot 端点的命令参数来自 os.popen('whoami') 的固定系统输出，非用户输入；该端点是 permission_required 保护下有意设计的“重启 fastcgi”维护动作，不构成命令注入
- auditor step 45 L13, L14 判为无害：L13：form.errors 中这些字段的校验消息为固定文本，不回显用户输入，且端点有 permission_required。L14：robots 响应是固定字符串
- auditor step 45 L21 判为无害：SHA1 仅用于附件内容去重哈希，不参与认证或完整性保护
- auditor step 45 L22 判为无害：`current` 是 datetime 对象的固定 repr，非用户输入
- auditor step 45 L24 判为无害：XML-RPC 端点逐请求携带用户名密码、不依赖 Cookie 会话，csrf_exempt 合理；全站缺少 CSRF 的问题已由 CSRF-001 记录
