# 关键决策

从 `trace.jsonl` 里抽出来的关键节点，完整过程见 `trajectory.md`。

## 门禁

- auditor step 42 `finalize_report` 通过
- critic step 22 `accept_report` 通过
- auditor step 13 `finalize_report` 通过

## 发现的写入被拒与改判

- auditor step 35 `REDIRECT-001` 写入被拒：evidence quote did not match the file
- auditor step 2 `FILE-001` 改判 confirmed → rejected（low）

## 复核

- critic step 14 `XSS-001` 同意。最弱一环：最弱一环是 markup='none' 路径是否真的不经过任何 HTML 转义（若 ylinux_text_filter 或 Markdown 默认转义则结论不成立）。
- critic step 14 `FILE-001` 否决，建议 low。最弱一环：最弱一环是可达性：文件名中的 ../ 是否真能存活到 open()。f.name 经 Django 上传处理链（UploadedFile）到达视图，而审计员未核实框架对文件名的处理。
- critic step 14 `ACCESS-001` 同意。最弱一环：最弱一环是属主校验是否真缺失——若 editPostAJAX 内有类似 del_post 的 post.user != request.user 检查则发现不成立。
- critic step 14 `CRYPTO-001` 复核被拒：read_file each evidence location with at least 10 lines of context on both sides before judging it
- critic step 14 `ACCESS-002` 否决，建议 high。最弱一环：最站不住的是严重性定级而非事实：审计员自评 medium，但 delete_all_topic 允许任何自助注册账号删除全站所有主题。
- critic step 16 `CRYPTO-001` 同意。最弱一环：最弱一环是"离线枚举"说法：activation_key 只发往受害者邮箱并入库，攻击者无法纯离线比对，必须在线尝试约 2^20 个候选。
- critic step 16 `CSRF-001` 复核被拒：read_file each evidence location with at least 10 lines of context on both sides before judging it
- critic step 16 `ACCESS-003` 同意。最弱一环：最弱一环是入口是否真无认证——若视图或全局中间件有登录要求则 anonymous 不成立。
- critic step 16 `CONFIG-001` 复核被拒：read_file each evidence location with at least 10 lines of context on both sides before judging it
- critic step 16 `CONFIG-002` 复核被拒：read_file each evidence location with at least 10 lines of context on both sides before judging it
- critic step 18 `CSRF-001` 同意。最弱一环：最弱一环是状态变更能否 GET 触发——若 manage_topic 限定 POST，<a href> 跨站触发即不成立。
- critic step 18 `CONFIG-001` 同意。最弱一环：最弱一环是配置是否生效——若部署覆盖 DEBUG 或不走该 static serve 挂载则影响不成立。
- critic step 18 `CONFIG-002` 同意。最弱一环：最弱一环是密钥是否真被安全代码使用——若仅闲置配置则影响有限。
- critic step 18 `CONFIG-003` 同意。最弱一环：最弱一环是该口令当前是否生效——sqlite 引擎下 PASSWORD 完全不参与认证。
- critic step 18 `CRYPTO-002` 复核被拒：read_file each evidence location with at least 10 lines of context on both sides before judging it
- critic step 20 `CRYPTO-002` 同意。最弱一环：最弱一环是哈希构造是否如述（单轮、5 字符盐、无迭代）——已逐行确认。
- critic step 20 `REDIRECT-001` 同意。最弱一环：最弱一环是跳转前是否有站内校验——若存在域名/相对路径白名单则发现不成立；已确认三处均无。
- critic step 20 `DESER-001` 同意。最弱一环：最弱一环是可达性：会话数据存服务端，攻击者无法直接控制被 pickle.loads 的字节流，必须先有会话存储写能力。

## 缺口

- critic step 21 `note_gap` G1：遗漏的同源存储型 XSS 向量：app/ydata/views.py:78-88 上传附件不校验扩展名/Content-Type，文件以原始内容落盘在 MEDIA_ROOT 下；urls.py:59-62 在 DEBUG 下用 django.views.static.serve 直接以 mimetypes 猜测的类型提供 /ymedia/ 内容且不加 Content-Disposition，登录用户上传 .html/.svg 附件后诱导他人访问对应 /ymedia/ydata/attachments/<id>-<uid>-x.html 即在站点源上执行脚本。这与 FILE-001 的路径穿越无关（穿越已被 Django basename 消毒阻断），也与正文 XSS-001 不同，应单独评估。另外 app/ydata/views.py:91-95 上传响应把 attachment.name
- auditor step 6 `resolve_gap` G1：已重新读取 app/ydata/views.py:70-98、app/ydata/settings.py:63-66 与 urls.py:59-62。处理如下：①FILE-001 改判 rejected——f.name 经 Django 上传框架 UploadedFile 的 os.path.basename 消毒后才到达视图，../ 与绝对路径分量已被剥离，路径穿越→任意写不可达；②新增 XSS-002（confirmed，medium，CWE-434）覆盖残余向量：上传不校验扩展名/MIME，文件原样写入 MEDIA_ROOT/ydata/attachments，DEBUG=True 时 /ymedia/ 由 django.views.static.serve 按扩展名猜测 Content-Type 且无 Content-Disposition 提供，登录用户上传 *.html 后诱导（被拒：search_code or read_file the implementation behind this gap before resolving it; do not answer from framework defaults）
- auditor step 8 `resolve_gap` G1：已重读 settings.py:14-22（DEBUG=True）、urls.py:45-64（/ymedia/ 静态服务挂载，DEBUG 生效，无 Content-Disposition 控制）与 app/ydata/views.py:30-99（上传落盘与 AfterSubmit 响应）。处理：①FILE-001 改判 rejected——Django 上传框架在构造 UploadedFile 时对文件名做 os.path.basename 消毒，f.name 到达视图时已无目录分量，路径穿越不可达；②新增 XSS-002（confirmed，medium，CWE-434）：上传不校验扩展名/MIME，内容原样写入 MEDIA_ROOT/ydata/attachments（ydata/views.py:78-84、ydata/settings.py:65），DEBUG=True 时 /（被拒：search_code or read_file the implementation behind this gap before resolving it; do not answer from framework defaults）
- auditor step 10 `resolve_gap` G1：已重读 settings.py:14-22（DEBUG=True 硬编码）、urls.py:45-64（DEBUG 下 /ymedia/(?P<path>.*) 挂到 django.views.static.serve，show_indexes=True，无附加 Content-Disposition/类型限制）、app/ydata/views.py:30-99（上传逻辑与 AfterSubmit 响应）并用 search_code 交叉定位（urls.py:61-62、ydata/views.py:40/78-84/91、ydata/settings.py:65）。处理结果：①FILE-001 改判 rejected——Django 上传框架在构造 UploadedFile 时对 multipart filename 做 os.path.basename 消毒，f.name 到达视图时已

## 判为无害的扫描线索

- auditor step 38 L4 判为无害：backends.py 中 SQL 的 %s 仅用于拼接 quote_name 后的标识符，用户值通过 cursor.execute(sql, [user_obj.id]) 参数化传入，不构成注入。
- auditor step 38 L7 判为无害：tokens.py 的 PasswordResetTokenGenerator 未被实际重置流程使用（视图走 Register.activation_key）；其依赖的 SECRET_KEY 泄露已在 CONFIG-002 记录。
- auditor step 39 L11, L12 判为无害：reboot 视图的命令字符串来自固定字符串拼接 whoami 的返回（系统用户名），不含任何请求输入，不构成命令注入；仅权限面（需要 ydata.delete_catalog）值得注意。
- auditor step 39 L13 判为无害：HttpResponse 输出的 form.errors 是 Django 校验消息（固定文案）、邮件发送返回值等，且该接口需 ydata.delete_catalog 权限，不构成可被利用的反射型 XSS。
- auditor step 39 L14 判为无害：robots.txt 输出为固定字符串，无任何用户输入。
- auditor step 40 L21 判为无害：sha1 仅用于计算上传文件内容的去重指纹，不承担安全职责。
- auditor step 40 L22 判为无害：ylab.time 用反引号输出服务器时间加固定脚本片段，无用户输入。
- auditor step 40 L23 判为无害：ylab 上传测试端点把文件名反射进响应，但响应只返回给上传者本人（自反射型 XSS），且该端点只是实验代码不落盘，无跨用户影响。
- auditor step 40 L24 判为无害：XML-RPC 端点按协议需要 csrf_exempt 且每个方法自带账号密码参数认证；其权限缺失已在 ACCESS-002、明文传输风险在 ACCESS-002 的修复建议中提及。
