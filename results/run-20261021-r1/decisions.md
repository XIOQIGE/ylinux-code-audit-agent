# 关键决策

从 `trace.jsonl` 自动抽取。完整上下文见 `trajectory.md`。

## 门禁

- auditor step 51 `finalize_report` 通过
- critic step 35 `accept_report` 通过
- auditor step 5 `finalize_report` 通过
- critic step 6 `accept_report` 通过

## 发现的写入被拒与改判

- auditor step 41 `ACCESS-001` 写入被拒：evidence quote did not match the file
- auditor step 45 `FILE-002` 写入被拒：evidence quote did not match the file

## 复核

- critic step 30 `XSS-001` 同意。最弱一环：最弱的一环是"Markdown safe_mode=False 真的不转义原始 HTML、且中途没有其他清洗"。我核对了 lib/markdown/__init__.py:185-189（safe_mode 默认 False）、postprocessors.py:43-59（RawHtmlPostprocessor 在 not self.markdown.safeMode 时把 stash 里的原始 HTML 原样还原）、app/ydata/models.py:258-260（markup='none' 走 Markdown(extensions=['fenced_code']).conver
- critic step 30 `XSS-002` 同意。最弱一环：最弱的一环是"路径参数能否携带 < > 等字符并原样出现在 HTML 响应里"。我核对了 app/account/urls.py:8 的 `(?P<key>.+)/$`（.+ 不限制字符集，Django 1.x 对解码后的路径做正则匹配），app/account/views.py:96-102 与 202-208 两个视图在 Register.DoesNotExist 时用 `u'<h1>错误的 Key ： %s </h1>' % key` 直接字符串格式化进 HttpResponseForbidden，无任何 escape；HttpResponseForbidden 默认 Content-T
- critic step 30 `FILE-001` 同意。最弱一环：最弱的一环是"f.name 是否真能保留 ../ 穿越序列进入 os.path.join"。我核对了 app/ydata/views.py:31-90：upload_single_file 有 @login_required；f.name 取自 req.FILES['single_file'] 后未经 os.path.basename 或任何黑名单，直接进入 local_name = str(id)+'-'+str(req.user.id)+'-'+f.name（:78），再 os.path.join(MEDIA_ROOT, 'ydata/attachments', local_name) 后
- critic step 30 `ACCESS-002` 同意。最弱一环：最弱的一环是"是否真的缺少归属校验"。我核对了 app/wiki/views.py:447-467：editPostAJAX 有 @login_required，但取 post 后直接判断方法并 post.body = post_body; post.save()，全程没有 post.user == request.user 或 topic 归属校验；对比同文件 edit_topic（:217-218）与 del_post（:277-278）都有归属校验，说明此处是遗漏而非设计。路由 app/wiki/urls.py:54 确认 /post/<postID>/editAJAX/ 暴露。
- critic step 30 `ACCESS-001` 同意。最弱一环：最弱的一环是"has_auth 只认证身份、方法对所有权/权限零校验"。我核对了 lib/ylinux_xmlrpc.py:39-45（has_auth 仅 authenticate(username,password)），:47-58 delete_topic（凭自身口令即可删任意 Topic 及其帖子，无 topic.user 校验）、:60-69 delete_all_topic（Topic.objects.all().delete() 无任何权限）、:168-185 edit_topic（改写任意 Topic 的 name 与正文，无归属校验）；settings.py:164-175 
- critic step 30 `CSRF-001` 同意。最弱一环：最弱的一环是"全站确实没有任何 CSRF 防护且存在 GET 可触发的状态变更"。我核对了 settings.py:98-104（MIDDLEWARE_CLASSES 仅 CommonMiddleware + 自定义 Session/Authentication 中间件，无 CsrfViewMiddleware），全仓库 grep csrf_token/csrfmiddlewaretoken/CsrfViewMiddleware 为 0 命中；app/wiki/views.py:271-283 del_post、:237-268 manage_topic、app/admin/views.py:
- critic step 30 `CRYPTO-001` 同意。最弱一环：最弱的一环是"口令确实以单轮 SHA1+5 字符盐存储且在校验路径上真实使用"。我核对了 app/account/models.py:50-66（get_hexdigest：sha1(salt+raw_password) 单轮）、:228-234（set_password：algo='sha1'，salt = get_hexdigest(...)[:5] 即 5 个 hex 字符，生成 '%s$%s$%s'）、:70-76（check_password 按同一算法比较）；Register.create_activate_user 与表单注册/管理员建号均走该 set_password。盐熵 2
- critic step 30 `CRYPTO-002` 同意。最弱一环：最弱的一环是"2^20 枚举是否现实、key 是否真的无过期/无失效"。我核对了 app/account/models.py:424-430（reset_activation_key：salt=sha1(random.random())[:5] 即 5 hex 字符，activation_key=sha1(salt+email)，密钥空间 2^20），app/account/views.py:167-196（匿名可对任意邮箱触发重置/刷新 Register 记录）与 :202-223（password_reset 仅按 key 查库，不检查 updated 时间戳、不限制尝试次数、成功后不删除
- critic step 30 `CONFIG-001` 同意。最弱一环：最弱的一环是"DEBUG=True 是否真实生效并开放媒体目录"。我核对了 settings.py:18-19（DEBUG=True、TEMPLATE_DEBUG=DEBUG）与 urls.py:59-63（settings.DEBUG 为真时注册 /ymedia/ 的 django.views.static.serve，show_indexes=True）；触发例证成立：app/ydata/views.py:138 无条件读取 request.META['HTTP_USER_AGENT']，缺 UA 头时抛 KeyError，DEBUG 下返回含 settings 转储（含 SECRET_K
- critic step 30 `CONFIG-002` 同意。最弱一环：最弱的一环是"公开的 SECRET_KEY 是否足以让会话完整性校验失效，以及 RCE 措辞是否越界"。我核对了 settings.py:79（SECRET_KEY 明文提交）、app/sessions/models.py:13-19 与 backends/base.py:86-98（encode=base64(pickled+md5(pickled+SECRET_KEY))，decode 校验后 pickle.loads）。密钥公开后校验确可被伪造；但 pickle.loads 的代码执行要求攻击者同时能写会话存储（DB 行或会话文件），finding 的 impact 段落明确写了"任何能
- critic step 30 `REDIR-001` 同意。最弱一环：最弱的一环是"next/HTTP_REFERER 是否真的未经校验进入重定向"。我核对了 app/account/views.py:55-60（logout 将 request.GET.get('next') 直接传给 HttpResponseRedirect，无站内校验）与 app/admin/views.py:48-66（管理员登录成功后将 session['previous_url']——来源为 HTTP_REFERER——直接重定向）；login 视图（account/views.py:44/38）的 next→session 跳转同类但未被 finding 单独列明，不影响结论。
- critic step 30 `FILE-002` 同意。最弱一环：最弱的一环是"下载端点确实无鉴权"。我核对了 app/ydata/views.py:117-127：download_attachment 无 @login_required、无权限装饰器，直接 get_object_or_404(Attachment,pk=id) 后 open 读文件并返回；路由 app/ydata/urls.py:9 为 ^attachment/(?P<id>\d+)/download/$，id 自增可枚举。需要指出 impact 里"受限目录下的私有附件"表述偏乐观：wiki/bbs 的读取视图（如 app/wiki/views.py:81-103 topic、:51-
- critic step 30 `MISC-001` 同意。最弱一环：最弱的一环是"端点是否真的匿名可达且全表写库"。我核对了 app/ylab/views.py:37-48（update_post_profile 无装饰器、无方法校验，遍历 Post.objects.all() 改写 touser/updated 并逐条 save()）与 app/ylab/urls.py:5-8（映射到 ^update_post_profile$，根部 urls.py:31 以 ^lab/ 挂载）。GET 即触发，匿名成立。
- critic step 30 `CONFIG-003` 同意。最弱一环：最弱的一环是"该凭据当前是否生效"。我核对了 settings.py:42-53：生效 ENGINE 为 sqlite3（NAME='ylinux'，HOST/PORT 为空），USER='ylinux'、PASSWORD='123456' 对 sqlite 不起作用，mysql ENGINE 被注释。finding 自己也如实标注"当前 sqlite 未生效"，没有把它当高危。
- critic step 5 `ACCESS-003` 同意。最弱一环：最弱的一环是"读侧真的从未调用 has_access、也没有中间件/装饰器兜底"。我做了全库正则搜索，has_access 的调用点只有 4 处且全部在写路径（app/wiki/views.py:141/172/192/423）；逐一读窗口核实读视图：wiki topic（81-103）、catalog（51-79）、post（119-128）只有 @render_to，ajax_show_posts（368-388）连装饰器都没有，bbs catalog/topic（app/bbs/views.py:30-56）与 download_attachment（app/ydata/views.py

## 缺口

- critic step 34 `note_gap` G1：Catalog 组权限（Catalog.groups + has_access，app/ydata/models.py:91-101）只在写路径上被强制（app/wiki/views.py:141 add_post、:172/:192 add_topic、:423 replayAJAX），所有读取路径都没有调用 has_access：wiki 的 topic（:81-103）、post（:119-128）、catalog（:51-79）、ajax_show_posts（:368-388，匿名渲染全部回复的 body_html）、bbs 的 topic/catalog（app/bbs/views.py:30-56）以及 ydata 的附件下载（app/ydata/views.py:117-127）。结果是"组内可见"的受限目录内容（主题、回复、附件）可以被任何匿名访客直接读取/下载，访问控制
- auditor step 4 `resolve_gap` G1：已核实并单独成条：find_references 确认 has_access 仅被 4 个写路径调用（app/wiki/views.py:141/172/192/423），所有读路径（wiki topic/catalog/post/ajax_show_posts、bbs catalog/topic、ydata download_attachment）均不校验组权限且匿名可达。新增 ACCESS-003（读侧越权，medium，anonymous），证据引用 app/ydata/models.py:91-101、app/wiki/views.py:81-96 与 368-388。

## 判为无害的扫描线索

- auditor step 48 L4 判为无害：backends.py:43-57 中所有插入内容均为 connection.ops.quote_name 引用的固定标识符，用户值经 cursor.execute(sql, [user_obj.id]) 参数化传入，不存在注入。
- auditor step 48 L7 判为无害：tokens.py 的 default_token_generator 未被任何视图调用（PasswordResetForm 无引用，实际重置流程使用 Register.activation_key），属死代码。
- auditor step 48 L11, L12 判为无害：os.popen('whoami')/os.system('killall -u %s') 的参数来自 whoami 输出而非请求输入，属固定命令；且 reboot 视图有 permission_required('ydata.delete_catalog') 保护，不构成注入。
- auditor step 49 L13 判为无害：admin/views.py:400 将 form.errors 原样返回，端点虽需权限（已并入 CSRF/GET 写问题），但 Django 1.x 表单错误信息不直接回显用户输入值，无法构成可利用的反射 XSS；因该 GET 写端点问题已由 CSRF-001 覆盖，此处按 benign 处理 XSS 线索。
- auditor step 49 L14 判为无害：home/views.py:77 robots 返回固定字符串，无用户输入。
- auditor step 49 L21 判为无害：ydata/views.py:52-55 的 SHA1 仅用于文件去重（相同内容不重复存储），不用于完整性/认证，弱哈希不构成风险。
- auditor step 49 L22 判为无害：ylab time 视图用反引号输出 datetime 的 repr，无任何用户输入。
- auditor step 49 L23 判为无害：ylab/views.py:31-34 回显的文件名只能来自受害者本机上传的文件，属 self-XSS，无法跨用户触发；且该端点不保存文件，仅调试用途。
- auditor step 49 L24 判为无害：XML-RPC 接口以方法参数携带用户名口令认证、不依赖 Cookie 会话，csrf_exempt 合理；全站缺少 CSRF 中间件的问题已由 CSRF-001 记录。
