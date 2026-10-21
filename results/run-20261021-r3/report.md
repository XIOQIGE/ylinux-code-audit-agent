# ylinux_old 应用安全审计报告

- 目标：`https://github.com/gwind/ylinux_old`，commit `8a7316deec88287d020eca21c38dad921b623ffc`
- 模型：审计员 `deepseek-v4-pro`，复核员 `deepseek-v4-pro`
- 时间：2026-10-21T09:28:29+08:00 → 2026-10-21T09:44:40+08:00
- 结论：确认 16 个问题，最高严重性为 high。
- 统计：已确认 16，待再确认 0，已排除 0；引用核对 46 条，未通过 0 条

## 发现总表

| 严重性 | 编号 | 问题 | 入口身份 | 状态 | 复核员 | 位置 |
| --- | --- | --- | --- | --- | --- | --- |
| high | [`ACCESS-002`](#finding-access-002) | XML-RPC 接口仅认证不鉴权：任意注册用户可删除全部主题或改写任意主题 | 可自助注册的用户 | confirmed | 同意 | `lib/ylinux_xmlrpc.py:39` |
| high | [`CRYPTO-002`](#finding-crypto-002) | 注册/重置令牌熵仅约 20 bit 且无时效与速率限制，可枚举接管任意账号 | 匿名 | confirmed | 同意 | `app/account/models.py:361` |
| high | [`FILE-001`](#finding-file-001) | 附件上传文件名未消毒导致路径穿越任意文件写入 | 可自助注册的用户 | confirmed | 同意 | `app/ydata/views.py:40` |
| high | [`XSS-001`](#finding-xss-001) | 主题与回复正文存储型 XSS（Markdown 未启用 safe_mode，模板 \|safe 渲染） | 可自助注册的用户 | confirmed | 同意 | `app/wiki/views.py:432` |
| medium | [`ACCESS-001`](#finding-access-001) | editPostAJAX 缺少所有权校验，任意登录用户可编辑他人回复（IDOR） | 可自助注册的用户 | confirmed | 同意 | `app/wiki/views.py:447` |
| medium | [`CONFIG-001`](#finding-config-001) | DEBUG=True 提交进仓库并暴露 MEDIA_ROOT 目录浏览 | 无请求入口 | confirmed | 同意 | `settings.py:18` |
| medium | [`CONFIG-002`](#finding-config-002) | SECRET_KEY 硬编码进仓库，会话签名与密码重置令牌可被伪造 | 无请求入口 | confirmed | 同意 | `settings.py:78` |
| medium | [`CRYPTO-001`](#finding-crypto-001) | 密码使用弱哈希（单轮 SHA1 + 短弱随机盐） | 可自助注册的用户 | confirmed | 同意 | `app/account/models.py:62` |
| medium | [`CSRF-001`](#finding-csrf-001) | 全站缺少 CSRF 防护，状态变更接口可被跨站请求伪造 | 可自助注册的用户 | confirmed | 同意 | `settings.py:98` |
| medium | [`FILE-002`](#finding-file-002) | 上传无类型白名单且落盘同源静态目录，可上传 HTML/SVG 形成同源存储型 XSS | 可自助注册的用户 | confirmed | 同意 | `app/ydata/views.py:77` |
| medium | [`REDIRECT-001`](#finding-redirect-001) | logout/login 流程的 next 与 Referer 参数导致开放重定向 | 匿名 | confirmed | 同意 | `app/account/views.py:55` |
| medium | [`XSS-002`](#finding-xss-002) | 注册/密码重置视图对 URL key 未转义导致的反射型 XSS | 匿名 | confirmed | 同意 | `app/account/urls.py:8` |
| medium | [`XSS-003`](#finding-xss-003) | 上传文件名未转义嵌入响应脚本导致的 XSS（ylab/ydata 上传视图） | 匿名 | confirmed | 同意 | `app/ydata/views.py:91` |
| low | [`ACCESS-003`](#finding-access-003) | ylab update_post_profile 未鉴权的全表写操作 | 匿名 | confirmed | 同意 | `app/ylab/views.py:37` |
| low | [`CONFIG-003`](#finding-config-003) | 数据库与邮件凭据以明文弱口令形式提交进仓库 | 无请求入口 | confirmed | 同意 | `settings.py:42` |
| low | [`SENSITIVE-001`](#finding-sensitive-001) | AddUserForm 创建用户时口令未哈希（明文/空口令入库） | 管理员或特权用户 | confirmed | 同意 | `app/admin/forms.py:84` |

发现列表来自 Agent 写入并经过引用核对的结构化结果。审计员综述写于复核之前，单条发现的状态以复核之后为准。线索处置、读过的文件、阶段记录、工具序列和逐条引用核对见 `appendix.md`；关键决策摘要见 `decisions.md`。

## 审计员综述

这是一个基于旧版 Django（django.conf.urls.defaults，约 1.3 时代）的论坛/Wiki 站点，自实现会话与认证系统。整体安全基线很差：全站没有 CSRF 防护、DEBUG=True 与硬编码 SECRET_KEY/数据库弱口令直接提交进仓库；内容渲染链路（markdown 无 safe_mode + 模板 |safe）形成可由任意自助注册用户写入的存储型 XSS；上传接口把客户端文件名直接拼进路径（路径穿越任意文件写入）、嵌入响应脚本（反射 XSS），且无类型白名单地落盘到同源静态目录（可上传 HTML/SVG 形成持久 XSS）；XML-RPC 接口只认证不鉴权，普通用户即可删除全部主题；注册/密码重置令牌熵仅约 20 bit 且无时效与速率限制，可通过枚举重置链接接管任意账号；另有 editPostAJAX 越权编辑他人回复、logout/login 开放重定向、未鉴权的全表写调试视图、单轮 SHA1 弱口令哈希等。综合评估：若以仓库当前配置直接部署，站点面临内容篡改、会话劫持、账户接管与数据毁灭等高风险。

## 风险概览

最高风险依次为：1) 存储型 XSS（XSS-001，注册用户写入、匿名访客/管理员执行，配合非 HttpOnly 会话 Cookie 可接管账号）；2) 密码重置令牌弱熵枚举（CRYPTO-002，知道邮箱即可 ~10^6 请求枚举重置链接并接管任意账号）；3) 上传路径穿越任意文件写入（FILE-001，可覆盖站点模板实现全站控制）；4) XML-RPC 越权（ACCESS-002，任意用户删除全部主题/改写任意主题）；5) 上传无类型白名单 + 同源静态服务（FILE-002，上传 HTML/SVG 形成持久 XSS/钓鱼托管）；6) 全站无 CSRF 防护（CSRF-001，含管理员接口）；7) 反射 XSS 两处（XSS-002 匿名、XSS-003 上传文件名）；8) 配置类问题（DEBUG/静态目录浏览、SECRET_KEY、弱数据库口令）与单轮 SHA1 弱口令哈希（CRYPTO-001）使数据库泄露后口令可被快速爆破。

## 已确认的问题

<a id="finding-access-002"></a>

### [HIGH] XML-RPC 接口仅认证不鉴权：任意注册用户可删除全部主题或改写任意主题

- 编号：`ACCESS-002`
- 类别：`access_control`
- CWE：`CWE-862`
- 入口身份：可自助注册的用户
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

公开 XML-RPC 接口（/xmlrpc/，csrf_exempt）只验证“用户名密码有效”（has_auth 仅调用 authenticate），不校验任何权限或对象归属：delete_topic/delete_all_topic/edit_topic 允许任何普通注册用户删除任意/全部主题、改写任意主题正文。这与 Web 界面对删除/编辑均做所有权检查形成鲜明对比。

**触发条件。** 用任意有效账号密码调用 metaWeblog.editPost、delete_topic 或 delete_all_topic（POST /xmlrpc/）。

**数据流。** 来源：XML-RPC 调用参数（user/passwd/id/struct，经 POST /xmlrpc/ 的 request.raw_post_data 由 SimpleXMLRPCDispatcher 分发，lib/django_xmlrpc/views.py:85-87）→ 中间环节：has_auth(user, passwd) 只调用 authenticate 校验“凭据有效”（lib/ylinux_xmlrpc.py:39-45），不校验权限或归属 → 危险点：delete_topic 按传入 id 删除任意主题（lib/ylinux_xmlrpc.py:52-55），delete_all_topic 删除全部主题（lib/ylinux_xmlrpc.py:65-66），edit_topic 修改任意主题正文（lib/ylinux_xmlrpc.py:173-181）。这些方法在 settings.py:164-174 被注册为公开 XML-RPC 方法。入口：任何持有有效账号密码的人（注册自助开放），凭证经明文 HTTP 传输。

**影响。** 任何普通注册用户可通过 XML-RPC 删除单个或全部主题、修改任意主题内容（并可借此写入 XSS），无需任何管理权限或所有权；接口通过明文 HTTP 暴露，凭证还可被网络窃听。

**修复。** 删除/编辑操作校验调用者权限或主题归属（例如只允许 owner 或持有 ydata.delete_topic 权限的用户）；delete_all_topic 应仅限管理员并考虑整体移除；XML-RPC 接口应强制 HTTPS。

**复核员指出的最弱一环。** 最站不住的一环是"has_auth 是否仅认证不鉴权"。核实 lib/ylinux_xmlrpc.py:39-45 has_auth 只调用 authenticate 判断凭据有效；delete_topic（47-58）、delete_all_topic（60-69）、edit_topic（168-185）均无权限码或对象归属检查；settings.py:164-174 把这些方法注册为公开 XML-RPC 方法，urls.py:45-48 /xmlrpc/ 无登录要求。

**判定历史。**

- 复核员同意：任意有效注册账号即可删除单个/全部主题、改写任意主题，破坏范围覆盖全站内容，与 Web 界面的所有权检查形成对比；high 成立。（最弱一环：最站不住的一环是"has_auth 是否仅认证不鉴权"。核实 lib/ylinux_xmlrpc.py:39-45 has_auth 只调用 authenticate 判断凭据有效；delete_topic（47-58）、delete_all_topic（60-69）、edit_topic（168-185）均无权限码或对象归属检查；settings.py:164-174 把这些方法注册为公开 XML-RPC 方法，urls.py:45-48 /xmlrpc/ 无登录要求。）

**证据。**

`lib/ylinux_xmlrpc.py:39-45`

```
def has_auth(user, passwd):

    user = authenticate(username=user, password=passwd)
    if user is not None:
        return True
    else:
        return False
```

`lib/ylinux_xmlrpc.py:60-69`

```
def delete_all_topic(user, passwd):
    '''delete all topic'''
    if not has_auth(user, passwd):
        raise Fault(-1, "Authentication Failure")

    try:
        Topic.objects.all().delete()
        return True
    except:
        raise Fault(-1, "delete all topics failed")
```

`lib/ylinux_xmlrpc.py:173-181`

```
    try:
        topic = Topic.objects.get(pk=postid)
        if struct.has_key('title'):
            topic.name = st(struct['title'], 'utf-8')

        topic.updated = datetime.now()
        topic.save()
        if struct.has_key('description'):
            topic.save_file(st(struct['description'], 'utf-8'))
```

`settings.py:164-171`

```
XMLRPC_METHODS = (
    ('ylinux_xmlrpc.delete_topic', 'delete_topic'),
    ('ylinux_xmlrpc.delete_all_topic', 'delete_all_topic'),

    # MetaWebBlog API
    ('ylinux_xmlrpc.new_topic', 'metaWeblog.newPost'),
    ('ylinux_xmlrpc.new_media', 'metaWeblog.newMediaObject'),
    ('ylinux_xmlrpc.edit_topic', 'metaWeblog.editPost'),
```

<a id="finding-crypto-002"></a>

### [HIGH] 注册/重置令牌熵仅约 20 bit 且无时效与速率限制，可枚举接管任意账号

- 编号：`CRYPTO-002`
- 类别：`crypto`
- CWE：`CWE-330`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

注册激活/密码重置令牌只有约 20 bit 熵（salt = sha1(str(random.random()))[:5]，再 sha1(salt+email)），且 /account/password/reset/<key>/ 不校验时效、无速率限制、验证失败立即返回可区分的响应——攻击者知道目标邮箱即可在 2^20 空间内枚举出重置链接并直接设置新口令，构成独立于 CRYPTO-001/CONFIG-002 的账号接管路径。

**触发条件。** 匿名 POST /account/password/reset/ 为目标邮箱创建/轮换 Register 行（app/account/views.py:182-187），随后枚举 16^5 个 salt 计算 sha1(salt+email) 并 GET /account/password/reset/<key>/，命中后提交新口令。

**影响。** 攻击者知道目标邮箱即可接管任意账号：Register 行的 activation_key = sha1(salt+email)，salt 仅为 5 个十六进制字符（16^5 ≈ 2^20 ≈ 105 万种可能，且由 Mersenne Twister 派生）。该 key 同时是密码重置入口 /account/password/reset/<key>/ 的唯一凭据，视图只按 key 查库、无时效校验、无失败次数限制；攻击者可用 ~10^6 次请求枚举出正确 key，随后通过 SetPasswordForm 设置新口令。password_reset_request 还允许匿名者为任意已注册邮箱创建 Register 行，确保目标存在可枚举的行。

**修复。** 令牌改用密码学安全随机源生成足够长度（如 os.urandom(32) 的 hex/base64），对重置与激活令牌加有效期与一次性标记，对 /account/password/reset/ 与 /account/register/ 加速率限制（按 IP/邮箱）并在验证失败时延迟响应；重置成功后立即使令牌失效。

**复核员指出的最弱一环。** 最站不住的一环是"password_reset 是否真的既无时效校验又无速率限制、且命中后就能保存新口令"。我核实了 app/account/views.py:201-223：password_reset 仅有 @render_to 装饰器（无登录要求），按 activation_key 查库（205-206），错误 key 返回可区分的 403"错误的 Key"（208），正确 key 直接渲染 SetPasswordForm 并在 is_valid 后 form.save()；app/account/forms.py:166-170 确认 save() 调用 user.set_password(cleaned_data['new_password1'])。Register 模型（app/account/models.py:389-396）只有 email/activation_key/updated 三个字段，无过期时间字段，视图中也无任何时间戳比较；settings.py:98-104 的 MIDDLEWARE_CLASSES 只有 CommonMiddleware 和自定义 session/auth 中间件，无任何限速组件。响应可区分（403 错误页 vs 200 表单页），枚举可行。

**判定历史。**

- 复核员同意：逐项核实：1) 熵值：models.py:364/427 salt=sha1(str(random.random())).hexdigest()[:5] 仅 5 个十六进制字符，16^5≈2^20；activation_key=sha1(salt+email)（367/430），搜索空间由 2^20 的 salt 决定，与描述一致。2) 匿名入口：password_reset_request（views.py:166-198）无鉴权装饰器，对任意已注册邮箱 GET/创建 Register 行并重置 key（182-187），保证目标存在可枚举的行。3) 危险点：password_reset 只按 key 查库、无时效、无限速，错误 key 返回可区分的 403 响应（208），命中后 SetPasswordForm.save() 直接改口令（forms.py:166-170）。4) 严重性：约 2^20（均值 2^19）次请求即可确定 key 并接管账号，无任何限速缓解，high 恰当。结论成立。（最弱一环：最站不住的一环是"password_reset 是否真的既无时效校验又无速率限制、且命中后就能保存新口令"。我核实了 app/account/views.py:201-223：password_reset 仅有 @render_to 装饰器（无登录要求），按 activation_key 查库（205-206），错误 key 返回可区分的 403"错误的 Key"（208），正确 key 直接渲染 SetPasswordForm 并在 is_valid 后 form.save()；app/account/forms.py:166-170 确认 save() 调用 user.set_password(cleaned_data['new_password1'])。Register 模型（app/account/models.py:389-396）只有 email/activation_key/updated 三个字段，无过期时间字段，视图中也无任何时间戳比较；settings.py:98-104 的 MIDDLEWARE_CLASSES 只有 CommonMiddleware 和自定义 session/auth 中间件，无任何限速组件。响应可区分（403 错误页 vs 200 表单页），枚举可行。）

**证据。**

`app/account/models.py:361-369`

```
    def create_profile(self, email):
        """ 创建一个 Email - Key 对 """

        salt = sha_constructor(str(random.random())).hexdigest()[:5]
        if isinstance(email, unicode):
            email = email.encode('utf-8')
        activation_key = sha_constructor(salt+email).hexdigest()
        return self.create(email=email,
                           activation_key=activation_key)
```

`app/account/models.py:424-430`

```
    def reset_activation_key (self):
        ''' 重新生成 activation_key '''

        salt = sha_constructor(str(random.random())).hexdigest()[:5]
        if isinstance(self.email, unicode):
            email = self.email.encode('utf-8')
        self.activation_key = sha_constructor(salt+self.email).hexdigest()
```

`app/account/views.py:205-219`

```
    try:
        register = Register.objects.get(activation_key=key)
    except Register.DoesNotExist:
        return HttpResponseForbidden(u'<h1>错误的 Key ： %s </h1>' % key)

    try:
        user = User.objects.get(email=register.email)
    except User.DoesNotExist:
        return HttpResponseForbidden(u'<h2>无此 email 注册的用户 ： %s </h2>' % register.email)

    form = build_form (SetPasswordForm, request, user=user)

    if form.is_valid():
        form.clean_new_password2()
        form.save()
```

<a id="finding-file-001"></a>

### [HIGH] 附件上传文件名未消毒导致路径穿越任意文件写入

- 编号：`FILE-001`
- 类别：`file_access`
- CWE：`CWE-22`
- 入口身份：可自助注册的用户
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

/ydata/uploadsf/<id>/ 上传视图把客户端文件名 f.name 直接拼入存储路径（前缀 str(id)+'-'+str(user.id)+'-' 无法阻止后续的 ../ 序列），未做 basename 或目录归一化，登录用户可路径穿越把文件写到 MEDIA_ROOT 之外，包括 templates 目录（页面模板被 Django 直接加载渲染）与任意 Web 进程可写路径。

**触发条件。** 登录用户 POST /ydata/uploadsf/<id>/，文件名为 '3-1-../../../../templates/home/index.html' 之类的多段 ../ 文件名。

**数据流。** 来源：multipart 文件名 req.FILES['single_file'].name（app/ydata/views.py:40，客户端可控，Django 1.x 不消毒）→ 中间环节：local_name = str(id) + '-' + str(req.user.id) + '-' + f.name（app/ydata/views.py:78）→ 危险点：os.path.join(settings.MEDIA_ROOT, ATTACHMENT_UPLOAD_TO, local_name) 后 open(save_path, 'wb+') 写入（app/ydata/views.py:79-84）。文件名中追加的 ../ 序列可越过 MEDIA_ROOT/ydata/attachments 向上穿越，例如 3-1-../../../../templates/home/index.html 落到 PROJECT_ROOT/templates/home/index.html。入口需登录（@login_required，注册自助开放）。

**影响。** 任意文件写入（以 Web 进程权限）：覆盖站点模板（PROJECT_ROOT/templates 下的页面模板）实现全站内容篡改/持久 XSS，覆盖 MEDIA_ROOT 下主题 HTML 或静态资源；若 Web 用户对部署目录外有写权限，还可写 crontab、启动脚本等进一步扩大权限。

**修复。** 绝不要用客户端文件名拼路径：服务端生成文件名（如 hash+扩展名白名单），并用 os.path.basename 归一化后确认最终路径仍在 ATTACHMENT_UPLOAD_TO 之内（realpath 前缀校验）。

**复核员指出的最弱一环。** 最站不住的一环是"Django 是否会对 f.name 做 basename 消毒"。核实：ydata/views.py:78 直接用客户端文件名 f.name 拼 local_name，未经过 FileSystemStorage.get_valid_name 等任何归一化；Django 1.x 的 UploadedFile 对 name 不做路径剥离；79-84 行 open(save_path,'wb+') 前无 realpath 前缀校验，追加 ../ 段即可越出 MEDIA_ROOT/ydata/attachments。

**判定历史。**

- 复核员同意：来源：@login_required 上传接口（ydata/views.py:31-40），注册自助开放；危险点 os.path.join + open 写入核实无误；可覆盖 templates 目录下被直接加载渲染的模板，任意文件写入 high 成立。（最弱一环：最站不住的一环是"Django 是否会对 f.name 做 basename 消毒"。核实：ydata/views.py:78 直接用客户端文件名 f.name 拼 local_name，未经过 FileSystemStorage.get_valid_name 等任何归一化；Django 1.x 的 UploadedFile 对 name 不做路径剥离；79-84 行 open(save_path,'wb+') 前无 realpath 前缀校验，追加 ../ 段即可越出 MEDIA_ROOT/ydata/attachments。）

**证据。**

`app/ydata/views.py:40-41`

```
    f = req.FILES['single_file'] #req.FILES.values()[0]
    if f.size > ydata_settings.ATTACHMENT_SIZE_LIMIT:
```

`app/ydata/views.py:77-84`

```
    else:
        local_name = str(id) + '-' + str(req.user.id) + '-' + f.name
        save_path = os.path.join(settings.MEDIA_ROOT,
                                 ydata_settings.ATTACHMENT_UPLOAD_TO,
                                 local_name)
        save_file = open(save_path, 'wb+')
        for chunk in f.chunks():
            save_file.write(chunk)
```

`app/ydata/models.py:373-375`

```
    def get_absolute_path(self):
        return os.path.join(settings.MEDIA_ROOT, ydata_settings.ATTACHMENT_UPLOAD_TO,
                            self.path)
```

<a id="finding-xss-001"></a>

### [HIGH] 主题与回复正文存储型 XSS（Markdown 未启用 safe_mode，模板 |safe 渲染）

- 编号：`XSS-001`
- 类别：`xss`
- CWE：`CWE-79`
- 入口身份：可自助注册的用户
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

发帖与回复正文经 python-markdown 2.0.3 转换时没有启用 safe_mode，原始 HTML（包括 <script>）原样保留进 body_html，随后被模板以 |safe 原样输出到主题页、论坛页和 AJAX 接口，形成存储型 XSS。回复和帖子使用 markup='none' 路径（Post.save 中 Markdown(...).convert(...)），主题正文走 Topic.save_file 的 convertFile，两条路径均未传 safe_mode。攻击者只需注册一个账号（注册是自助的，激活后 is_active=True），即可向公开主题注入脚本，任何访客（含管理员）访问主题页时执行。

**触发条件。** 登录用户 POST /wiki/topic/<id>/replayAJAX/（body 参数，markup='none'）、/wiki/topic/<id>/addpost/、/wiki/catalog/<id>/addtopic/（text 参数）或 /wiki/topic/<id>/edit/，正文可含任意 HTML。

**数据流。** 来源：request.POST.get("body")（app/wiki/views.py:432，replayAJAX，需登录，注册自助开放）→ Post(markup='none', body=post_body)（app/wiki/views.py:435）→ Post.save() 中 Markdown(extensions=['fenced_code']).convert(ylinux_text_filter(self.body))，未启用 safe_mode（app/ydata/models.py:258-260）；主题路径：AddTopicForm.save() 的 text → Topic.save_file（app/ydata/models.py:190-200）convertFile 同样无 safe_mode → 危险点 1：templates/wiki/topic.html:54 {{ topic.body_html|safe }} 与 :59 {{ POST_HTML|safe }}；危险点 2：app/wiki/utils.py:18 {{ post.body_html|safe }}（render_post 被 topic 视图与 ajax_show_posts 使用）；危险点 3：templates/bbs/topic.html:23,30、templates/wiki/post.html:12、replayAJAX.html:16、editPostAJAX.html:19 的 |safe。lib/markdown/postprocessors.py:54 表明 safeMode 为假时原始 HTML 原样还原。

**影响。** 攻击者在所有访问者的同源上下文中执行脚本：窃取会话 Cookie（自定义 SessionMiddleware 设置 Cookie 时未传 httponly，见 app/sessions/middleware.py:37-41）、以受害者身份发帖/删帖，若管理员浏览则可通过 /admin/ 接口扩大权限；可长期控制页面内容。

**修复。** 1) 转换时启用 safe_mode='escape'（或改用支持 HTML 消毒的渲染器，如 bleach 过滤后再渲染）；2) 移除模板中的 |safe，或仅对经过严格消毒的 HTML 使用；3) Session Cookie 加 HttpOnly。

**复核员指出的最弱一环。** 最站不住的一环是"中间是否可能被 ylinux_text_filter 消毒"。我核实了 app/ydata/models.py:396-452：该过滤器只做 [A:ID]/[W:ID]/[I:ID] 宏替换，完全不清理 <script> 等原始 HTML；lib/markdown/__init__.py:188 确认 Markdown 构造器默认 safe_mode=False，Post.save 的 markup='none' 分支（models.py:258-260）和 Topic.save_file 的 convertFile（198-200）都没传 safe_mode，postprocessors.py:54 在 safeMode 为假时原样还原原始 HTML。

**判定历史。**

- 复核员同意：来源可信：replayAJAX 需登录（views.py:399-400），add_post @login_required（132-134），AddPostForm.save 强制 markup='none'（forms.py:46），注册自助开放；危险点核实：templates/wiki/topic.html:54,59、bbs/topic.html:23,30、wiki/utils.py:18 均 |safe 输出 body_html，show_topic 无访问控制（views.py:81-103 任意访客可见）。会话 Cookie 确无 httponly（app/sessions/middleware.py:37-41）。存储型 XSS 成立，high 合理。（最弱一环：最站不住的一环是"中间是否可能被 ylinux_text_filter 消毒"。我核实了 app/ydata/models.py:396-452：该过滤器只做 [A:ID]/[W:ID]/[I:ID] 宏替换，完全不清理 <script> 等原始 HTML；lib/markdown/__init__.py:188 确认 Markdown 构造器默认 safe_mode=False，Post.save 的 markup='none' 分支（models.py:258-260）和 Topic.save_file 的 convertFile（198-200）都没传 safe_mode，postprocessors.py:54 在 safeMode 为假时原样还原原始 HTML。）

**证据。**

`app/wiki/views.py:432-436`

```
        post_body = request.POST.get("body", None)
        if len(post_body) < 2:
            return {'error': u'您的回复太短，至少2个字符！'}
        post = Post(topic = topic, user = request.user, user_ip = ip, markup = 'none', body = post_body, parent = parent_post)
        post.save()
```

`app/ydata/models.py:258-260`

```
        elif self.markup == 'none':
            #self.body_html = self.body
            self.body_html = Markdown(extensions=['fenced_code']).convert(ylinux_text_filter(self.body))
```

`app/ydata/models.py:198-200`

```
        Markdown(extensions=['fenced_code']).convertFile(input=self.body_path, 
                       output=self.body_html_path, 
                       encoding="utf8", myfilter=ylinux_text_filter)
```

`lib/markdown/postprocessors.py:54-57`

```
            if safe or not self.markdown.safeMode:
                text = text.replace("<p>%s</p>" % 
                            (markdown.preprocessors.HTML_PLACEHOLDER % i),
                            html + "\n")
```

`templates/wiki/topic.html:53-60`

```
  <div class="topic-body content">
    {{ topic.body_html|safe }}
  </div>


{% if posts %}
{{ POST_HTML|safe }}
{% endif %}
```

`app/wiki/utils.py:17-19`

```
<div class="post-body">
  <p>{{ post.body_html|safe }}</p>
</div>
```

`templates/bbs/topic.html:22-31`

```
    <h2>标题： {{ topic.name }}</h2>
    {{ topic.body_html|safe }}
  </div>
</div>
{% for p in posts %}
<div class="post_body">
  <div class="tdc1"><a href="{% url account:show_user p.user.id %}">{{ p.user }}</a></div>
  <div class="tdc2">
    {{ p.body_html|safe }}
```

<a id="finding-access-001"></a>

### [MEDIUM] editPostAJAX 缺少所有权校验，任意登录用户可编辑他人回复（IDOR）

- 编号：`ACCESS-001`
- 类别：`access_control`
- CWE：`CWE-639`
- 入口身份：可自助注册的用户
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

editPostAJAX 视图允许任意登录用户修改任意回复：只校验了登录态，没有校验回复归属（同文件的 edit_topic/del_post 都有所有权检查，唯独这里没有）。

**触发条件。** 登录用户 POST /wiki/post/<任意 postID>/editAJAX/，body 参数为任意内容。

**数据流。** 来源：URL 参数 postID（app/wiki/urls.py:54 (?P<postID>\d+)）与 POST body（app/wiki/views.py:456 request.POST.get('body')）→ 中间环节：get_object_or_404(Post, pk=postID)（app/wiki/views.py:451）→ 危险点：post.body = post_body; post.save()（app/wiki/views.py:459-460）。视图仅 @login_required，无 post.user == request.user 校验（对比同文件 edit_topic 第 217-218 行与 del_post 第 277-278 行的所有权检查）。入口为任意登录用户（注册自助开放）。

**影响。** 任意登录用户可改写他人（含管理员）的任何回复内容，用于内容篡改、注入 XSS（正文走无 safe_mode 的 markdown 渲染后 |safe 输出，见 XSS-001）或抹除证据。

**修复。** 在 editPostAJAX 中校验 post.user == request.user（或相应编辑权限）后再保存；同一视图的其他变更操作同样先做所有权校验。

**复核员指出的最弱一环。** 最站不住的一环是"是否真的没有归属校验"。核实 app/wiki/views.py:447-467：editPostAJAX 仅有 @login_required，GET 返回任意 post，POST 直接 post.body=post_body 后 save()，全文无 post.user==request.user 检查；对比同文件 edit_topic:217-218 与 del_post:277-278 均有所有权检查，差异属实。

**判定历史。**

- 复核员同意：任意登录用户可改写他人回复，且改写的 body 走 XSS-001 的无 safe_mode 渲染链放大危害；medium 合理。（最弱一环：最站不住的一环是"是否真的没有归属校验"。核实 app/wiki/views.py:447-467：editPostAJAX 仅有 @login_required，GET 返回任意 post，POST 直接 post.body=post_body 后 save()，全文无 post.user==request.user 检查；对比同文件 edit_topic:217-218 与 del_post:277-278 均有所有权检查，差异属实。）

**证据。**

`app/wiki/views.py:447-460`

```
@login_required
@render_to('wiki/editPostAJAX.html')
def editPostAJAX(request, postID):

    post = get_object_or_404(Post, pk = postID)

    if request.method == 'GET':
        return {'method': 'GET', 'post': post}

    post_body = request.POST.get('body', None)
    if not post_body:
        return HttpResponse(u'error: No contents found!')
    post.body = post_body
    post.save()
```

`app/wiki/views.py:213-218`

```
def edit_topic(request, id):

    topic = get_object_or_404(Topic, pk=id)

    if topic.user != request.user:
        return HttpResponseForbidden('<h1>您没有这个权限！</h1>')
```

<a id="finding-config-001"></a>

### [MEDIUM] DEBUG=True 提交进仓库并暴露 MEDIA_ROOT 目录浏览

- 编号：`CONFIG-001`
- 类别：`config`
- CWE：`CWE-215`
- 入口身份：无请求入口
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

DEBUG=True 被提交进仓库，且 urls.py 在 DEBUG 下用 django.views.static.serve 以 show_indexes=True 暴露整个 MEDIA_ROOT。若部署时未覆盖 settings，将开启详细错误页（泄露堆栈与配置）与媒体目录浏览。

**触发条件。** 部署直接使用仓库 settings.py（无环境覆盖）时生效：触发任意异常查看错误页；访问 /ymedia/ 浏览目录。

**影响。** 生产环境一旦以此配置运行：任意未捕获异常向访问者泄露堆栈、局部变量、settings 值（含 SECRET_KEY、数据库口令）；/ymedia/ 可浏览 MEDIA_ROOT 目录树（show_indexes=True），下载所有上传附件与主题源文件；静态服务本身也可能被用作内容托管。

**修复。** 部署环境显式设置 DEBUG=False；不要用 django.views.static.serve 服务媒体目录（交给 Web 服务器），并关闭 show_indexes；把 DEBUG 等环境相关配置从仓库移到环境变量。

**复核员指出的最弱一环。** 最站不住的一环是"配置是否真的生效（取决于部署）"。核实 settings.py:18-19 DEBUG=True 确已提交，urls.py:59-63 在 DEBUG 下挂载 django.views.static.serve 且 show_indexes=True 暴露 MEDIA_ROOT 目录树；发现本身已注明"部署未覆盖时生效"的条件，medium 定级与条件性相符。

**判定历史。**

- 复核员同意：DEBUG 详情页泄露堆栈/配置、/ymedia/ 目录浏览均属实，作为仓库默认配置风险成立。（最弱一环：最站不住的一环是"配置是否真的生效（取决于部署）"。核实 settings.py:18-19 DEBUG=True 确已提交，urls.py:59-63 在 DEBUG 下挂载 django.views.static.serve 且 show_indexes=True 暴露 MEDIA_ROOT 目录树；发现本身已注明"部署未覆盖时生效"的条件，medium 定级与条件性相符。）

**证据。**

`settings.py:18-19`

```
DEBUG = True
TEMPLATE_DEBUG = DEBUG
```

`urls.py:59-63`

```
if (settings.DEBUG):
    urlpatterns += patterns ('',
        (r'^ymedia/(?P<path>.*)$', 'django.views.static.serve',
         {'document_root': settings.MEDIA_ROOT, 'show_indexes': True}),
    )
```

<a id="finding-config-002"></a>

### [MEDIUM] SECRET_KEY 硬编码进仓库，会话签名与密码重置令牌可被伪造

- 编号：`CONFIG-002`
- 类别：`crypto`
- CWE：`CWE-321`
- 入口身份：无请求入口
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

Django SECRET_KEY 明文硬编码在仓库中。它被用于会话数据防篡改签名（app/sessions/models.py 与 backends/base.py 的 MD5(pickled+SECRET_KEY)）和密码重置令牌生成（app/account/tokens.py 的 SHA1(SECRET_KEY+uid+password+last_login)），密钥泄露使这些防护可被离线伪造。

**触发条件。** 仓库公开可见即可取得密钥；结合用户密码哈希与 last_login（如数据库泄露）离线构造重置令牌。

**影响。** SECRET_KEY 公开后：会话数据签名（MD5(pickle+KEY)）与密码重置令牌（SHA1(KEY+uid+password_hash+last_login)）的完整性保证失效——攻击者一旦再获得用户密码哈希与最后登录时间（如数据库泄露或其它信息泄露），即可离线伪造密码重置令牌接管任意账号；签名机制整体失去意义。

**修复。** 轮换 SECRET_KEY（从环境变量/密钥管理读取，不入库）；会话与令牌的防篡改改用专用随机会话密钥或 HMAC 并独立于 SECRET_KEY。

**复核员指出的最弱一环。** 最站不住的一环是"影响是否被夸大（能否直接伪造会话）"。核实：会话签名 MD5(pickle+KEY)（sessions/models.py:13-19）但会话数据存 DB、客户端只有 session_key，密钥泄露本身不能直接远程伪造会话；密码重置令牌 SHA1(KEY+uid+password+last_login)（tokens.py:53-57）在同时获得口令哈希与 last_login 时可离线伪造——发现已如实表述这一前置条件，未夸大。

**判定历史。**

- 复核员同意：SECRET_KEY 明文入库（settings.py:78-79）且用于令牌与签名，medium 合理。（最弱一环：最站不住的一环是"影响是否被夸大（能否直接伪造会话）"。核实：会话签名 MD5(pickle+KEY)（sessions/models.py:13-19）但会话数据存 DB、客户端只有 session_key，密钥泄露本身不能直接远程伪造会话；密码重置令牌 SHA1(KEY+uid+password+last_login)（tokens.py:53-57）在同时获得口令哈希与 last_login 时可离线伪造——发现已如实表述这一前置条件，未夸大。）

**证据。**

`settings.py:78-79`

```
# Make this unique, and don't share it with anybody.
SECRET_KEY = 'c#0cz^i$lyr6*b*xe-t@0tqc_c3dnju=+c1lk^k7(r^7lhz$g@'
```

`app/account/tokens.py:53-57`

```
        from django.utils.hashcompat import sha_constructor
        hash = sha_constructor(settings.SECRET_KEY + unicode(user.id) +
                               user.password + user.last_login.strftime('%Y-%m-%d %H:%M:%S') +
                               unicode(timestamp)).hexdigest()[::2]
        return "%s-%s" % (ts_b36, hash)
```

`app/sessions/models.py:13-19`

```
    def encode(self, session_dict):
        """
        Returns the given session dictionary pickled and encoded as a string.
        """
        pickled = pickle.dumps(session_dict)
        pickled_md5 = md5_constructor(pickled + settings.SECRET_KEY).hexdigest()
        return base64.encodestring(pickled + pickled_md5)
```

<a id="finding-crypto-001"></a>

### [MEDIUM] 密码使用弱哈希（单轮 SHA1 + 短弱随机盐）

- 编号：`CRYPTO-001`
- 类别：`crypto`
- CWE：`CWE-916`
- 入口身份：可自助注册的用户
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

密码存储为单轮 sha1(salt+password)（兼容路径还有 md5），盐仅 5 个十六进制字符，且由 random.random()（MT 伪随机）派生，抵御离线爆破能力极弱。

**触发条件。** 任何途径获得 user.password 列（数据库备份/泄露、SQLite 文件可被下载时）即可离线爆破。

**影响。** 数据库一旦泄露，口令哈希可被低成本爆破：单轮 SHA1、5 个十六进制字符（约 20 bit）的盐、盐源自可预测的 random.random()（MT19937）输出；使用常见字典即可批量还原大部分用户口令，进而通过 XML-RPC（ACCESS-002）等入口扩大破坏。

**修复。** 改用强 KDF：PBKDF2/argon2（django.contrib.auth.hashers 或 hashlib.pbkdf2_hmac），提高迭代次数并使用密码学安全的随机盐（os.urandom/secrets）。

**复核员指出的最弱一环。** 最站不住的一环是"是否真是单轮 SHA1 + 弱盐"。核实 app/account/models.py:62-66 get_hexdigest 为 md5/sha1 单轮拼接；set_password（228-234）盐 = sha1(str(random.random()))[:5] 仅 5 个十六进制字符，随机源为 Mersenne Twister 伪随机，描述准确。

**判定历史。**

- 复核员同意：数据库泄露后离线爆破成本极低，medium 合理；入口角色 registered_open 只是提供口令来源，无碍。（最弱一环：最站不住的一环是"是否真是单轮 SHA1 + 弱盐"。核实 app/account/models.py:62-66 get_hexdigest 为 md5/sha1 单轮拼接；set_password（228-234）盐 = sha1(str(random.random()))[:5] 仅 5 个十六进制字符，随机源为 Mersenne Twister 伪随机，描述准确。）

**证据。**

`app/account/models.py:62-66`

```
    if algorithm == 'md5':
        return md5_constructor(salt + raw_password).hexdigest()
    elif algorithm == 'sha1':
        return sha_constructor(salt + raw_password).hexdigest()
    raise ValueError("未知加密算法")
```

`app/account/models.py:228-234`

```
    def set_password(self, raw_password):
        "设置密码"
        import random
        algo = 'sha1'
        salt = get_hexdigest(algo, str(random.random()), str(random.random()))[:5]
        hsh = get_hexdigest(algo, salt, raw_password)
        self.password = '%s$%s$%s' % (algo, salt, hsh)
```

<a id="finding-csrf-001"></a>

### [MEDIUM] 全站缺少 CSRF 防护，状态变更接口可被跨站请求伪造

- 编号：`CSRF-001`
- 类别：`csrf`
- CWE：`CWE-352`
- 入口身份：可自助注册的用户
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

全站未启用 CSRF 防护：MIDDLEWARE_CLASSES 没有 CsrfViewMiddleware，代码中也没有任何 csrf_protect 装饰器，且大量状态变更接口（删除用户/主题/帖子、编辑、上传、管理员群发邮件、reboot 等）甚至接受 GET 请求。仅凭会话 Cookie 即可完成敏感操作，可被跨站请求伪造。

**触发条件。** 任意页面中的表单/图片请求指向登录用户会话可及的写接口（如 /wiki/topic/<id>/delete/、/admin/user/<id>/del、/wiki/post/<id>/editAJAX/ 等）。

**影响。** 攻击者页面可在受害者登录状态下跨站触发所有状态变更操作：发帖/改帖/删帖、删主题、改个人资料，若受害者是管理员还可删除用户/权限/目录、群发邮件（email_to_all）、重启服务进程（reboot，killall 当前用户）等；配合 XSS-003 可窃取会话。

**修复。** 在 MIDDLEWARE_CLASSES 加入 django.middleware.csrf.CsrfViewMiddleware（或对敏感视图加 csrf_protect），并在表单模板加 {% csrf_token %}；把删除等状态变更改为 POST 且校验令牌。

**复核员指出的最弱一环。** 最站不住的一环是"是否真的全站无 CSRF 防护"。全仓搜索 csrf 仅命中 lib/django_xmlrpc/views.py 的 csrf_exempt；settings.py:98-104 MIDDLEWARE_CLASSES 无 CsrfViewMiddleware；app 代码无 csrf_protect 装饰器；del_user（admin/views.py:250-257）、manage_topic 删除（wiki/views.py:237-250）等写操作可 GET 触发，均只依赖会话 Cookie。

**判定历史。**

- 复核员同意：全站状态变更接口可被跨站伪造，配合本报告 XSS 发现可扩大影响；medium 合理。（最弱一环：最站不住的一环是"是否真的全站无 CSRF 防护"。全仓搜索 csrf 仅命中 lib/django_xmlrpc/views.py 的 csrf_exempt；settings.py:98-104 MIDDLEWARE_CLASSES 无 CsrfViewMiddleware；app 代码无 csrf_protect 装饰器；del_user（admin/views.py:250-257）、manage_topic 删除（wiki/views.py:237-250）等写操作可 GET 触发，均只依赖会话 Cookie。）

**证据。**

`settings.py:98-104`

```
MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
#    'django.contrib.sessions.middleware.SessionMiddleware',
#    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'ylinux.app.sessions.middleware.SessionMiddleware',
    'ylinux.app.account.middleware.AuthenticationMiddleware',
)
```

`app/admin/views.py:250-257`

```
@permission_required('just_admin_can_delete')
@render_to ('admin/del_user.html')
def del_user (request, id):

    user = get_object_or_404 (User, pk=id)
    # 这里等待以后验证是否已有其他关联
    user.delete()
    return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))
```

`app/wiki/views.py:237-250`

```
@login_required
def manage_topic (request, id, type=None):

    topic = get_object_or_404 (Topic, pk=id)

    if topic.user != request.user:
        return HttpResponseForbidden('<h1>您没有这个权限！</h1>')

    c_id = topic.catalog.id

    if type is "delete":
        for p in topic.posts.all():
            p.delete()
        topic.delete()
```

<a id="finding-file-002"></a>

### [MEDIUM] 上传无类型白名单且落盘同源静态目录，可上传 HTML/SVG 形成同源存储型 XSS

- 编号：`FILE-002`
- 类别：`file_access`
- CWE：`CWE-434`
- 入口身份：可自助注册的用户
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

附件上传对文件类型/扩展名没有任何白名单（仅检查 512KB 大小），文件以客户端文件名落盘在 MEDIA_ROOT 下；而仓库默认配置（DEBUG=True）把 MEDIA_ROOT 以 django.views.static.serve（同源 /ymedia/）直接服务，生产环境 .htaccess 也把 /ymedia 作为静态目录。因此即使不利用路径穿越（FILE-001），登录用户也能上传 .html/.svg 等文件获得同源 URL，形成持久存储型 XSS 与钓鱼页面托管。

**触发条件。** 登录用户 POST /ydata/uploadsf/<id>/ 上传扩展名为 .html/.svg 的文件，得到 /ymedia/ydata/attachments/... 同源 URL 后诱导受害者访问。

**数据流。** 来源：multipart 文件名与内容 req.FILES['single_file'].name/req.FILES['single_file'].chunks()（app/ydata/views.py:40，登录用户可控，无类型/扩展名白名单，仅大小检查）→ 中间环节：local_name = str(id)+'-'+str(user.id)+'-'+f.name，open(save_path,'wb+') 写入 MEDIA_ROOT/ydata/attachments（app/ydata/views.py:78-84，settings.py:74-75 MEDIA_ROOT=PROJECT_ROOT+'/ymedia/'）→ 危险点：urls.py:59-63 在 DEBUG=True 下用 django.views.static.serve 以 show_indexes=True 同源服务 /ymedia/，django 按扩展名猜测 Content-Type，.html 以 text/html 下发并执行；入口为 @login_required（注册自助开放）。

**影响。** 登录用户上传 evil.html/evil.svg（或含脚本的 .js 引用页）后获得同源 URL /ymedia/ydata/attachments/<id>-<uid>-<文件名>，以钓鱼链接发给受害者即在可信域上执行攻击者脚本：窃取会话 Cookie（Cookie 非 HttpOnly）、伪造登录页收集凭据、对登录用户做同源操作；内容持久存在，独立于 FILE-001 的路径穿越。

**修复。** 上传时按扩展名/MIME 双重白名单限制（如仅允许图片，并重写扩展名）；存储目录与站点主域隔离（不同源）或强制静态文件以 Content-Disposition: attachment 下发；对上传内容做服务端检查（如 PIL 解码验证）；Cookie 加 HttpOnly。

**复核员指出的最弱一环。** 最站不住的一环是"上传落盘的文件能否被同源以 text/html 服务并执行"。我核实了 urls.py:59-63：DEBUG=True（settings.py:18-19）时 /ymedia/ 由 django.views.static.serve 同源服务（show_indexes=True），static.serve 按扩展名经 mimetypes 猜测 Content-Type，.html 以 text/html 下发即执行；生产侧 scripts/.htaccess:23-24 的 RewriteCond REQUEST_FILENAME !-f 意味着已存在的文件（上传附件）不会被重写到 fcgi，而由 Apache 在同源 /ymedia/ 下按扩展名直接静态下发。同时核实 ydata 上传视图（app/ydata/views.py:31-100）：仅 @login_required + POST 限制 + 512KB 大小检查（41 行，ydata/settings.py:66），52-75 行只做 sha1 去重，无任何扩展名/MIME 白名单，78-84 行以客户端文件名写入 MEDIA_ROOT/ydata/attachments（ATTACHMENT_UPLOAD_TO='ydata/attachments'，ydata/settings.py:65；MEDIA_URL='/ymedia/'，settings.py:74-75），与 /ymedia/ydata/attachments/<文件> 的 URL 路径完全吻合。

**判定历史。**

- 复核员同意：核实了来源、落盘与危险点全链：上传无类型白名单（仅大小检查，views.py:40-42）、文件名原样落盘 MEDIA_ROOT（78-84）、/ymedia/ 在 DEBUG 下由 static.serve 同源服务且按扩展名以 text/html 下发 .html（urls.py:59-63），生产 .htaccess 对已存在文件同样由 Web 服务器静态下发（scripts/.htaccess:23-24），同源执行成立。入口为 @login_required（注册自助开放），危害为持久同源存储型 XSS/钓鱼托管，需诱导受害者访问，medium 定级恰当。与 FILE-001（路径穿越）为同一上传点的两个独立风险，分别记录合理。结论成立。（最弱一环：最站不住的一环是"上传落盘的文件能否被同源以 text/html 服务并执行"。我核实了 urls.py:59-63：DEBUG=True（settings.py:18-19）时 /ymedia/ 由 django.views.static.serve 同源服务（show_indexes=True），static.serve 按扩展名经 mimetypes 猜测 Content-Type，.html 以 text/html 下发即执行；生产侧 scripts/.htaccess:23-24 的 RewriteCond REQUEST_FILENAME !-f 意味着已存在的文件（上传附件）不会被重写到 fcgi，而由 Apache 在同源 /ymedia/ 下按扩展名直接静态下发。同时核实 ydata 上传视图（app/ydata/views.py:31-100）：仅 @login_required + POST 限制 + 512KB 大小检查（41 行，ydata/settings.py:66），52-75 行只做 sha1 去重，无任何扩展名/MIME 白名单，78-84 行以客户端文件名写入 MEDIA_ROOT/ydata/attachments（ATTACHMENT_UPLOAD_TO='ydata/attachments'，ydata/settings.py:65；MEDIA_URL='/ymedia/'，settings.py:74-75），与 /ymedia/ydata/attachments/<文件> 的 URL 路径完全吻合。）

**证据。**

`app/ydata/views.py:77-90`

```
    else:
        local_name = str(id) + '-' + str(req.user.id) + '-' + f.name
        save_path = os.path.join(settings.MEDIA_ROOT,
                                 ydata_settings.ATTACHMENT_UPLOAD_TO,
                                 local_name)
        save_file = open(save_path, 'wb+')
        for chunk in f.chunks():
            save_file.write(chunk)

        attachment = Attachment(user=req.user, name=f.name, path=local_name, size=f.size, hash=fhash)
```

`settings.py:74-75`

```
MEDIA_ROOT = PROJECT_ROOT+'/ymedia/'
MEDIA_URL = '/ymedia/'
```

`urls.py:59-63`

```
if (settings.DEBUG):
    urlpatterns += patterns ('',
        (r'^ymedia/(?P<path>.*)$', 'django.views.static.serve',
         {'document_root': settings.MEDIA_ROOT, 'show_indexes': True}),
    )
```

<a id="finding-redirect-001"></a>

### [MEDIUM] logout/login 流程的 next 与 Referer 参数导致开放重定向

- 编号：`REDIRECT-001`
- 类别：`redirect`
- CWE：`CWE-601`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

多个重定向直接使用攻击者可控值而不校验：/account/logout/?next=<任意 URL> 会 302 到任意外部地址（匿名即可触发）；登录流程把 ?next= 存入 session 并在登录成功后跳转；admin 登录把 HTTP_REFERER 存入 session 并在成功后跳转。

**触发条件。** 访问 /account/logout/?next=//evil.example/（匿名）；或先访问 /account/login?next=//evil.example/ 再登录；admin 带恶意 Referer 登录。

**数据流。** 来源：request.GET.get('next')（app/account/views.py:58，匿名可控）→ 危险点：logout() 后 HttpResponseRedirect(previous_url or '/')（app/account/views.py:60），未校验 URL 是否站内。次级路径：login 视图把 GET 的 next 存入 session（app/account/views.py:44），登录成功后重定向到它（app/account/views.py:38）；admin login 用 HTTP_REFERER 存入 session（app/admin/views.py:65）并在登录后跳转（app/admin/views.py:62）。入口：anonymous（无需登录，点击 /account/logout/?next=//evil.com 即触发）。

**影响。** 钓鱼/凭据劫持：把受害者从可信域无缝带到攻击者站点（伪造登录页窃取账号），或借 ylinux.org 的域名信誉绕过链接过滤；admin 登录的 Referer 跳转可把管理员引向恶意站点。

**修复。** 跳转目标必须校验为站内相对路径（如 django.utils.http.is_safe_url 或强制以 '/' 开头且不含 '//'）；admin 不要信任 HTTP_REFERER 作为跳转目标。

**复核员指出的最弱一环。** 最站不住的一环是"跳转目标是否真的无校验"。核实 account/views.py:55-60 logout 直接 HttpResponseRedirect(request.GET.get('next'))；login 将 GET 的 next 存入 session 并在成功后跳转（42-45、36-38）；admin login 用 HTTP_REFERER 存 session 并在登录后跳转（admin/views.py:62,65）；三处均无 is_safe_url/前缀校验。

**判定历史。**

- 复核员同意：logout 匿名即可触发 302 到 //evil.example，登录流程可做钓鱼跳板；开放重定向 medium 符合惯例。（最弱一环：最站不住的一环是"跳转目标是否真的无校验"。核实 account/views.py:55-60 logout 直接 HttpResponseRedirect(request.GET.get('next'))；login 将 GET 的 next 存入 session 并在成功后跳转（42-45、36-38）；admin login 用 HTTP_REFERER 存 session 并在登录后跳转（admin/views.py:62,65）；三处均无 is_safe_url/前缀校验。）

**证据。**

`app/account/views.py:55-60`

```
def logout(request):
    #from django.contrib.auth import logout
    from account import logout
    previous_url = request.GET.get('next')
    logout(request)
    return HttpResponseRedirect(previous_url or '/')
```

`app/account/views.py:42-45`

```
    else:
        # 形如 "http://127.0.0.1:8000/account/login?next=/admin/" 的 url 可以得到 next 值
        request.session['login_redirect_url'] = request.GET.get('next')
        form = AuthenticationForm(request)
```

`app/account/views.py:36-38`

```
                    if request.session.test_cookie_worked():
                        request.session.delete_test_cookie()
                        return HttpResponseRedirect(request.session.get('login_redirect_url','/') or '/')
```

<a id="finding-xss-002"></a>

### [MEDIUM] 注册/密码重置视图对 URL key 未转义导致的反射型 XSS

- 编号：`XSS-002`
- 类别：`xss`
- CWE：`CWE-79`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

注册激活和密码重置视图把 URL 中的 key 参数直接 % 格式化进 HttpResponseForbidden 的 HTML（未转义）。URL 正则 (?P<key>.+)/ 接受任意字符，且 Django 匹配前已对路径做百分号解码，因此匿名用户可通过 /account/register/%3Cscript%3E...%3C/script%3E/ 触发反射型 XSS（密码重置入口同理）。

**触发条件。** 匿名 GET /account/register/<编码后的任意 HTML>/ 或 /account/password/reset/<任意 key>/，key 与库中 activation_key 不匹配时进入异常分支直接回显。

**数据流。** 来源：URL 路径中的 key（app/account/urls.py:8 与 :13 的正则 (?P<key>.+)/，Django 在路由匹配前对路径做百分号解码）→ register()/password_reset() 在 Register 查找失败时直接拼进 HTML 字符串（app/account/views.py:102 与 :208）→ 危险点：HttpResponseForbidden 以默认 text/html 输出，key 未做任何 HTML 转义。入口无需任何身份（anonymous），构造 /account/register/%3Cscript%3E...%3C/script%3E/ 即可触发。

**影响。** 反射型 XSS：攻击者向受害者发送携带编码后的 <script> 的链接，受害者点击后在 ylinux 同源执行攻击者脚本，可窃取会话 Cookie（非 HttpOnly）或伪造页面钓鱼。

**修复。** 对 key 做 HTML 转义后再输出（如 django.utils.html.escape），或改为模板渲染（自动转义）；不要用 % 拼接用户输入到 HTML 响应。

**复核员指出的最弱一环。** 最站不住的一环是"百分号解码后的 <script> 能否匹配 (?P<key>.+)/ 并原样回显"。核实：WSGI 规范下服务器对 PATH_INFO 做 URL 解码（wsgiref/mod_wsgi 均如此），解码后 /account/register/<script>alert(1)</script>/ 中 .+ 匹配任意字符含尖括号且满足尾斜杠；views.py:96-102 与 202-208 在 Register 查找失败分支把 key 直接 % 拼进 HttpResponseForbidden（默认 text/html），无任何转义。

**判定历史。**

- 复核员同意：来源匿名可达（app/account/urls.py:8,13 无装饰器映射），回显点核实为原生字符串拼接（account/views.py:102、208），无 escape 调用，反射型 XSS 成立；medium 符合该类型惯例。（最弱一环：最站不住的一环是"百分号解码后的 <script> 能否匹配 (?P<key>.+)/ 并原样回显"。核实：WSGI 规范下服务器对 PATH_INFO 做 URL 解码（wsgiref/mod_wsgi 均如此），解码后 /account/register/<script>alert(1)</script>/ 中 .+ 匹配任意字符含尖括号且满足尾斜杠；views.py:96-102 与 202-208 在 Register 查找失败分支把 key 直接 % 拼进 HttpResponseForbidden（默认 text/html），无任何转义。）

**证据。**

`app/account/urls.py:8-13`

```
    url(r'^register/(?P<key>.+)/$', 'register', name='complete_register'),
```

`app/account/views.py:96-102`

```
def register(request, key=None):
    """用户注册视图，根据用户名和Email信息注册新用户。 """

    try:
        register = Register.objects.get(activation_key=key)
    except Register.DoesNotExist:
        return HttpResponseForbidden(u'<h1>错误的 Key ： %s </h1>' % key)
```

`app/account/views.py:202-208`

```
def password_reset (request, key=None):
    """ 重置用户密码 """

    try:
        register = Register.objects.get(activation_key=key)
    except Register.DoesNotExist:
        return HttpResponseForbidden(u'<h1>错误的 Key ： %s </h1>' % key)
```

<a id="finding-xss-003"></a>

### [MEDIUM] 上传文件名未转义嵌入响应脚本导致的 XSS（ylab/ydata 上传视图）

- 编号：`XSS-003`
- 类别：`xss`
- CWE：`CWE-79`
- 入口身份：匿名
- 置信度：`medium`
- 状态：`confirmed`
- 复核员：同意

两个上传视图把客户端提供的文件名原样拼进响应中的 JavaScript/HTML：/lab/uploadsf（匿名、无方法外检查、仅限 POST）与 /ydata/uploadsf/<id>/（登录）。文件名可含引号或 </script>，从而闭合脚本上下文，使注入的脚本在站点同源执行。

**触发条件。** 向 /lab/uploadsf 或 /ydata/uploadsf/<id>/ 提交文件名含 \" 或 </script> 的 multipart 文件；ylab 入口匿名可达，ydata 入口需登录（无 CSRF 防护可跨站触发）。

**数据流。** 来源：multipart 上传的客户端文件名 req.FILES['single_file'].name（app/ydata/views.py:40）与 req.FILES.values()[0].name（app/ylab/views.py:31）→ 中间环节：attachment.name 存入 Attachment 并被 % 直接拼入 JavaScript 字符串（ydata，app/ydata/views.py:91-95），ylab 则把 name 拼入 innerHTML 再嵌入 <script> 参数（app/ylab/views.py:32-33）→ 危险点：HttpResponse 以 text/html 返回，文件名中的 \" 或 </script> 可闭合字符串/脚本标签，使攻击者可控的脚本在 ylinux 源执行。ylab 入口匿名；ydata 入口需登录（但站点无 CSRF 防护，攻击者可跨站表单携带构造文件名的 multipart 请求）。

**影响。** 上传响应页面执行攻击者注入的脚本：窃取登录用户会话 Cookie、以受害者身份执行操作（配合站点缺失的 CSRF 防护可实现跨站触发）。

**修复。** 文件名插入 JS/HTML 前做 JS 字符串转义（json/escapejs）与 HTML 转义；上传成功后返回结构化 JSON 而非内联 script。

**复核员指出的最弱一环。** 最站不住的一环是"拼接进 <script> 的响应是否真的会执行"。核实：两个视图都返回默认 content_type=text/html 的整页 HttpResponse，ylab 把文件名拼进 innerHTML 再内联进脚本参数（ylab/views.py:32-33），文件名含 </script> 即可提前闭合脚本标签注入新脚本；ydata 文件名位于双引号 JS 字符串内（ydata/views.py:91-95），引号即可闭合，无需 </script>。ylab 视图无任何登录/权限装饰器（匿名可达），ydata 为 @login_required。

**判定历史。**

- 复核员同意：核实 ylab/urls.py:8 直接映射无鉴权，ydata/views.py:31-32 有 @login_required；文件名未做 escapejs/json 转义即嵌入脚本，XSS 成立；配合 CSRF-001 的缺失可跨站触发，medium 合理。（最弱一环：最站不住的一环是"拼接进 <script> 的响应是否真的会执行"。核实：两个视图都返回默认 content_type=text/html 的整页 HttpResponse，ylab 把文件名拼进 innerHTML 再内联进脚本参数（ylab/views.py:32-33），文件名含 </script> 即可提前闭合脚本标签注入新脚本；ydata 文件名位于双引号 JS 字符串内（ydata/views.py:91-95），引号即可闭合，无需 </script>。ylab 视图无任何登录/权限装饰器（匿名可达），ydata 为 @login_required。）

**证据。**

`app/ydata/views.py:91-95`

```
    r = u'<script type="text/javascript">window.parent.AfterSubmit("%s","%s","%s","%s","%s");</script>'\
        % (attachment.id, attachment.name,
           reverse ('ydata:show_attachment', args=[attachment.id]),
           reverse ('ydata:download_attachment', args=[attachment.id]),
           notes)
```

`app/ylab/views.py:30-34`

```
    url = '/ydata/attachement/3'
    attachment = req.FILES.values()[0]
    innerHTML = u'<span><a href="%s">%s</a>， %s， <a href="%s/delete">删除</a></span>' % (url, attachment.name, attachment.size, url)
    r = u'<script type="text/javascript">window.parent.AfterSubmit(%s);</script>' % innerHTML
    return HttpResponse(r)
```

<a id="finding-access-003"></a>

### [LOW] ylab update_post_profile 未鉴权的全表写操作

- 编号：`ACCESS-003`
- 类别：`access_control`
- CWE：`CWE-306`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

/lab/update_post_profile 是一个无需登录、接受任意 HTTP 方法的调试视图，对全站所有 Post 做批量重写（updated=touser 重算并 save）。任何匿名访问都会触发全表写操作。

**触发条件。** 匿名访问 GET /lab/update_post_profile（无参数、无身份要求）。

**数据流。** 来源：无任何请求参数或身份（匿名 GET/POST 均可，ylab/urls.py:8 直接映射到视图，无装饰器）→ 危险点：update_post_profile 遍历全部 Post 并逐个 save()（app/ylab/views.py:39-46），把 p.updated 覆盖为 p.created 并重写 touser。入口：anonymous。

**影响。** 任何匿名请求（含被搜索引擎、爬虫或恶意脚本重复触发的 GET）都会全表重写所有帖子的更新时间与 touser 关联，破坏内容顺序与引用关系，可造成数据错乱和持续的写放大。

**修复。** 删除该调试视图，或加 @login_required + @permission_required 并仅接受 POST。

**复核员指出的最弱一环。** 最站不住的一环是"是否真的匿名可达且写全表"。核实 app/ylab/urls.py:8 无装饰器直接映射到 update_post_profile，视图（ylab/views.py:37-48）遍历 Post.objects.all() 并对每行 save() 重写 updated/touser，无方法限制无鉴权。

**判定历史。**

- 复核员同意：匿名 GET 即可触发全表重写，破坏帖子时间与回复关系，属调试接口遗留；low 定级恰当。（最弱一环：最站不住的一环是"是否真的匿名可达且写全表"。核实 app/ylab/urls.py:8 无装饰器直接映射到 update_post_profile，视图（ylab/views.py:37-48）遍历 Post.objects.all() 并对每行 save() 重写 updated/touser，无方法限制无鉴权。）

**证据。**

`app/ylab/views.py:37-48`

```
def update_post_profile(req):
    
    posts = Post.objects.all()
    for p in posts:
        if p.parent:
            p.touser = p.parent.user
        else:
            p.touser = p.topic.user
        p.updated = p.created
        p.save()

    return HttpResponse(u'更新 posts 完成!')
```

`app/ylab/urls.py:6-8`

```
url(r'^time$', 'time', name='time'),
url(r'^uploadsf$', 'upload_single_file', name='uploadsf'),
url(r'^update_post_profile$', 'update_post_profile', name='update_post_profile'),
```

<a id="finding-config-003"></a>

### [LOW] 数据库与邮件凭据以明文弱口令形式提交进仓库

- 编号：`CONFIG-003`
- 类别：`config`
- CWE：`CWE-798`
- 入口身份：无请求入口
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

settings.py 提交了数据库凭据（USER 'ylinux' / PASSWORD '123456'）并预留了直接填写邮件账户密码的位置。当前生效 ENGINE 是 sqlite3（凭据未使用），但一旦按注释切换到 mysql 就会使用弱口令连接数据库。

**触发条件。** 运维将 ENGINE 改为 mysql 并按仓库配置连接数据库时，弱口令生效；邮件口令如按注释填写即泄露。

**影响。** 数据库口令 123456（USER 'ylinux'）已公开，一旦运维按注释把 ENGINE 切回 mysql 并沿用此配置，数据库即用弱口令暴露；同时仓库明示让开发者把邮箱凭据直接填入 settings.py（EMAIL_HOST_PASSWORD），诱导把邮件账户口令提交进版本库。

**修复。** 移除仓库中的数据库口令，改用环境变量或密钥管理；邮件凭据同样外部化；若曾切到 mysql 使用过该口令，立即轮换。

**复核员指出的最弱一环。** 最站不住的一环是"凭据当前是否生效"。核实 settings.py:42-49 当前 ENGINE 为 sqlite3（46 行），USER 'ylinux'/PASSWORD '123456' 确实未被使用；发现已如实限定为"切换 mysql 时生效"且邮件口令为诱导填写位置，low 定级恰当。

**判定历史。**

- 复核员同意：弱口令明文提交进仓库属实，作为配置卫生问题成立。（最弱一环：最站不住的一环是"凭据当前是否生效"。核实 settings.py:42-49 当前 ENGINE 为 sqlite3（46 行），USER 'ylinux'/PASSWORD '123456' 确实未被使用；发现已如实限定为"切换 mysql 时生效"且邮件口令为诱导填写位置，low 定级恰当。）

**证据。**

`settings.py:42-49`

```
DATABASES = {
    'default': {
        # 可选数据库: postgresql_psycopg2 postgresql mysql sqlite3 oracle
        #'ENGINE': 'django.db.backends.mysql',
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'ylinux',
        'USER': 'ylinux',
        'PASSWORD': '123456',
```

`settings.py:29-34`

```
DEFAULT_FROM_EMAIL = ''
EMAIL_HOST = ''
EMAIL_HOST_USER = ''
EMAIL_HOST_PASSWORD = ''
EMAIL_PORT = ''
EMAIL_USE_TLS = True
```

<a id="finding-sensitive-001"></a>

### [LOW] AddUserForm 创建用户时口令未哈希（明文/空口令入库）

- 编号：`SENSITIVE-001`
- 类别：`sensitive_data`
- CWE：`CWE-256`
- 入口身份：管理员或特权用户
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

admin 的 AddUserForm.save() 构造 User 时完全没有处理密码字段（表单包含 password 但 save 未调用 set_password），导致经 /admin/user/add/ 创建的用户口令以空串明文入库，绕过哈希存储逻辑；对比 EditUserForm.save() 显式调用了 set_password。

**触发条件。** 持有 account.create_user 权限的管理员通过 /admin/user/add/ 提交表单。

**影响。** 通过该表单创建的账号口令未哈希（为空串），与既有设计（EditUserForm 调 set_password）不一致，口令安全模型被绕过；相关用户无法正常登录且可能以空口令形态被误用。

**修复。** AddUserForm.save() 中像 EditUserForm 一样调用 user.set_password(self.cleaned_data['password'])，并把 password 字段声明为 PasswordInput 控件。

**复核员指出的最弱一环。** 最站不住的一环是"表单是否真有 password 字段、save 是否真的忽略它"。核实 app/admin/forms.py:75-96：AddUserForm.Meta.fields 含 'password'，但 save() 构造 User 时未处理密码，User.password 为无默认 CharField（account/models.py:165-166）→ 入库空串；对比 EditUserForm.save() 在 115 行显式调用 set_password，差异属实。

**判定历史。**

- 复核员同意：管理员通过该表单创建的用户其填写的口令被静默丢弃，哈希模型被绕过；影响限于具备 account.create_user 权限的管理员操作，low 合理。（最弱一环：最站不住的一环是"表单是否真有 password 字段、save 是否真的忽略它"。核实 app/admin/forms.py:75-96：AddUserForm.Meta.fields 含 'password'，但 save() 构造 User 时未处理密码，User.password 为无默认 CharField（account/models.py:165-166）→ 入库空串；对比 EditUserForm.save() 在 115 行显式调用 set_password，差异属实。）

**证据。**

`app/admin/forms.py:84-91`

```
    def save (self):
        user = User(username=self.cleaned_data['username'],
                email=self.cleaned_data['email'],
                is_staff=self.cleaned_data['is_staff'],
                is_active=self.cleaned_data['is_active'],
                is_superuser=self.cleaned_data['is_superuser'],
                )
        user.save()
```

`app/admin/forms.py:108-116`

```
    def save (self):
        user = super(EditUserForm, self).save(commit=False)
        user.username=self.cleaned_data['username']
        user.email=self.cleaned_data['email']
        user.is_staff=self.cleaned_data['is_staff']
        user.is_active=self.cleaned_data['is_active']
        user.is_superuser=self.cleaned_data['is_superuser']
        user.set_password(self.cleaned_data['password'])
        user.save()
```

## 需要再确认的问题

无。

## 复核员否决、尚未改判的问题

无。

## 已排除的可疑点

无。

## 未完成判断的候选

无。

## 范围

覆盖范围：settings.py 与根 urls；全部 app（home/admin/account/wiki/ydata/bbs/blog/me/ylab/syndication/sessions）的 views、urls、forms、models；自定义会话与认证中间件/后端/装饰器；lib 下 django_xmlrpc 全套与 ylinux_xmlrpc 全部公开方法；markdown 2.0.3 渲染核心（safe_mode 语义）；templates 中 |safe 使用点逐一核对；注册/密码重置令牌生成与校验路径。未覆盖：tests.py、sessions 的 cache/file/cached_db 后端（SESSION_ENGINE 未配置，默认指向未安装的 django.contrib.sessions.backends.db，属运行期问题）、doc/ 与 scripts/ 客户端脚本的完整审计。

## 局限

静态审计无法验证运行环境（如部署时是否覆盖 DEBUG/SECRET_KEY、Web 服务器与进程权限、网络层是否启用 HTTPS、生产环境 /ymedia/ 的实际托管方式）；未对 Django 框架本体（系统安装版本）做漏洞核对；未运行任何动态验证（无 payload 执行）；lib/markdown 仅阅读了与渲染安全相关的核心路径；tests 与 scripts/ 客户端脚本仅抽查。部分组合攻击（如上传响应 XSS 与 CSRF 的联动）依赖浏览器对 multipart 文件名的处理，实际可利用性受客户端实现影响；令牌枚举（CRYPTO-002）的实际耗时取决于服务器性能与并发容忍度。

## 复核意见

本轮只复核 critic_verdict 为空的两条新发现（CRYPTO-002、FILE-002），其余 agree 条目沿用上一轮结论。CRYPTO-002：重读 app/account/models.py:351-440、views.py:165-235、forms.py:145-170、settings.py:60-110，确认 salt 仅 5 个十六进制字符（2^20 空间）、activation_key=sha1(salt+email)、password_reset_request 匿名可为任意已注册邮箱创建/轮换 Register 行、password_reset 无时效无速率限制且错误响应可区分、SetPasswordForm.save 直接 set_password，枚举接管账号成立，high 维持。FILE-002：重读 app/ydata/views.py:25-100、ydata/settings.py:60-95、settings.py:60-110、urls.py:49-64、scripts/.htaccess:1-43，确认上传仅查大小无类型白名单、落盘 MEDIA_ROOT/ydata/attachments、DEBUG 下 static.serve 与生产 .htaccess 均按扩展名同源静态下发，.html 以 text/html 执行成立，medium 维持。两点保留意见（不影响结论）：CRYPTO-002 的枚举约需百万级请求，可行性取决于部署性能与是否有反向代理/防火墙层限速，但仓库本身确无任何限制，定级仍站得住；FILE-002 生产侧同源执行依赖 ymedia 目录位于 Web 根下且由 .htaccess 静态服务，发现已如实以"仓库默认配置+生产沿用静态托管"为前提表述。无其他异议。

## 复核缺口

- `G1`（已回应）密码重置/注册激活令牌熵仅约 20 bit 且来自可预测 PRNG：RegisterManager.create_profile 与 Register.reset_activation_key 用 sha1(str(random.random()))[:5] 作盐再对 email 做 sha1（app/account/models.py:361-369、424-430），而 /account/password/reset/<key>/（app/account/views.py:202-208）只按 key 查库、不校验时效、无速率限制——攻击者知道目标邮箱即可在 2^20 空间内枚举出重置链接并接管任意账号。CRYPTO-001/CONFIG-002 只覆盖了口令哈希和 SECRET_KEY，未覆盖该令牌熵问题，属于独立的账号接管路径。
  - 审计员回应：已通过 search_code + read_file 重新核实实现：app/account/models.py:364,367,427,430 显示 salt = sha_constructor(str(random.random())).hexdigest()[:5]（5 个十六进制字符，约 20 bit），activation_key = sha_constructor(salt+email).hexdigest()；app/account/views.py:205-219 的 password_reset 只按 key 查库、无时效校验、无速率限制，命中即渲染 SetPasswordForm 并可保存新口令。该路径独立于 CRYPTO-001/CONFIG-002，已新增 finding CRYPTO-002（high，CWE-330，anonymous）。
- `G2`（已回应）上传接口对文件类型/扩展名无任何白名单，且文件以客户端文件名原样落盘到 MEDIA_ROOT 下、由同源 /ymedia/ 静态服务（DEBUG 下 django.views.static.serve，生产下若沿用 Web 服务器托管同样生效）：即使不做路径穿越，登录用户也可上传 .html/.svg 等文件获得同源 URL，形成持久的存储型 XSS/钓鱼页面托管。FILE-001 只覆盖了路径穿越写入，未覆盖"合法落盘文件被同源静态服务渲染执行"这一独立风险。
  - 审计员回应：已 read_file app/ydata/views.py:31-100 核实：上传仅检查大小（41 行），无扩展名/MIME 白名单；78-84 行以客户端文件名写入 MEDIA_ROOT/ydata/attachments，settings.py:74-75 MEDIA_URL='/ymedia/' 同源，urls.py:59-63 在 DEBUG=True 下由 django.views.static.serve（show_indexes=True）同源服务该目录，.html 按 text/html 下发执行。已新增 finding FILE-002（CWE-434，medium，registered_open，data_flow 完整）；与 FILE-001（路径穿越）为同一上传点两个独立风险，故分别记录。
