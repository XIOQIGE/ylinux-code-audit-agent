# 关键决策

从 `trace.jsonl` 自动抽取。完整上下文见 `trajectory.md`。

## 门禁

- auditor step 37 `finalize_report` 被拒：call set_stage for: hunt
- auditor step 39 `finalize_report` 通过
- critic step 12 `accept_report` 通过
- auditor step 5 `finalize_report` 通过
- critic step 5 `accept_report` 通过

## 发现的写入被拒与改判

- auditor step 27 `XSS-001` 写入被拒：evidence quote did not match the file
- auditor step 27 `XSS-002` 写入被拒：evidence quote did not match the file
- auditor step 28 `XSS-001` 写入被拒：evidence quote did not match the file
- auditor step 2 `ACCESS-003` 写入被拒：evidence quote did not match the file

## 复核

- critic step 8 `CMDI-001` 同意。最弱一环：最需要核实的是"匿名可达且 title 原样进入 os.system"。我重读了 views.py:170-201：upload 视图对 GET/POST 均无 is_authenticated 检查，GET 分支把带 {% csrf_token %} 的 upload.html（第 13 行）返回给匿名者，token 可取得；misc.py:33-39 把 title 无引号、无转义直接拼进 "mv ... dir/title"。第二条入口 profile_by_id（views.py:710-732，@csrf_exempt）在 728-730 用 POST 可控的 user.userna
- critic step 8 `SQLI-001` 同意。最弱一环：最需核实的是 name/upload_path 是否真的未转义进入 SQL 语句。重读 views.py:181-185：INSERT 用 % 直接把 name 与 upload_path（misc.py:41 派生自 name）格式化进语句后交 connection.cursor().execute，值周围只有单引号、无任何转义或参数化；name 含单引号即可闭合字符串并注入，即使 sqlite3 单语句执行，也能改写 INSERT 的 values（如写任意 path），发现所述影响成立。
- critic step 8 `FILE-001` 同意。最弱一环：最需核实的是 file.path 能否真的带出 uploads 目录。misc.py:41 返回 '/static/taskManager/uploads/%s' % title，title 含 ../ 时 open(模块目录 + file.path)（views.py:209-213）经路径归一化即可逃出；叠加 SQLI-001 还能直接写任意 path。download 视图 206-217 无 is_authenticated、无归属校验，直接回读。
- critic step 8 `SESSION-001` 同意。最弱一环：最需核实的是"已知 SECRET_KEY + signed_cookies + PickleSerializer ⇒ 攻击者自签 pickle 被执行"。settings.py:24 硬编码密钥、104 用 signed_cookies、109 用 PickleSerializer，三者同文件实锤；Django 1.8 的签名校验只验证 HMAC，验签后即 pickle.loads，攻击者持密钥可伪造任意会话并触发反序列化 RCE，链条成立。
- critic step 8 `AUTH-001` 复核被拒：read_file each evidence location with at least 10 lines of context on both sides before judging it
- critic step 8 `AUTH-002` 同意。最弱一环：最需核实的是该视图是否真的既无登录校验也无"只能改自己"校验、且 password 直接落库。views.py:710-732 实锤：@csrf_exempt、无 is_authenticated、User.objects.get(pk=user_id) 取任意用户、726-727 对 POST password 直接 set_password 并 save；form.is_valid() 门槛仅 ProfileForm（first_name/last_name/email/picture 全可选），匿名 POST 可通过。
- critic step 8 `ACCESS-001` 同意。最弱一环：最需核实的是 POST 分支是否真的缺 can_change_group、且 admin_g 是否有实际特权。views.py:116-138 POST 分支只查 is_authenticated() 就直接 groups.add；同函数 GET 分支（155）才有 has_perm('can_change_group')。admin_g 在 dashboard/profile_view/task_details（views.py:471、497、603）授予 admin_level/角色与任务可见性旁路，提权有实际含义。注册开放使"任意登录用户"门槛极低。
- critic step 8 `ACCESS-002` 同意。最弱一环：最需核实的是这些端点是否确实全部无鉴权、且删除端点可用 GET 触发。task_delete(299-306)、task_complete(311-319) 无任何 is_authenticated/归属检查；project_delete(376-380) 直接 delete 且可 GET 触发；task_edit(273-294)、project_edit(350-371)、note_edit(554-576)、note_delete(581-590) 同样只按 pk 取对象后写/删，唯一条件校验是 task.project==proj 这类对象关系，而非请求者身份。
- critic step 8 `XSS-003` 复核被拒：read_file each evidence location with at least 10 lines of context on both sides before judging it
- critic step 8 `XSS-004` 复核被拒：read_file each evidence location with at least 10 lines of context on both sides before judging it
- critic step 8 `XSS-002` 复核被拒：read_file each evidence location with at least 10 lines of context on both sides before judging it
- critic step 8 `XSS-001` 复核被拒：read_file each evidence location with at least 10 lines of context on both sides before judging it
- critic step 8 `CSRF-001` 同意。最弱一环：最需核实的是 csrf_exempt 是否真的使改密免 CSRF 校验，以及跨站表单能否指定新密码。views.py:710 的 @csrf_exempt 对该视图整体生效（CsrfViewMiddleware 在 settings.py:47 已启用，仅此处豁免）；726-727 用 POST password 直接 set_password。攻击者页自动提交的表单可携带任意 password 值，浏览器自动带 Cookie，改密成立。
- critic step 8 `CRYPTO-001` 同意。最弱一环：最需核实的是 PASSWORD_HASHERS 覆盖是否生效、fixture 口令是否为 md5$ 形式。settings.py:101 明确指定 MD5PasswordHasher 为唯一 hasher，所有 set_password 产出加盐 MD5；fixtures/users.json:9 的 admin 口令正是 md5$<salt>$<hash> 格式。离线破解成本低属实。
- critic step 8 `CONFIG-002` 同意。最弱一环：最需核实的是该密钥是否真的被框架签名机制使用（否则只是摆设）。settings.py:24 硬编码 SECRET_KEY，settings.py:104 SESSION_ENGINE=signed_cookies 用该密钥对会话签名，同文件闭环；仓库内明文即对所有能看代码者公开。
- critic step 8 `CONFIG-001` 同意。最弱一环：最需核实的是 DEBUG/TEMPLATE_DEBUG 是否真的被提交且无环境覆盖。settings.py:28-29 明文置 True，无环境变量回退，ALLOWED_HOSTS=[]（31 行）印证未按生产标准部署；DEBUG=True 时 Django 1.8 的异常页会回显堆栈、局部变量与 settings 内容。
- critic step 8 `CONFIG-003` 同意。最弱一环：最需核实的是该配置是否真实存在并覆盖 Django 默认值（True）。settings.py:110 显式 SESSION_COOKIE_HTTPONLY=False，确实关闭了默认保护，document.cookie 可读 sessionid。
- critic step 8 `REDIRECT-001` 同意。最弱一环：最需核实的是 Django 1.8.3 的 redirect() 是否真的不校验目标。logout_view（views.py:385-387）把 GET 参数 redirect 原样传入；Django 1.8.3 的 redirect() 对 scheme/host 无 is_safe_url 类校验（该校验是后续版本才加入的），//evil.example 或 https://evil.example 会 302 到外部。
- critic step 8 `FILE-002` 同意。最弱一环：最需核实的是写入目录是否真在静态伺服范围内、文件名/扩展名是否全无校验。misc.py:24-41：upload_dir 为 taskManager/static/taskManager/uploads（staticfiles 的 AppDirectoriesFinder 在 DEBUG 下伺服 app 的 static 目录），返回路径 '/static/taskManager/uploads/%s'；title 无白名单、无扩展名/内容校验，../ 与任意 .html 均可写；settings.py:58-59 强制 TemporaryFileUploadHandler，temp 源文件存
- critic step 8 `COMP-001` 同意。最弱一环：最需核实的是版本是否确为 1.8.3 且已 EOL。requirements.txt:1 固定 Django==1.8.3；1.8 系列早已停止安全支持，后续版本的修复（含 redirect 校验等）均未包含，事实无误。
- critic step 10 `AUTH-001` 同意。最弱一环：最需核实的是 ModelForm 是否真的把 is_superuser/is_staff 纳入字段并落库。重读 forms.py:71-75：exclude 仅列 groups/user_permissions/last_login/date_joined/is_active，is_superuser、is_staff 未被排除、必被 ModelForm 自动生成；register（views.py:429-434）user_form.save() 后 445 行 user.save() 持久化，POST 附带的值生效。
- critic step 10 `XSS-003` 同意。最弱一环：最需核实的是 |safe 确在渲染处、且写入端无鉴权。task_details.html 第 12 行 {{task.title|safe}}、第 48 行 {{task.text|safe}} 实锤；task_create（views.py:246-261）与 task_edit（282-289）均无登录检查，POST 值直存数据库。
- critic step 10 `XSS-004` 同意。最弱一环：最需核实的是 username 是否可被攻击者写为脚本、且确实以 |safe 输出。tutorials/base.html:53-54 与 base_backend.html:57-58 均无转义输出 username；profile_by_id（views.py:718-719）@csrf_exempt、无鉴权地把 POST username 写入任意用户。
- critic step 10 `XSS-002` 同意。最弱一环：最需核实的是攻击者能否把可控值塞进 request.META 并以 |safe 回显。settings.html:28 {{v|safe}} 在 {% for n,v in settings.items %} 循环里输出全部值，settings 即 views.py:838 的 request.META；Django 1.8 对 HTTP_* 头不做 HTML 清洗。
- critic step 10 `XSS-001` 同意。最弱一环：最需核实的是 href 属性内的 |safe 能否被属性逃逸利用。search.html:14 把 GET 参数 q 原样放入 href="/taskManager/search/?q={{q|safe}}"，无任何 URL 编码或转义；q 来自 views.py:662 的 request.GET.get('q','')。
- critic step 4 `RESET-001` 同意。最弱一环：最站不住的一环是"令牌空间≤10^6 且可在 10 分钟内无限制枚举"。我重读了 views.py:779-809：README.md:8/16 要求 Python 3.4+/python3，因此 os.urandom(6) 返回 bytes、迭代得 0-255 的整数、str(x) 为十进制串，res[:6] 恒为 6 位十进制数字，空间上界确为 10^6（实际分布还小于此，只对攻击者更有利）；有效期 10 分钟在 views.py:796 实锤。再看 views.py:739-775 的 reset_password：@csrf_exempt（739）、全程无 is_authenticat
- critic step 4 `ACCESS-003` 同意。最弱一环：最站不住的一环是"assigned_to/logged_in 只是界面标记、不构成访问控制，内容仍无条件渲染"。我重读了 views.py:593-625：logged_in（599-600）、admin_level、pmanager_level、assigned_to 全部只是计算出的布尔值塞进模板上下文，视图里没有任何权限分支、无 redirect、无 is_authenticated 门槛；task = Task.objects.get(pk=task_id)（595）只按 task_id 取值，project_id 参数甚至完全未参与校验。再看 task_details.html 全文

## 缺口

- critic step 11 `note_gap` G1：弱口令重置令牌可暴力破解：forgot_password（taskManager/views.py:788-794）把 os.urandom(6) 各字节的十进制串取前 6 位作为重置令牌（空间约 10^6、有效期 10 分钟），reset_password（views.py:739-775）为匿名 + @csrf_exempt 且无速率限制/失败锁定，知道目标邮箱即可在窗口内枚举令牌改掉任意账户密码（账户接管）。现有发现只覆盖了哈希强度（CRYPTO-001），未记录该令牌熵/限速问题。
- critic step 11 `note_gap` G2：读侧 IDOR 未记录：task_details（taskManager/views.py:593-625）对任意 task_id 直接 Task.objects.get 并渲染，assigned_to/logged_in 只是传给模板的界面标记、不构成访问控制，匿名者可读取任意任务内容（标题/正文又以 |safe 渲染，与 XSS-003 叠加）；profile_view（views.py:491-508）同样把任意用户资料暴露给任何访问者。审计员只记录了写侧 IDOR（ACCESS-002），读侧数据暴露漏掉。
- auditor step 4 `resolve_gap` G1：已重读 views.py:739-809 与 README.md。README 明确要求 Python 3.4+（README.md:8、16），因此在 Python 3 下 os.urandom(6) 返回 bytes、迭代得 int、str(x) 是十进制串，reset_token=res[:6] 是 6 位十进制数字（空间≤10^6）；有效期 10 分钟且 reset_password 匿名 + @csrf_exempt、无任何速率限制/失败锁定。已新增 finding RESET-001（high，CWE-307）记录该暴力枚举令牌导致的账户接管。
- auditor step 4 `resolve_gap` G2：已重读 views.py:491-508 与 593-625：task_details 按 task_id 直接取对象渲染，assigned_to/logged_in/admin_level 仅为布尔标记、未做任何权限分支；profile_view 按 user_id 直接渲染任意用户资料。已新增 finding ACCESS-003（medium，CWE-639）记录读侧 IDOR。

## 判为无害的扫描线索

- auditor step 35 L1 判为无害：fixtures/taskManagerNotes.json 中的 <script> 与 {% autoescape off %} 只是演示种子数据；task_details.html 第 81/84 行用普通 {{ }}（自动转义）渲染 Notes.title/text，不会执行，不构成 XSS。
- auditor step 35 L12, L13, L14, L15, L16 判为无害：已读 tutorials/partials/base.html、csrf.html、injection.html、xss.html：均为教程说明文档，代码片段以 &lt;/&#123; 等 HTML 实体转义后展示，不是可注入的模板输出，与真实漏洞无关。
