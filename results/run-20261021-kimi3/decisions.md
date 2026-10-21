# 关键决策

从 `trace.jsonl` 里抽出来的关键节点，完整过程见 `trajectory.md`。

## 门禁

- auditor step 55 `finalize_report` 被拒：call set_stage for: hunt
- auditor step 57 `finalize_report` 通过

## 发现的写入被拒与改判

- auditor step 42 `XSS-005` 写入被拒：evidence quote did not match the file
- auditor step 48 `CONFIG-003` 写入被拒：evidence quote did not match the file
- auditor step 49 `REDIRECT-001` 写入被拒：evidence quote did not match the file

## 复核

- critic step 12 `XSS-001` 同意。最弱一环：最弱一环是"注册开放（registered_open）"这一攻击者前提是否属实，以及 ylinux_text_filter 是否在 Markdown 之前做了转义。核实结果：account.views.request_register（views.py:63-93）只有 @render_to，无登录要求，匿名即可申请注册链接，注册开放成立；ylinux_text_filter（models.py:396-452）只做 [a:]/[w:]/[i:] 引用替换，不做任何 HTML 转义；lib/markdown/__init__.py:188 确认 safe_mode 默认 False，model
- critic step 12 `XSS-002` 同意。最弱一环：最弱一环是 markup='none' 分支是否真的不转义、以及 urlize() 是否可能充当过滤。核实：models.py:258-260 对 markup='none' 用无 safe_mode 的 Markdown.convert 渲染，原始 HTML 直接通过；:264 的 urlize 只做 URL 自动链接，不转义 HTML；replayAJAX 虽注释掉了 @login_required（views.py:394），但 :399 有手动 is_authenticated() 检查，攻击者仍需登录（registered_open 成立，注册匿名开放）；add_post（:132-
- critic step 12 `XSS-003` 同意。最弱一环：最弱一环是 URL 正则是否允许注入 HTML 元字符。核实 account/urls.py:8 与 :13：两个路由均为 (?P<key>.+)，对字符无任何限制，<、>、"、空格之外的注入字符都可进入 key；views.py:102 与 :208 在 DoesNotExist 分支把 key 用 % 直接拼进 HttpResponseForbidden 的 HTML 字符串返回，无 escape；HttpResponse 默认 text/html。匿名可达，两个端点均无需登录。
- critic step 12 `XSS-004` 否决，建议 low。最弱一环：最弱一环是"可用于向受害者投递脚本"这一反射型 XSS 的可投递性。代码事实成立：ylab/views.py:31-33 把 attachment.name 未转义拼进 innerHTML 与 <script> 响应并以 text/html 返回，ylab/urls.py:7 无任何鉴权，Django 的 UploadedFile basename 清洗不会去掉引号与尖括号。但要让受害者浏览器触发，必须使受害者发出文件名受攻击者控制的 multipart POST 并把响应当作文档渲染：跨站表单无法设置 file input 的文件名（浏览器禁止），XHR/fetch 的响应不会被渲染为文档，
- critic step 13 `FILE-001` 否决，建议 medium。最弱一环：最弱一环是"路径穿越"声明：f.name 直接拼 local_name 看似可注入 ../，但 req.FILES 返回 Django UploadedFile，其 _set_name 自 Django 1.0 起就用 os.path.basename 清洗文件名（本仓库未内置 Django，但代码特征 hashcompat/urls.defaults/patterns 指向 1.3–1.5，均含该清洗），f.name 不可能含路径分隔符，"../../ 覆盖任意文件（如重写主题 .html）"不可达。次弱点：下载接口并非"按扩展名回显即可内联执行"——ydata/views.py:148 明
- critic step 13 `XSS-005` 同意。最弱一环：最弱一环是上传文件名能否真的携带 HTML 元字符到达拼接点。核实：ydata/views.py:78/86 的 f.name 经 Django UploadedFile basename 清洗后仍保留引号/尖括号（basename 只切路径），Attachment.name 原样入库；ylinux_text_filter（models.py:396-452）对 [a:ID]/[i:ID] 的替换把 a.name 直接插进 <a> 标签体、img.name 插进 <img alt="..."> 属性（:408、:444），无任何转义；该 HTML 随正文经无 safe_mode 的 Markd
- critic step 13 `ACCESS-001` 同意。最弱一环：最弱一环是"没有任何属主校验"是否为真。核实 views.py:447-467 全函数：仅 @login_required + get_object_or_404，随后直接把 request.POST['body'] 写入 post.body 并 save()，确实无 post.user == request.user 或权限检查；对照同文件 del_post:277、edit_topic:217 都有 if post/topic.user != request.user: return HttpResponseForbidden，遗漏属实。wiki/urls.py:54 路由存在，注册开放，
- critic step 13 `ACCESS-002` 复核被拒：read_file each evidence location with at least 10 lines of context on both sides before judging it
- critic step 15 `ACCESS-002` 复核被拒：read_file each evidence location with at least 10 lines of context on both sides before judging it
- critic step 15 `ACCESS-003` 同意。最弱一环：最弱一环是"无鉴权无方法限制"是否属实。核实 ylab/views.py:37-48 函数体：无任何装饰器（对照同文件 import 了 login_required/permission_required 却未用），无 req.method 检查，GET 即触发对 Post 全表逐条 p.save()；ylab/urls.py:8 直接暴露该路由。影响仅为 touser/updated 字段被批量改写（updated 重置为 created），不改正文，属于数据完整性骚扰。
- critic step 15 `CSRF-001` 同意。最弱一环：最弱一环是"该版本 Django 需要显式启用 CSRF 中间件、而配置里确实没有"。核实 settings.py:98-104：MIDDLEWARE_CLASSES 只有 CommonMiddleware + 自定义 Session/Authentication 中间件，无 CsrfViewMiddleware；搜索全仓库也无 csrf_protect 装饰器（仅 django_xmlrpc/views.py 有 csrf_exempt，方向相反）；该代码指向 Django 1.3–1.5 时代，CSRF 确实默认不启用。会话认证依赖 Cookie（sessions/middleware.p
- critic step 15 `CRYPTO-001` 复核被拒：read_file each evidence location with at least 10 lines of context on both sides before judging it

## 缺口

无。

## 判为无害的扫描线索

- auditor step 51 L4 判为无害：SQL 标识符经 connection.ops.quote_name 引用，用户 id 走 cursor.execute 的参数列表（%%s + [user_obj.id]），不是注入。
- auditor step 51 L7 判为无害：account/tokens.py 的 default_token_generator 是标准 Django 模式且实际密码重置流程不使用它（用 Register.activation_key），属死代码。
- auditor step 51 L11, L12 判为无害：os.system 的参数来自 whoami 输出（服务器用户名），非请求输入，且视图受 permission_required 保护，不构成命令注入。
- auditor step 51 L13, L14, L22 判为无害：admin 的 form.errors 是 Django 生成的固定错误文案不回声用户原始值，ret 是邮件发送数；robots 为静态文案；ylab time 输出服务器时间戳。均无攻击者可控内容。
- auditor step 51 L21 判为无害：sha1 仅用于附件内容去重比对，不参与安全决策。
