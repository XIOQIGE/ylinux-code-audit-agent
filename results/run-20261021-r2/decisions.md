# 关键决策

从 `trace.jsonl` 里抽出来的关键节点，完整过程见 `trajectory.md`。

## 门禁

- auditor step 50 `finalize_report` 通过
- critic step 18 `accept_report` 通过

## 发现的写入被拒与改判

- auditor step 44 `ACL-002` 写入被拒：evidence quote did not match the file

## 复核

- critic step 15 `XSS-001` 同意。最弱一环：最站不住的一环是"不带 safe_mode 就必然原样还原用户 HTML"这条因果链。我核实了：lib/markdown/__init__.py:185-212 中 Markdown.__init__ 默认 safe_mode=False；preprocessors.py:56-75 的 HtmlStash.store(html, safe=False) 把原始 HTML 块存进 rawHtmlBlocks；postprocessors.py:43-60 在 "safe or not self.markdown.safeMode" 时把占位符原样替换回 HTML——因果成立。同时确认 ylin
- critic step 15 `FILE-001` 同意。最弱一环：最站不住的一环是"os.path.join 是否真能被 ../ 穿越"。核实 app/ydata/views.py:31-84：从 req.FILES['single_file'] 取到的 f.name 是客户端 multipart 文件名（Django UploadedFile.name 不做路径清洗），第 78 行直接拼进 local_name，79-81 行与 MEDIA_ROOT/'ydata/attachments' 做 os.path.join 后 open('wb+')，中间没有任何 basename/白名单/字符校验。os.path.join 不规范化路径，'../' 段交由 
- critic step 15 `ACL-001` 复核被拒：read_file each evidence location with at least 10 lines of context on both sides before judging it
- critic step 15 `CSRF-001` 同意。最弱一环：最站不住的一环是"自定义 Session/Auth 中间件是否可能暗含 CSRF 校验"。核实 settings.py:98-104：MIDDLEWARE_CLASSES 仅 CommonMiddleware + ylinux.app.sessions.middleware.SessionMiddleware + ylinux.app.account.middleware.AuthenticationMiddleware，无 CsrfViewMiddleware；通读两个自定义中间件（app/sessions/middleware.py:8-42、app/account/middleware.
- critic step 15 `ACL-002` 同意。最弱一环：最站不住的一环是"是否存在隐藏的属主校验"。核实 app/wiki/views.py:447-467：GET 分支仅返回渲染数据，POST 分支取 body 后直接 post.body=post_body; post.save()，全程只有 @login_required，从未比较 post.user 与 request.user；同文件 manage_topic:242 与 del_post:277 均做了属主检查，证明此处是遗漏而非设计。模板里的"仅属主显示编辑按钮"只是客户端隐藏，不构成服务端授权。
- critic step 15 `XSS-002` 同意。最弱一环：最站不住的一环是"URL 路径里的 payload 能否原样进入 HTML 响应"。核实 app/account/urls.py:8、13 的正则 (?P<key>.+)/$：.+ 贪婪匹配可含斜杠（仅要求以 / 结尾），所以 <script>alert(document.cookie)</script> 这类带 / 的 payload 也能成为 key；Django 对 PATH_INFO 做百分号解码，%3C 等还原为 <；app/account/views.py:96-102、202-208 在 Register 查无时用 % 把 key 原样拼进 HttpResponseForbidd
- critic step 15 `REDIR-001` 同意。最弱一环：最站不住的一环是 login 分支"受害者必须完成登录才会跳转"。核实 app/account/views.py:42-44 把 GET 参数 next 存入会话、38 行登录成功后 HttpResponseRedirect(request.session.get('login_redirect_url','/'))；logout（55-60 行）直接 HttpResponseRedirect(request.GET.get('next') or '/')，匿名即可触发；admin login（admin/views.py:62-66）把 HTTP_REFERER 存入会话用于登录后跳转（浏览
- critic step 15 `CRYPTO-001` 同意。最弱一环：最站不住的一环是严重性是否偏高——它确实以数据库泄露为前提。核实 app/account/models.py:62-66（md5/sha1 单轮、无迭代）、228-234（盐 = get_hexdigest('sha1', str(random.random()), str(random.random()))[:5]，即 5 个十六进制字符 ≈20 位熵）、241-250（兼容无盐 MD5）。单轮 SHA1 + 20 位盐的离线抗破解能力弱是事实，CWE-916 成立；结合本仓库 DB/SECRET_KEY 泄露场景（CONFIG-002），medium 恰当，不算偏高。
- critic step 15 `CRYPTO-002` 复核被拒：read_file each evidence location with at least 10 lines of context on both sides before judging it
- critic step 15 `CONFIG-001` 同意。最弱一环：最站不住的一环是"是否真的暴露在生产"。核实 settings.py:18-20 硬编码 DEBUG=True（仓库内无生产覆写），urls.py:59-63 依据 DEBUG 挂载 django.views.static.serve(document_root=MEDIA_ROOT, show_indexes=True)。只要按仓库配置运行（无论是否"生产"），/ymedia/ 即带目录列举、上传文件按原 mimetype 直接提供，未捕获异常还会回显完整调试页（泄露路径、SQL、局部变量）。配置确实生效。
- critic step 15 `CONFIG-002` 同意。最弱一环：最站不住的一环是"DB 口令泄露导致直连数据库"这一半影响。核实 settings.py:42-49：ENGINE 为 django.db.backends.sqlite3，sqlite 不使用 USER/PASSWORD，'123456' 在本地 sqlite 下根本不参与认证——该影响只有在其被注释掉的 mysql 引擎启用时才成立。但 SECRET_KEY（settings.py:79）硬编码入库是实的：app/sessions/models.py 的会话完整性 MD5(pickled+SECRET_KEY)、app/account/tokens.py:54 的重置 token SHA1
- critic step 15 `LAB-001` 复核被拒：read_file each evidence location with at least 10 lines of context on both sides before judging it
- critic step 17 `ACL-001` 同意。最弱一环：最站不住的一环是"这些方法真的被暴露且派发层不加授权"。核实：urls.py:45-48 注册 r'^xmlrpc/$' → django_xmlrpc.views.handle_xmlrpc（views.py:73-92，仅 POST 后 _marshaled_dispatch）；lib/django_xmlrpc/dispatcher.py 继承 SimpleXMLRPCDispatcher，无任何权限层；settings.py:164-174 注册了 delete_topic/delete_all_topic/edit_topic；lib/ylinux_xmlrpc.py:39-69、1
- critic step 17 `CRYPTO-002` 同意。最弱一环：最站不住的一环是"2^20 在线爆破是否可行、是否有 oracle"。核实 app/account/models.py:361-369、424-430：key = sha1(salt+email)，salt 为 sha1(str(random.random())) 的十六进制前 5 字符，候选空间 16^5≈1,048,576；password_reset_request（views.py:167-198）匿名可为目标邮箱创建/重置 Register 行（email 需已注册为 User）；password_reset（views.py:201-223）对错误 key 返回 403（208 行
- critic step 17 `LAB-001` 同意。最弱一环：最站不住的一环是"文件名反射 XSS"的利用面。核实 app/ylab/views.py:24-34：响应只返回给提交请求者本人（响应进入自己的父帧），属自 XSS 而非对第三方受害者的反射/存储 XSS，且 uploadsf 并不落盘；update_post_profile（37-48 行）为匿名 GET 即触发的全表遍历改写（touser/updated 字段 + 每条 p.save()），影响真实但限于这两个字段。因此 low 是恰当定级，而非 medium 以上。

## 缺口

无。

## 判为无害的扫描线索

- auditor step 49 L4 判为无害：SQL 仅用 %s 拼接经 connection.ops.quote_name 引用的表/列标识符，user_id 经 cursor.execute 参数列表绑定，不构成注入。
- auditor step 49 L11, L12 判为无害：whoami 为固定命令，killall 参数来自 whoami 输出而非请求输入，无命令注入；该端点 GET 触发且无 CSRF 的问题由 CSRF-001 覆盖。
- auditor step 49 L13, L14 判为无害：L13 输出的是框架生成的 form.errors/邮件返回码（非攻击者控制的 HTML 原文），且端点为特权接口；L14 为固定 robots 文本。
- auditor step 49 L15, L16, L17, L18 判为无害：会话数据 pickle 存于服务端数据库，客户端只有随机会话 key，无法把可控字节送入 pickle.loads；MD5(SECRET_KEY) 校验是服务端完整性检查，密钥泄露影响已记入 CONFIG-002。
- auditor step 49 L21, L22 判为无害：L21 的 SHA1 仅用于附件内容去重指纹；L22 输出为 datetime 的 repr 拼接固定脚本，均不含不可信输入。
