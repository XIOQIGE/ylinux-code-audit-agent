# django.nV 应用安全审计报告

- 目标：`https://github.com/nVisium/django.nV`，commit `a48901f106da4888417339b7b44b8ed56b64c63f`
- 模型：审计员 `deepseek-v4-pro`，复核员 `kimi-k3`
- 时间：2026-10-21T10:55:11+08:00 → 2026-10-21T11:19:06+08:00
- 结论：确认 19 个问题，最高严重性为 critical。
- 统计：已确认 19，待再确认 0，已排除 0；引用核对 43 条，未通过 0 条

> 这次运行中途中断（原因见文末“运行警告”），复核没有做完，标“未复核”的条目只经过审计员判断。

## 发现总表

| 严重性 | 编号 | 问题 | 入口身份 | 状态 | 复核员 | 位置 |
| --- | --- | --- | --- | --- | --- | --- |
| critical | [`AUTHZ-001`](#finding-authz-001) | profile_by_id 未授权 IDOR：匿名可改任意用户密码（账户接管） | 匿名 | confirmed | 同意 | `taskManager/views.py:710` |
| critical | [`AUTHZ-004`](#finding-authz-004) | 注册表单 mass assignment：匿名可自助注册 is_superuser 超级用户 | 匿名 | confirmed | 未复核 | `taskManager/forms.py:71` |
| critical | [`DESER-001`](#finding-deser-001) | 硬编码 SECRET_KEY + signed_cookies + PickleSerializer 可伪造会话并反序列化 RCE | 匿名 | confirmed | 未复核 | `taskManager/settings.py:24` |
| critical | [`RCE-001`](#finding-rce-001) | 上传文件名拼接进 os.system 导致 shell 命令注入（未授权 RCE） | 匿名 | confirmed | 同意 | `taskManager/misc.py:31` |
| high | [`AUTH-001`](#finding-auth-001) | 弱随机密码重置令牌 + 无速率限制，可暴力枚举重置任意账号口令 | 匿名 | confirmed | 同意 | `taskManager/views.py:788` |
| high | [`AUTHZ-002`](#finding-authz-002) | manage_groups POST 分支缺少权限检查，普通用户可提权到 admin_g | 可自助注册的用户 | confirmed | 未复核 | `taskManager/views.py:120` |
| high | [`AUTHZ-003`](#finding-authz-003) | 任务/笔记/项目/文件接口普遍 IDOR：匿名可改删任意数据并下载文件 | 匿名 | confirmed | 同意 | `taskManager/views.py:275` |
| high | [`SQLI-001`](#finding-sqli-001) | upload 视图用字符串格式化拼接原始 SQL，存在 SQL 注入 | 匿名 | confirmed | 同意 | `taskManager/views.py:182` |
| high | [`XSS-001`](#finding-xss-001) | 任务标题/描述 \|safe 渲染导致匿名可触发的存储型 XSS | 匿名 | confirmed | 同意 | `taskManager/views.py:246` |
| high | [`XSS-002`](#finding-xss-002) | username 经 \|safe 渲染，配合未授权改名构成存储型 XSS | 匿名 | confirmed | 同意 | `taskManager/views.py:718` |
| medium | [`CONFIG-001`](#finding-config-001) | DEBUG/TEMPLATE_DEBUG 开启且 ALLOWED_HOSTS 为空，错误页泄露配置与堆栈 | 无请求入口 | confirmed | 同意 | `taskManager/settings.py:27` |
| medium | [`CRYPTO-001`](#finding-crypto-001) | 使用 MD5PasswordHasher 存储口令哈希，且默认账号哈希随仓库公开 | 无请求入口 | confirmed | 同意 | `taskManager/settings.py:100` |
| medium | [`FILE-001`](#finding-file-001) | 任意文件（含 HTML/JS）落盘 Web 可服务目录并可同源访问 | 匿名 | confirmed | 未复核 | `taskManager/misc.py:26` |
| medium | [`REDIR-001`](#finding-redir-001) | logout 开放重定向（redirect 参数未校验） | 匿名 | confirmed | 同意 | `taskManager/views.py:385` |
| medium | [`XSS-003`](#finding-xss-003) | 搜索参数 q \|safe 渲染导致反射型 XSS | 匿名 | confirmed | 同意 | `taskManager/views.py:661` |
| medium | [`XSS-004`](#finding-xss-004) | settings 视图用 \|safe 渲染 request.META：信息泄露 + 请求头反射 XSS | 匿名 | confirmed | 未复核 | `taskManager/views.py:837` |
| low | [`AUTH-002`](#finding-auth-002) | 登录接口无速率限制/锁定，可无限在线爆破口令 | 匿名 | confirmed | 未复核 | `taskManager/views.py:390` |
| low | [`CSRF-001`](#finding-csrf-001) | 多个口令相关端点被 csrf_exempt 豁免 CSRF 防护 | 匿名 | confirmed | 同意 | `taskManager/views.py:779` |
| low | [`INFO-001`](#finding-info-001) | 登录接口用户名枚举（错误文案可区分账号是否存在） | 匿名 | confirmed | 同意 | `taskManager/views.py:391` |

下面的发现由 Agent 写入，每条引用都回到源码核对过。审计员综述写在复核之前，单条发现的状态以复核后为准。线索处置、读过的文件、阶段记录、工具序列和引用核对见 `appendix.md`，关键决策见 `decisions.md`。

## 审计员综述

这是一个故意留有大量漏洞的教学型 Django 1.8.3 应用（django.nV）。审计确认 17 个问题，其中 5 个 critical：1) 上传文件名拼进 os.system 的未授权 shell 命令注入（RCE-001）；2) 硬编码 SECRET_KEY + signed_cookies 会话 + PickleSerializer 可伪造会话并反序列化执行任意代码（DESER-001）；3) profile_by_id 未授权改任意账号密码的账户接管（AUTHZ-001）；4) 注册表单 mass assignment，匿名可自助注册 is_superuser 超级用户（AUTHZ-004）；5) upload 视图的原始 SQL 注入（SQLI-001，high 中最高一档）。其余问题包括普遍 IDOR（AUTHZ-003）、manage_groups 提权（AUTHZ-002）、多处 |safe 存储型/反射型 XSS（XSS-001~004）、开放重定向（REDIR-001）、弱随机密码重置令牌（AUTH-001）、MD5 口令哈希（CRYPTO-001）、任意文件落盘 Web 可服务目录（FILE-001）、DEBUG 开启（CONFIG-001）、登录无爆破防护（AUTH-002）、用户名枚举（INFO-001）与 CSRF 豁免（CSRF-001）。多数高危问题入口匿名可达，整体安全态势极差。

## 风险概览

最高风险集中在五条匿名可达的 RCE/接管链：1) /taskManager/<id>/upload/ 的 name 参数既进 os.system（shell 注入）又进裸 SQL（SQL 注入），匿名即可触达；2) 仓库公开的 SECRET_KEY 配合 signed_cookies+PickleSerializer，任何人都能伪造会话 Cookie，验签通过后 pickle 反序列化执行任意代码；3) /taskManager/profile/<user_id> 无认证且 csrf_exempt，匿名可重置任意账号（含 admin）口令；4) 注册表单可直接提交 is_superuser=true 自助成为超级用户；5) 上述注入/越权可读库后，MD5 口令哈希可快速破解。次高风险为系统性访问控制缺失：任务/笔记/项目/文件接口无归属校验可匿名改删、manage_groups 普通注册用户可自我提权到 admin_g、多处存储型 XSS（任务标题/描述、username、上传 HTML 文件）可窃取会话（SESSION_COOKIE_HTTPONLY=False 加剧）。

## 已确认的问题

<a id="finding-authz-001"></a>

### [CRITICAL] profile_by_id 未授权 IDOR：匿名可改任意用户密码（账户接管）

- 编号：`AUTHZ-001`
- 类别：`access_control`
- CWE：`CWE-306`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

profile_by_id 无登录检查、无所有者校验且 csrf_exempt：URL 中的 user_id 决定被改对象，POST 参数直接改用户名/邮箱/密码，任何匿名用户都能重置任意账号口令（含管理员），属于未授权账户接管。

**触发条件。** 匿名 POST /taskManager/profile/<user_id>，body 携带 password=<新口令>（表单校验仅要求 first_name/last_name/email 可空、picture 可选）。

**数据流。** 来源：POST 参数 username/first_name/last_name/email/password（views.py:718-727）→ 目标对象由 URL 中的 user_id 决定（views.py:712 User.objects.get(pk=user_id)，无任何认证/授权检查）→ 危险点 views.py:726-727 user.set_password(request.POST.get('password')) 直接改任意账号口令。视图被 @csrf_exempt 修饰（views.py:710），无 CSRF 防护。入口：匿名。

**影响。** 匿名攻击者可以把任意账号（包括 admin/is_superuser）的密码改成自己选择的值，实现完整账户接管；也可以改写其用户名、邮箱，并借该接口设置恶意 username 触发存储型 XSS。

**修复。** 给该视图加 login_required 和所有者检查（request.user.id == user_id 或管理员权限），去掉 @csrf_exempt，并只允许本人修改自己的 profile；不要接受任意 POST 字段直接写 User 对象。

**复核员指出的最弱一环。** 最弱一环是 ProfileForm 的 is_valid() 是否会拦住只带 password 的 POST（若校验失败则进不了改密分支）。核实结果：ProfileForm（forms.py:84-89）四个字段全部 required=False，空 POST 也能通过 is_valid()；进入分支后 user.set_password(request.POST.get('password'))（views.py:726-727）无条件执行；视图 @csrf_exempt（:710）、无登录检查、无所有者校验，目标对象由 URL user_id 直接 User.objects.get（:712）；taskManager_urls.py:43 确认路由可达。

**判定历史。**

- 复核员同意：重读 views.py:710-735、forms.py:84-89、taskManager_urls.py:43-44。匿名即可重置任意账号（含 admin）口令，证据引用逐行吻合，账户接管 critical 定级准确。（最弱一环：最弱一环是 ProfileForm 的 is_valid() 是否会拦住只带 password 的 POST（若校验失败则进不了改密分支）。核实结果：ProfileForm（forms.py:84-89）四个字段全部 required=False，空 POST 也能通过 is_valid()；进入分支后 user.set_password(request.POST.get('password'))（views.py:726-727）无条件执行；视图 @csrf_exempt（:710）、无登录检查、无所有者校验，目标对象由 URL user_id 直接 User.objects.get（:712）；taskManager_urls.py:43 确认路由可达。）

**证据。**

`taskManager/views.py:710-712`

```
@csrf_exempt
def profile_by_id(request, user_id):
    user = User.objects.get(pk=user_id)
```

`taskManager/views.py:718-719`

```
            if request.POST.get('username') != user.username:
                user.username = request.POST.get('username')
```

`taskManager/views.py:726-727`

```
            if request.POST.get('password'):
                user.set_password(request.POST.get('password'))
```

<a id="finding-authz-004"></a>

### [CRITICAL] 注册表单 mass assignment：匿名可自助注册 is_superuser 超级用户

- 编号：`AUTHZ-004`
- 类别：`access_control`
- CWE：`CWE-915`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：未复核

注册表单 UserForm 的 exclude 未排除 is_superuser/is_staff，二者仍是 ModelForm 字段；register 视图对匿名开放并直接 user_form.save()，攻击者 POST is_superuser=true 即可自助注册超级用户（mass assignment 提权）。

**触发条件。** 匿名 POST /taskManager/register/，除常规字段外附带 is_superuser=true（Django BooleanField 接受 'true'/'1'/'True'），表单校验通过后 save() 落库。

**数据流。** 来源：POST 参数 is_superuser/is_staff（匿名可提交）→ views.py:429 UserForm(data=request.POST) 绑定 ModelForm → forms.py:73-75 exclude 仅排除 groups/user_permissions/last_login/date_joined/is_active，is_superuser 与 is_staff 仍是表单字段（Django ModelForm 由模型推导字段）→ 危险点 views.py:434 user_form.save() 把攻击者提交的 is_superuser=true 直接落库。入口：匿名（register 视图无认证、注册对所有人开放）。

**影响。** 匿名攻击者提交带 is_superuser=true（及 is_staff=true）的注册请求即可创建自己的超级用户账号，直接获得 Django admin（/admin/）与全站管理员权限，绕过一切权限模型；同样可借 is_staff=true 获取 staff 权限。

**修复。** UserForm 改用 fields 白名单（如 ['username','first_name','last_name','email','password']），或在 save 前强制覆盖 is_superuser/is_staff/is_active 为默认值；不要用 exclude 推断可编辑字段。

**证据。**

`taskManager/forms.py:71-75`

```
class UserForm(forms.ModelForm):
    """ User registration form """
    class Meta:
        model = User
        exclude = ['groups', 'user_permissions', 'last_login', 'date_joined', 'is_active']
```

`taskManager/views.py:429-434`

```
        user_form = UserForm(data=request.POST)

        # If the two forms are valid...
        if user_form.is_valid():
            # Save the user's form data to the database.
            user = user_form.save()
```

<a id="finding-deser-001"></a>

### [CRITICAL] 硬编码 SECRET_KEY + signed_cookies + PickleSerializer 可伪造会话并反序列化 RCE

- 编号：`DESER-001`
- 类别：`deserialization`
- CWE：`CWE-502`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：未复核

SECRET_KEY 硬编码提交进仓库，同时会话使用 signed_cookies 引擎 + PickleSerializer 序列化：知道密钥的人可以伪造签名会话 Cookie，把恶意 pickle 送入服务端反序列化，达到未授权远程代码执行。

**触发条件。** 任何人从仓库拿到 settings.py:24 的 SECRET_KEY 后，构造签名会话 Cookie 发给任意端点即可；无需任何账号。

**数据流。** 配置来源：settings.py:24 硬编码 SECRET_KEY（已随仓库公开）→ settings.py:104 SESSION_ENGINE=signed_cookies、settings.py:109 SESSION_SERIALIZER=PickleSerializer。攻击路径：攻击者用已知 SECRET_KEY 对任意 pickle 负载生成有效签名并伪造 sessionid Cookie → 服务端验签通过（攻击者持有密钥，验签形同虚设）后，由 PickleSerializer 反序列化该载荷，pickle 反序列化即执行攻击者构造的代码。入口为任意匿名请求（SessionMiddleware 在 settings.py:45 全局启用）。

**影响。** SECRET_KEY 已在公开仓库中，任何拿到该值的人都能伪造带任意 pickle 负载的签名会话 Cookie；验签通过后服务端反序列化该负载即执行任意代码（未授权 RCE、冒充任意用户会话）。同时 SESSION_COOKIE_HTTPONLY=False 使会话 Cookie 可被前端脚本读取，配合 XSS 可窃取会话。

**修复。** 轮换并保密 SECRET_KEY（从环境变量读取、不入库）；改用数据库/缓存会话后端与 JSONSerializer；把 SESSION_COOKIE_HTTPONLY 设为 True。

**判定历史。**

- 复核员同意：重读 settings.py 全文确认三项配置与硬编码密钥。已知密钥 + signed_cookies + PickleSerializer 构成教科书式的伪造会话 Cookie 反序列化 RCE，无需任何账号，critical 合理。仅 data_flow 中验签/反序列化先后顺序的表述有瑕疵，已在 weakest_point 指出，不影响成立。（最弱一环：最弱一环是 data_flow 中“服务端先反序列化（pickle 执行任意代码）再验签”的顺序描述，以及 signed_cookies 配置是否真的生效（INSTALLED_APPS 未含 django.contrib.sessions）。核实结果：Django 的 signing.loads 实际是先验签、后对载荷调用 serializer 反序列化，该句机制描述不准确；但这不影响结论——SECRET_KEY 在 settings.py:24 硬编码且随仓库公开，攻击者自己就能产出合法签名，验签通过后恶意 pickle 照常被反序列化。配置生效性：signed_cookies 后端不依赖 sessions 应用入库，SessionMiddleware 在 MIDDLEWARE_CLASSES（settings.py:45）中，任意视图访问 request.user/session 即触发会话加载与反序列化；SESSION_ENGINE（:104）、PickleSerializer（:109）、SESSION_COOKIE_HTTPONLY=False（:110）均逐行确认。）

**证据。**

`taskManager/settings.py:24-24`

```
SECRET_KEY = '0yxzudryd8)-%)(fz&7q-!v&cq1u6vbfoc4u7@u_&i)b@4eh^q'
```

`taskManager/settings.py:104-104`

```
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
```

`taskManager/settings.py:109-110`

```
SESSION_SERIALIZER = "django.contrib.sessions.serializers.PickleSerializer"
SESSION_COOKIE_HTTPONLY = False
```

<a id="finding-rce-001"></a>

### [CRITICAL] 上传文件名拼接进 os.system 导致 shell 命令注入（未授权 RCE）

- 编号：`RCE-001`
- 类别：`injection`
- CWE：`CWE-78`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

misc.py 的 store_uploaded_file 把用户提供的 title 直接拼进 os.system("mv ...") 命令字符串。title 来自上传表单的 name 参数（views.upload），以及 profile_by_id 中由 username 组成的文件名。upload 视图没有登录检查，匿名用户即可触发任意 shell 命令执行。

**触发条件。** POST /taskManager/<任意project_id>/upload/，表单字段 name 填入含 shell 元字符的值（上传页对匿名用户也渲染 CSRF token）；或 POST /taskManager/profile/<user_id> 携带 picture 文件时 username 进入 title。

**数据流。** 来源：views.py:178 request.POST.get('name') → misc.py:24 store_uploaded_file(title=name) → 危险点 misc.py:33-39 os.system("mv " + temporary_file_path() + " " + upload_dir + "/" + title)。入口 upload 视图（views.py:170-201）无任何认证检查，匿名可达；第二条路径：profile_by_id（views.py:729-730）把 user.username 拼入 title。

**影响。** 匿名攻击者可在服务器上以 Web 进程权限执行任意操作系统命令，实现完全控制（写 webshell、反弹 shell、读取数据库等）。

**修复。** 不要用 os.system 处理文件名：改用 shutil.move 或 os.rename 等不经过 shell 的 API；文件名应由服务端生成（如 uuid），并把上传目录移出 Web 根目录。

**复核员指出的最弱一环。** 最弱一环是 entry_role=anonymous：全局 CsrfViewMiddleware 开启且 upload 未加 csrf_exempt，匿名直连 POST 是否真可达？另外 form.is_valid() 是否可能过滤掉 shell 元字符。核实结果：upload 视图（views.py:170-201）完全没有认证检查，GET 分支对匿名渲染带 {% csrf_token %} 的表单，攻击者可先取 token 再 POST，CSRF 不构成访问控制；ProjectFileForm（forms.py:78-81）的 name 仅为 CharField(max_length=300)，不过滤任何元字符；settings.py:58-59 配置 TemporaryFileUploadHandler，保证 temporary_file_path() 存在；misc.py:33-39 的 os.system("mv " + ... + title) 原样确认；第二路径 profile_by_id（views.py:728-730）把可被匿名改写的 user.username 拼进 title 同样确认。

**判定历史。**

- 复核员同意：重读 misc.py 全文、views.py 166-201 与 700-735、forms.py、settings.py 上传句柄配置。数据来源（request.POST['name'] / user.username）真实不可信、无任何校验或转义即进入 shell 命令字符串，入口匿名可达，证据引用与代码一致。匿名命令注入以 Web 进程权限执行，critical 合理。（最弱一环：最弱一环是 entry_role=anonymous：全局 CsrfViewMiddleware 开启且 upload 未加 csrf_exempt，匿名直连 POST 是否真可达？另外 form.is_valid() 是否可能过滤掉 shell 元字符。核实结果：upload 视图（views.py:170-201）完全没有认证检查，GET 分支对匿名渲染带 {% csrf_token %} 的表单，攻击者可先取 token 再 POST，CSRF 不构成访问控制；ProjectFileForm（forms.py:78-81）的 name 仅为 CharField(max_length=300)，不过滤任何元字符；settings.py:58-59 配置 TemporaryFileUploadHandler，保证 temporary_file_path() 存在；misc.py:33-39 的 os.system("mv " + ... + title) 原样确认；第二路径 profile_by_id（views.py:728-730）把可被匿名改写的 user.username 拼进 title 同样确认。）

**证据。**

`taskManager/misc.py:31-39`

```
    # A1: Injection (shell)
    # Let's avoid the file corruption race condition!
    os.system(
        "mv " +
        uploaded_file.temporary_file_path() +
        " " +
        "%s/%s" %
        (upload_dir_path,
         title)
```

`taskManager/views.py:178-179`

```
            name = request.POST.get('name', False)
            upload_path = store_uploaded_file(name, request.FILES['file'])
```

<a id="finding-auth-001"></a>

### [HIGH] 弱随机密码重置令牌 + 无速率限制，可暴力枚举重置任意账号口令

- 编号：`AUTH-001`
- 类别：`crypto`
- CWE：`CWE-330`
- 入口身份：匿名
- 置信度：`medium`
- 状态：`confirmed`
- 复核员：同意

密码重置令牌由 os.urandom(6) 的十进制表示截取 6 位生成，熵极低；reset_password 接口无 CSRF 防护且无速率限制，令牌可被暴力枚举，导致任意账号接管。

**触发条件。** 先对受害者邮箱 POST /taskManager/forgot_password/ 触发重置邮件，再在 10 分钟内对 /taskManager/reset_password/ 暴力枚举 reset_token 与新口令。

**数据流。** 来源：forgot_password 的 token 生成逻辑 views.py:789-796（os.urandom(6) 的每个字节转十进制字符串后取前 6 个字符，实际有效空间远小于 10^6）→ 存入 UserProfile.reset_token（views.py:795）→ 危险点 reset_password（views.py:744-747）按 POST 的 reset_token 查找并重置口令，视图 @csrf_exempt（views.py:739-740），token 10 分钟有效（views.py:796）。入口：匿名。

**影响。** 攻击者对目标邮箱触发重置邮件后，可在 10 分钟窗口内以有限空间（约 10^4~10^5 个可能值）暴力枚举 reset_token（无速率限制、无 CSRF 校验），成功后把目标账号口令改为自己选择的值，造成账户接管。

**修复。** 用 secrets.token_urlsafe 生成至少 128 位熵的令牌并只存哈希值；对重置接口加速率限制与 CSRF 校验；缩短有效期并限制每邮箱的重置频率。

**复核员指出的最弱一环。** 最弱一环是令牌实际有效空间是否如宣称的那样小（若接近 10^6 且 10 分钟窗口，现实爆破存疑，这正是 confidence=medium 的点）。核实结果：views.py:788-796 中每字节 str(x) 为 1-3 位十进制，拼接后取前 6 字符——空间显著小于 10^6 且分布不均（小数字字节占比高，低值前缀远更常见），有效猜测集在 10^4~10^5 量级，10 分钟窗口内无速率限制（reset_password @csrf_exempt :739、无节流）可枚举；命中后 :766 直接 set_password。用户档案的 reset_token 仅在 forgot_password 成功后设置，流程闭环成立。

**判定历史。**

- 复核员同意：重读 views.py:739-775、779-809。弱熵令牌 + 无速率限制 + csrf_exempt + 按令牌直接改密的组合属实，可导致任意账号接管；利用的现实性依赖窗口内请求量，auditor 把 confidence 定为 medium 是恰当的自我校准，high 定级与账户接管影响相符。（最弱一环：最弱一环是令牌实际有效空间是否如宣称的那样小（若接近 10^6 且 10 分钟窗口，现实爆破存疑，这正是 confidence=medium 的点）。核实结果：views.py:788-796 中每字节 str(x) 为 1-3 位十进制，拼接后取前 6 字符——空间显著小于 10^6 且分布不均（小数字字节占比高，低值前缀远更常见），有效猜测集在 10^4~10^5 量级，10 分钟窗口内无速率限制（reset_password @csrf_exempt :739、无节流）可枚举；命中后 :766 直接 set_password。用户档案的 reset_token 仅在 forgot_password 成功后设置，流程闭环成立。）

**证据。**

`taskManager/views.py:788-796`

```
            # Generate secure random 6 digit number
            res = ""
            nums = [x for x in os.urandom(6)]
            for x in nums:
                res = res + str(x)

            reset_token = res[:6]
            reset_user.userprofile.reset_token = reset_token
```

`taskManager/views.py:739-740`

```
@csrf_exempt
def reset_password(request):
```

`taskManager/views.py:744-747`

```
        reset_token = request.POST.get('reset_token')

        try:
            userprofile = UserProfile.objects.get(reset_token = reset_token)
```

<a id="finding-authz-002"></a>

### [HIGH] manage_groups POST 分支缺少权限检查，普通用户可提权到 admin_g

- 编号：`AUTHZ-002`
- 类别：`access_control`
- CWE：`CWE-862`
- 入口身份：可自助注册的用户
- 置信度：`high`
- 状态：`confirmed`
- 复核员：未复核

manage_groups 的 POST 分支没有检查 can_change_group 权限（该检查只在 GET 分支），任何已登录用户都能把任意用户加入 admin_g 组，实现提权。

**触发条件。** 登录任意自助注册账号后 POST /taskManager/manage_groups/，body 为 userid=<自己的id>&accesslevel=admin_g。

**数据流。** 来源：POST 参数 accesslevel/userid（views.py:122-124）→ 危险点 views.py:130-137：按 POST 值创建/获取 Group 并把任意用户加入 admin_g/project_managers。POST 分支只检查 is_authenticated（views.py:116），而 has_perm('can_change_group') 只在 GET 分支（views.py:155）检查。入口：任何自助注册的登录用户（注册接口对匿名开放）。

**影响。** 任意注册用户把自己（或他人）加进 admin_g / project_managers 组，获得管理员与项目管理权限，实现垂直越权；配合其他缺失鉴权的视图可进一步读写全站数据。

**修复。** 在 POST 分支同样校验 user.has_perm('can_change_group')，或把权限校验放到视图入口统一处理。accesslevel 虽有白名单（views.py:126），但普通用户可提交其中的 admin_g，根因是 POST 分支的权限校验缺失。

**判定历史。**

- 复核员同意：重读 views.py:112-165 与 register 视图。POST 提权路径清晰：登录任意自助注册账号 → POST userid+accesslevel=admin_g → 加入管理组。证据与代码一致，high 合理。（最弱一环：最弱一环是“POST 分支缺少权限检查”这一核心论断，以及 remediation 中隐含的“accesslevel 无白名单”说法。核实结果：views.py:116 POST 分支只检查 is_authenticated，has_perm('can_change_group') 仅出现在 GET 分支（:155），核心论断成立；accesslevel 实际有白名单（:126），但白名单本身就包含 admin_g，任意登录用户仍可把自己加入 admin_g，remediation 措辞略有偏差但不影响漏洞成立。entry_role=registered_open 经 register 视图（views.py:421-463，无认证）确认。）

**证据。**

`taskManager/views.py:120-124`

```
        if request.method == 'POST':

            post_data = request.POST.dict()

            accesslevel = post_data["accesslevel"].strip()
```

`taskManager/views.py:130-138`

```
                    grp = Group.objects.get(name=accesslevel)
                except Group.DoesNotExist:
                    grp = Group.objects.create(name=accesslevel)
                specified_user = User.objects.get(pk=post_data["userid"])
                # Check if the user even exists
                if specified_user is None:
                    return redirect('/taskManager/', {'permission': False})
                specified_user.groups.add(grp)
                specified_user.save()
```

`taskManager/views.py:155-155`

```
            if user.has_perm('can_change_group'):
```

<a id="finding-authz-003"></a>

### [HIGH] 任务/笔记/项目/文件接口普遍 IDOR：匿名可改删任意数据并下载文件

- 编号：`AUTHZ-003`
- 类别：`access_control`
- CWE：`CWE-639`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

task_edit/task_delete/task_complete、note_edit/note_delete、project_edit/project_delete、download 等视图没有登录与资源归属检查，对象 ID 直接来自 URL，匿名用户可越权改、删、读任意记录（IDOR）。

**触发条件。** 匿名访问如 /taskManager/<project_id>/task_edit/<task_id>（POST）、/taskManager/<project_id>/project_delete/、/taskManager/download/<file_id>/ 等，替换 ID 即可操作他人资源。

**数据流。** 来源：URL 参数 project_id/task_id/note_id/file_id → 危险点：task_edit（views.py:275-289）直接 Task.objects.get(pk=task_id) 后写入并 save，只比较 task.project==proj（两个值都由攻击者选择）；project_delete（views.py:376-380）与 download（views.py:206-213）完全无归属/登录检查。入口：匿名（各视图没有 login_required，CSRF token 可从页面获取）。

**影响。** 匿名攻击者可以修改/删除任意任务、项目、笔记，并下载任意 File 记录对应的文件内容；结合 SQL 注入甚至能控制 File.path 指向任意本地文件实现任意文件读取。

**修复。** 所有数据操作视图加 login_required 与资源所有者校验（项目成员/任务分派者），删除/下载前校验归属；不要只做 task.project==proj 这类可由攻击者同时指定的比较。

**复核员指出的最弱一环。** 最弱一环是 task_edit 里 task.project == proj 的比较是否构成实质防护（若有效则“改任意任务”不成立）。核实结果：project_id 与 task_id 都来自 URL（taskManager_urls.py:67-72），攻击者同时任选，总能给出匹配的一对，比较形同虚设；project_delete（views.py:376-380）与 download（:206-217）连该比较都没有，完全无登录/归属检查；task_delete（:299-306）、task_complete（:311-319）、note_edit（:554-576）、note_delete（:581-590）同型，均已重读确认。

**判定历史。**

- 复核员同意：重读 views.py:206-217、273-319、376-380、554-590 及对应路由。各视图匿名可达、对象 ID 直接来自 URL、无归属校验，IDOR 集群属实；download 无认证读取 File.path 指向内容，与 SQLI-001 联动可任意文件读取的说法成立。high 合理。（最弱一环：最弱一环是 task_edit 里 task.project == proj 的比较是否构成实质防护（若有效则“改任意任务”不成立）。核实结果：project_id 与 task_id 都来自 URL（taskManager_urls.py:67-72），攻击者同时任选，总能给出匹配的一对，比较形同虚设；project_delete（views.py:376-380）与 download（:206-217）连该比较都没有，完全无登录/归属检查；task_delete（:299-306）、task_complete（:311-319）、note_edit（:554-576）、note_delete（:581-590）同型，均已重读确认。）

**证据。**

`taskManager/views.py:275-276`

```
    proj = Project.objects.get(pk=project_id)
    task = Task.objects.get(pk=task_id)
```

`taskManager/views.py:286-289`

```
            task.title = task_title
            task.text = text
            task.completed = True if task_completed == "1" else False
            task.save()
```

`taskManager/views.py:376-380`

```
def project_delete(request, project_id):
    # IDOR
    project = Project.objects.get(pk=project_id)
    project.delete()
    return redirect('/taskManager/dashboard')
```

`taskManager/views.py:206-213`

```
def download(request, file_id):

    file = File.objects.get(pk=file_id)
    abspath = open(
        os.path.dirname(
            os.path.realpath(__file__)) +
        file.path,
        'rb')
```

<a id="finding-sqli-001"></a>

### [HIGH] upload 视图用字符串格式化拼接原始 SQL，存在 SQL 注入

- 编号：`SQLI-001`
- 类别：`injection`
- CWE：`CWE-89`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

upload 视图用 cursor.execute 执行由 % 字符串格式化拼成的 INSERT 语句，name（用户可控）未经参数化直接进入 SQL。upload 无登录检查，匿名用户可注入任意 SQL 片段（如用子查询把其他表数据写进 file 记录，再经 download 视图读取，或用表达式篡改数据）。

**触发条件。** POST /taskManager/<project_id>/upload/ 时在 name 字段放入带单引号的 SQL 片段；视图对匿名用户开放。

**数据流。** 来源：views.py:178 request.POST.get('name') → views.py:183-185 cursor.execute("insert into taskManager_file ('name','path','project_id') values ('%s','%s',%s)" % (name, upload_path, project_id))。入口 upload 视图无认证检查（views.py:170 起只有 method 判断），匿名可达。

**影响。** 攻击者可以篡改/破坏数据库数据，并通过 INSERT...SELECT 子查询把敏感列（如 auth_user 密码哈希）搬进 name/path 字段，再经 download 响应头或文件读取泄露，形成数据外带。

**修复。** 使用 ORM（File.objects.create(...)）或参数化查询（cursor.execute(sql, params)），不要用 % 把用户输入拼进 SQL 文本。

**复核员指出的最弱一环。** 最弱一环是危险点前的可达性：curs.execute 在 store_uploaded_file 之后，若 os.system 阶段抛异常或 form.is_valid() 拦截则到不了 SQL；另外 sqlite3 驱动 execute() 不允许多语句，注入是否只剩报错。核实结果：os.system 不检查返回值、不抛异常，即使 mv 失败也继续执行到 SQL；form.is_valid() 对 name 无内容校验；SQLite 单语句限制下仍可通过 VALUES 内子查询（如 ',(SELECT password FROM auth_user)--）保持单语句完成 INSERT...SELECT 外带，再由 download（views.py:206-217，无认证）经 Content-Disposition 的 file.name 或文件内容读出。search_code 确认全库仅此一处原生 SQL。

**判定历史。**

- 复核员同意：重读 views.py:170-217、forms.py:78-81。name 直接经 % 格式化进入 INSERT 语句，无参数化；入口 upload 匿名可达。证据准确，影响分析（子查询外带 + download 读出）与代码路径吻合。high 合理（未直接给 critical 是因为 sqlite 单语句限制提高了利用门槛，认可该定级）。（最弱一环：最弱一环是危险点前的可达性：curs.execute 在 store_uploaded_file 之后，若 os.system 阶段抛异常或 form.is_valid() 拦截则到不了 SQL；另外 sqlite3 驱动 execute() 不允许多语句，注入是否只剩报错。核实结果：os.system 不检查返回值、不抛异常，即使 mv 失败也继续执行到 SQL；form.is_valid() 对 name 无内容校验；SQLite 单语句限制下仍可通过 VALUES 内子查询（如 ',(SELECT password FROM auth_user)--）保持单语句完成 INSERT...SELECT 外带，再由 download（views.py:206-217，无认证）经 Content-Disposition 的 file.name 或文件内容读出。search_code 确认全库仅此一处原生 SQL。）

**证据。**

`taskManager/views.py:182-185`

```
            curs = connection.cursor()
            curs.execute(
                "insert into taskManager_file ('name','path','project_id') values ('%s','%s',%s)" %
                (name, upload_path, project_id))
```

<a id="finding-xss-001"></a>

### [HIGH] 任务标题/描述 |safe 渲染导致匿名可触发的存储型 XSS

- 编号：`XSS-001`
- 类别：`xss`
- CWE：`CWE-79`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

task_create/task_edit 无认证地把用户输入写入 Task.title/text，task_details.html 用 |safe 原样渲染，构成匿名可注入的存储型 XSS。

**触发条件。** 匿名 POST /taskManager/<project_id>/task_create/（或 task_edit）提交含 HTML/JS 的 task_title/text，随后任意用户浏览 /taskManager/<project_id>/<task_id>/。

**数据流。** 来源：POST 参数 text/task_title（views.py:246-247，task_create 无认证检查）→ 存入 Task 模型（views.py:254-261 task.save()）→ 危险点 task_details.html:12 {{task.title|safe}}、:48 {{task.text|safe}} 以 |safe 原样输出。入口：匿名（task_create/task_edit 均无 login_required）。

**影响。** 匿名攻击者创建/编辑含脚本的任务，任意登录用户打开任务详情页即执行攻击者脚本，可窃取会话（配合 SESSION_COOKIE_HTTPONLY=False 可直接拿 sessionid）、冒充用户操作。

**修复。** 去掉 |safe（默认自动转义即可）；如需富文本使用经过白名单过滤的渲染器；给 task_create/task_edit 加认证与归属校验。

**复核员指出的最弱一环。** 最弱一环是匿名 task_create 是否真能把载荷落库：views.py:262 的 task.users_assigned = [request.user] 对 AnonymousUser 可能抛异常，若先于写库失败则存储不成立。核实结果：task.save() 在 :261，先于 :262 的 M2M 赋值，即使 :262 因 AnonymousUser 报错，任务行已写入；task_details.html:12 与 :48 的 {{task.title|safe}}、{{task.text|safe}} 原样确认；task_details 视图（:593-625）对匿名也渲染该模板，受害者面广；task_edit 同样无认证可改已有任务。

**判定历史。**

- 复核员同意：重读 views.py:240-268、593-625 与 task_details.html:1-60。来源（POST text/task_title）→ 落库 → |safe 渲染链路完整，匿名可注入、登录用户浏览即触发，配合 SESSION_COOKIE_HTTPONLY=False 可窃取 sessionid。high 合理。（最弱一环：最弱一环是匿名 task_create 是否真能把载荷落库：views.py:262 的 task.users_assigned = [request.user] 对 AnonymousUser 可能抛异常，若先于写库失败则存储不成立。核实结果：task.save() 在 :261，先于 :262 的 M2M 赋值，即使 :262 因 AnonymousUser 报错，任务行已写入；task_details.html:12 与 :48 的 {{task.title|safe}}、{{task.text|safe}} 原样确认；task_details 视图（:593-625）对匿名也渲染该模板，受害者面广；task_edit 同样无认证可改已有任务。）

**证据。**

`taskManager/views.py:246-247`

```
        text = request.POST.get('text', False)
        task_title = request.POST.get('task_title', False)
```

`taskManager/views.py:254-261`

```
        task = Task(
            text=text,
            title=task_title,
            start_date=now,
            due_date=task_duedate,
            project=proj)

        task.save()
```

`taskManager/templates/taskManager/task_details.html:12-12`

```
                {{task.title|safe}}
```

`taskManager/templates/taskManager/task_details.html:48-48`

```
                                   {{task.text|safe}}
```

<a id="finding-xss-002"></a>

### [HIGH] username 经 |safe 渲染，配合未授权改名构成存储型 XSS

- 编号：`XSS-002`
- 类别：`xss`
- CWE：`CWE-79`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

profile_by_id 允许匿名改写任意用户 username（无校验），后端基础模板用 |safe 渲染 username，形成面向任意用户的存储型 XSS。

**触发条件。** 匿名 POST /taskManager/profile/<user_id> 把 username 设为含 <script> 的值；受害用户访问 /taskManager/profile_view/<user_id> 或其自身任意后端页面时执行。

**数据流。** 来源：POST 参数 username（views.py:718-719，profile_by_id 不经表单校验直接写 user.username 并 save，views.py:732）→ 危险点 base_backend.html:57-58 {{ user.username|safe }}，profile_view 视图把他人 User 对象以 'user' 传入上下文（views.py:491-508），故他人在浏览该用户资料页时也会渲染。入口：匿名（profile_by_id 无认证且 csrf_exempt）。

**影响。** 匿名攻击者可把任意用户的 username 改成含脚本的字符串；被改用户自己以及浏览其资料的任何人（backend 页面顶部都渲染 username）都会执行脚本，造成会话窃取与账户操控。

**修复。** 去掉 base_backend.html（以及 tutorials/base.html）中的 |safe；对 username 做服务端校验（复用 Django 的 username 验证器）；给 profile_by_id 加认证与所有者校验。

**复核员指出的最弱一环。** 最弱一环是“面向任意用户触发”：base_backend.html 渲染的 user 是否可能是被攻击者改名的目标用户而非访问者本人（否则只是 self-XSS）。核实结果：profile_view（views.py:491-508）把 URL 指定的 User 对象以 'user' 传入上下文渲染 profile_view.html（extends base_backend），任何人浏览受害者资料页都会渲染其恶意 username；受害者本人访问任意后端页面时顶栏（base_backend.html:58）也渲染自身 username；username 写入点 profile_by_id（:718-719）无认证、不经表单校验（ProfileForm 不含 username 字段）。

**判定历史。**

- 复核员同意：重读 views.py:710-735、491-508，base_backend.html:40-70，并搜索确认 tutorials/base.html:54 同型。匿名改名 → 存储 → |safe 渲染链路完整，非 self-XSS。high 合理。（最弱一环：最弱一环是“面向任意用户触发”：base_backend.html 渲染的 user 是否可能是被攻击者改名的目标用户而非访问者本人（否则只是 self-XSS）。核实结果：profile_view（views.py:491-508）把 URL 指定的 User 对象以 'user' 传入上下文渲染 profile_view.html（extends base_backend），任何人浏览受害者资料页都会渲染其恶意 username；受害者本人访问任意后端页面时顶栏（base_backend.html:58）也渲染自身 username；username 写入点 profile_by_id（:718-719）无认证、不经表单校验（ProfileForm 不含 username 字段）。）

**证据。**

`taskManager/views.py:718-719`

```
            if request.POST.get('username') != user.username:
                user.username = request.POST.get('username')
```

`taskManager/templates/taskManager/base_backend.html:57-58`

```
                        <!--A3: Cross Site Scripting (XSS) -->
                        <span class="username"><i class="fa fa-user fa-fw"></i> {{ user.username|safe }}</span>
```

`taskManager/views.py:491-493`

```
def profile_view(request, user_id):
    try:
        user = User.objects.get(pk=user_id)
```

<a id="finding-config-001"></a>

### [MEDIUM] DEBUG/TEMPLATE_DEBUG 开启且 ALLOWED_HOSTS 为空，错误页泄露配置与堆栈

- 编号：`CONFIG-001`
- 类别：`config`
- CWE：`CWE-215`
- 入口身份：无请求入口
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

settings.py 固定开启 DEBUG/TEMPLATE_DEBUG 且 ALLOWED_HOSTS 为空，生产部署会通过错误页泄露堆栈、局部变量与配置机密。

**触发条件。** 该配置随 settings.py 直接生效；攻击者触发任意未捕获异常（如 task_create 的 int('') 转换）即可看到调试页。

**影响。** 生产环境开启 DEBUG 会在出错时输出完整堆栈、局部变量与 settings（含 SECRET_KEY、数据库路径），帮助攻击者收集情报并放大其他漏洞；DEBUG 模式下 ALLOWED_HOSTS 形同虚设，且多处视图的异常（如 int() 转换失败）会直接泄露回溯。

**修复。** 生产环境设置 DEBUG=False、TEMPLATE_DEBUG=False，并配置正确的 ALLOWED_HOSTS；用自定义错误页替代调试页。

**复核员指出的最弱一环。** 最弱一环是“生产泄露”是否只是假设性前提（配置是否真的会随部署生效）。核实结果：settings.py:28-31 DEBUG=True、TEMPLATE_DEBUG=True、ALLOWED_HOSTS=[] 硬编码生效，无环境变量分支；代码中存在多处未捕获异常路径可触发调试页，如 task_create（views.py:251-252 int('') 之外非法时间戳）、project_create（:328 int(None)）等，Django 1.7 DEBUG 错误页输出堆栈、局部变量与 settings 摘要。

**判定历史。**

- 复核员同意：重读 settings.py:26-31 及多个易抛异常视图。DEBUG 开启属于配置即生效的暴露面，且本仓库中多个视图缺异常处理使触发路径现实存在。medium 合理。（最弱一环：最弱一环是“生产泄露”是否只是假设性前提（配置是否真的会随部署生效）。核实结果：settings.py:28-31 DEBUG=True、TEMPLATE_DEBUG=True、ALLOWED_HOSTS=[] 硬编码生效，无环境变量分支；代码中存在多处未捕获异常路径可触发调试页，如 task_create（views.py:251-252 int('') 之外非法时间戳）、project_create（:328 int(None)）等，Django 1.7 DEBUG 错误页输出堆栈、局部变量与 settings 摘要。）

**证据。**

`taskManager/settings.py:27-31`

```
# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True
TEMPLATE_DEBUG = True

ALLOWED_HOSTS = []
```

<a id="finding-crypto-001"></a>

### [MEDIUM] 使用 MD5PasswordHasher 存储口令哈希，且默认账号哈希随仓库公开

- 编号：`CRYPTO-001`
- 类别：`crypto`
- CWE：`CWE-916`
- 入口身份：无请求入口
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

项目把口令哈希算法强制替换为 MD5PasswordHasher（快速、可字典破解），而非 Django 默认的 PBKDF2；fixtures 里的默认账号也使用 MD5 哈希存储。

**触发条件。** settings.py:101 的 PASSWORD_HASHERS 全局生效，新注册与改密均以 MD5 存储；fixtures/users.json 以明文形式提供含 MD5 哈希的默认账号。

**影响。** 数据库泄露（如借由 SQL 注入/IDOR 读取）后，MD5 口令哈希可用常见字典/彩虹表秒级破解，导致大面积账户泄露；fixtures 中 admin/seth 等账号的哈希也随仓库公开。

**修复。** 移除 MD5PasswordHasher，使用默认的 PBKDF2 或升级到 Argon2/BCrypt；为既有账号做哈希升级迁移。

**复核员指出的最弱一环。** 最弱一环是 PASSWORD_HASHERS 配置是否真的全局生效（而非被覆盖）。核实结果：settings.py:101 直接赋值 MD5PasswordHasher 为唯一 hasher，find/search 未见其他文件覆盖该设置；fixtures/users.json:9、23、37 中 admin/seth/chris 的 password 均为 md5$ 前缀哈希，与发现描述一致；Django 1.7 下该设置对 set_password/create_user 全局生效。

**判定历史。**

- 复核员同意：重读 settings.py:100-101 与 fixtures/users.json:1-40。MD5 快速哈希 + 默认账号哈希随仓库公开属实，属被动型弱点（需先拿到库），medium 合理。（最弱一环：最弱一环是 PASSWORD_HASHERS 配置是否真的全局生效（而非被覆盖）。核实结果：settings.py:101 直接赋值 MD5PasswordHasher 为唯一 hasher，find/search 未见其他文件覆盖该设置；fixtures/users.json:9、23、37 中 admin/seth/chris 的 password 均为 md5$ 前缀哈希，与发现描述一致；Django 1.7 下该设置对 set_password/create_user 全局生效。）

**证据。**

`taskManager/settings.py:100-101`

```
# A6: Sensitive Data Exposure
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
```

<a id="finding-file-001"></a>

### [MEDIUM] 任意文件（含 HTML/JS）落盘 Web 可服务目录并可同源访问

- 编号：`FILE-001`
- 类别：`file_access`
- CWE：`CWE-434`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：未复核

上传功能无类型/扩展名校验，文件以用户指定的名字存入应用 static/taskManager/uploads 目录，该目录在 DEBUG=True + staticfiles 下以 /static/ 对外伺服，攻击者可上传 HTML/JS 获得同源存储型内容注入。

**触发条件。** 匿名 POST /taskManager/<project_id>/upload/ 上传内容为脚本、name 为 x.html 的文件，随后访问 /static/taskManager/uploads/x.html。

**数据流。** 来源：POST 参数 name 与上传文件（views.py:178-179，upload 无认证；表单仅 CharField(max_length=300)+FileField，forms.py:80-81，无扩展名/内容校验）→ misc.py:26-27 落盘目录为应用 static/taskManager/uploads（Web 可服务目录），misc.py:41 返回路径 /static/taskManager/uploads/<name> → 由于 staticfiles 已安装且 DEBUG=True（settings.py:41、28），该目录经 runserver/staticfiles 以 /static/ 原样伺服。入口：匿名。

**影响。** 匿名攻击者把任意内容（如含脚本的 .html/.svg，或钓鱼页面）上传到应用 static 目录并自定文件名，随后经同源 /static/taskManager/uploads/<name> URL 直接访问；在 DEBUG=True 的 runserver 部署（runapp.sh）下该目录由 staticfiles 按 mimetype 伺服，可构成同源存储型内容注入/XSS。

**修复。** 上传目录移出 Web 可服务路径；文件名由服务端生成；对扩展名做白名单并对内容做校验（如仅允许图片并验证魔数）；生产环境不要用 runserver/DEBUG 模式伺服 static。

**证据。**

`taskManager/misc.py:26-27`

```
    upload_dir_path = '%s/static/taskManager/uploads' % (
        os.path.dirname(os.path.realpath(__file__)))
```

`taskManager/misc.py:41-41`

```
    return '/static/taskManager/uploads/%s' % (title)
```

`taskManager/forms.py:78-81`

```
class ProjectFileForm(forms.Form):
    """ Used for uploading files attached to projects """
    name = forms.CharField(max_length=300)
    file = forms.FileField()
```

<a id="finding-redir-001"></a>

### [MEDIUM] logout 开放重定向（redirect 参数未校验）

- 编号：`REDIR-001`
- 类别：`redirect`
- CWE：`CWE-601`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

logout 视图把 GET 参数 redirect 直接传给 redirect()，没有任何校验，构成开放重定向。

**触发条件。** 访问 /taskManager/logout?redirect=https://<攻击者域名>/。

**数据流。** 来源：GET 参数 redirect（views.py:387 request.GET.get('redirect', '/taskManager/')）→ 危险点 redirect() 直接跳转到攻击者提供的完整 URL。入口：匿名，logout 无 CSRF/认证要求。

**影响。** 攻击者构造 /taskManager/logout?redirect=https://evil.example 链接诱导用户点击，用于钓鱼；若站点信任链上依赖来源页面，可放大后续攻击。

**修复。** 重定向目标只接受站内路径，或对目标做白名单/前缀校验（如必须以 '/' 开头且不含 '//'）。

**复核员指出的最弱一环。** 最弱一环是 Django redirect() 是否真的会跳到任意外部 URL（某些封装会限制为相对路径）。核实结果：views.py:385-387 直接把 request.GET.get('redirect', '/taskManager/') 传给 django.shortcuts.redirect，字符串原样作为 Location 头，不校验 scheme/host；logout_view 无认证无 CSRF 要求，匿名可构造 /taskManager/logout/?redirect=https://evil 链接。

**判定历史。**

- 复核员同意：重读 views.py:382-387 与路由 taskManager_urls.py:33。开放重定向事实成立；用于钓鱼需用户点击，medium 处于常见定级区间（low-medium）上沿，不算明显偏高，予以认可。（最弱一环：最弱一环是 Django redirect() 是否真的会跳到任意外部 URL（某些封装会限制为相对路径）。核实结果：views.py:385-387 直接把 request.GET.get('redirect', '/taskManager/') 传给 django.shortcuts.redirect，字符串原样作为 Location 头，不校验 scheme/host；logout_view 无认证无 CSRF 要求，匿名可构造 /taskManager/logout/?redirect=https://evil 链接。）

**证据。**

`taskManager/views.py:385-387`

```
def logout_view(request):
    logout(request)
    return redirect(request.GET.get('redirect', '/taskManager/'))
```

<a id="finding-xss-003"></a>

### [MEDIUM] 搜索参数 q |safe 渲染导致反射型 XSS

- 编号：`XSS-003`
- 类别：`xss`
- CWE：`CWE-79`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

search 页把用户查询参数 q 用 |safe 渲染进 href 属性，可闭合属性注入事件处理器/脚本，构成匿名可达的反射型 XSS。

**触发条件。** 访问 /taskManager/search/?q=<可闭合引号的 payload>，无需登录。

**数据流。** 来源：GET 参数 q（views.py:662 query = request.GET.get('q', '')，search 视图无认证检查）→ 危险点 search.html:14 href="/taskManager/search/?q={{q|safe}}" 用 |safe 原样输出到属性内。入口：匿名。

**影响。** 反射型 XSS：攻击者可构造带脚本的 q 链接，诱导登录用户点击后在站内执行脚本，窃取会话或冒用身份。

**修复。** 去掉 |safe，让 Django 自动转义输出。

**复核员指出的最弱一环。** 最弱一环是属性上下文：{{q|safe}} 出现在双引号 href 属性内，若无法闭合属性则只能污染 URL 而非执行脚本。核实结果：search.html:14 确认 q 在 href="..." 双引号属性内以 |safe 原样输出，q 含双引号即可闭合属性并注入事件处理器或新属性；search 视图（views.py:661-675）无认证，q 直接来自 GET；同页 :22 的 value="{{q}}" 走自动转义无问题，漏洞点确为 :14。

**判定历史。**

- 复核员同意：重读 views.py:661-675 与 search.html:1-30。反射型 XSS 成立，需诱导点击、匿名可达，medium 与实际影响相符。（最弱一环：最弱一环是属性上下文：{{q|safe}} 出现在双引号 href 属性内，若无法闭合属性则只能污染 URL 而非执行脚本。核实结果：search.html:14 确认 q 在 href="..." 双引号属性内以 |safe 原样输出，q 含双引号即可闭合属性并注入事件处理器或新属性；search 视图（views.py:661-675）无认证，q 直接来自 GET；同页 :22 的 value="{{q}}" 走自动转义无问题，漏洞点确为 :14。）

**证据。**

`taskManager/views.py:661-662`

```
def search(request):
    query = request.GET.get('q', '')
```

`taskManager/templates/taskManager/search.html:14-14`

```
                    <a href="/taskManager/search/?q={{q|safe}}" id="loading-btn" class="btn btn-warning btn-xs"><i class="fa fa-refresh"></i> Refresh</a>
```

<a id="finding-xss-004"></a>

### [MEDIUM] settings 视图用 |safe 渲染 request.META：信息泄露 + 请求头反射 XSS

- 编号：`XSS-004`
- 类别：`xss`
- CWE：`CWE-79`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：未复核

tm_settings 视图未加认证地把 request.META（含 HTTP 头与服务器环境变量）渲染给模板，且模板用 |safe 输出：匿名可读取服务器环境信息，并存在请求头反射型 XSS。

**触发条件。** 匿名访问 /taskManager/settings/ 直接读取环境信息；携带含 HTML/JS 的 User-Agent 等请求头可在自身会话触发脚本。

**数据流。** 来源：HTTP 请求头（request.META 含 HTTP_USER_AGENT 等攻击者可控值），views.py:837-841 tm_settings 直接把 request.META 传给模板（无认证检查）→ 危险点 settings.html:28 {{v|safe}} 原样输出所有值。入口：匿名。

**影响。** 主影响是信息泄露：任何匿名访问者都能读取 request.META 全量内容（WSGI 环境变量、服务器路径、软件版本等），用于后续攻击情报收集；同时 {{v|safe}} 使攻击者可控的请求头原样输出，存在以自触发为主的反射型 XSS（受禁请求头无法让受害者跨站携带，XSS 部分接近 self-XSS）。

**修复。** 删除该调试视图（或加认证与敏感字段过滤），模板去掉 |safe。

**判定历史。**

- 复核员同意：重读 views.py:837-841、settings.html:1-40。漏洞事实成立；XSS 影响弱于描述（近 self-XSS），但匿名可访问的调试信息泄露足以支撑 medium，且与 CONFIG-001 不重复（那是错误页泄露，这是专用调试端点）。维持 medium 可接受。（最弱一环：最弱一环是 XSS 的可利用性：User-Agent 等是受禁请求头，攻击者无法让受害者浏览器跨站携带恶意头，脚本基本只在攻击者自己浏览器里执行（近 self-XSS）。核实结果：tm_settings（views.py:837-841）确无认证、把 request.META 全量交模板，settings.html:28 {{v|safe}} 原样输出；XSS 部分确以自触发为主，但该页同时把 WSGI/META 环境信息（服务器路径、软件版本、部分环境变量）展示给任意匿名访问者，信息泄露维度独立成立。）

**证据。**

`taskManager/views.py:837-841`

```
def tm_settings(request):
    settings_list = request.META
    return render(request,
                  'taskManager/settings.html',
                  {'settings': settings_list})
```

`taskManager/templates/taskManager/settings.html:27-28`

```
                          <td>
                              {{v|safe}}
```

<a id="finding-auth-002"></a>

### [LOW] 登录接口无速率限制/锁定，可无限在线爆破口令

- 编号：`AUTH-002`
- 类别：`auth`
- CWE：`CWE-307`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：未复核

login 视图没有任何速率限制、失败锁定或验证码，允许对账号进行无限制在线口令爆破；与用户名枚举、MD5 口令哈希构成完整攻击链。

**触发条件。** 匿名对 /taskManager/login/ 反复 POST 尝试不同口令，服务端无节流或告警。

**数据流。** 来源：POST 参数 username/password（views.py:392-393）→ views.py:395-409 直接做存在性判断与 authenticate，无任何尝试计数、锁定、退避或验证码；结合 INFO-001（用户名枚举）与 CRYPTO-001（MD5 快速哈希）可对已确认账号做在线字典爆破。入口：匿名。

**影响。** 登录接口可被无限次尝试：攻击者先借 INFO-001 枚举存在的用户名，再对目标账号做在线口令爆破（口令为 CRYPTO-001 的快速 MD5 哈希，弱口令极易命中），且无任何审计/告警，最终接管账号。

**修复。** 为登录（以及 forgot_password/reset_password）增加速率限制与失败退避/锁定（如 django-axes），部署验证码，并记录审计日志。

**证据。**

`taskManager/views.py:390-401`

```
def login(request):
    if request.method == 'POST':
        username = request.POST.get('username', False)
        password = request.POST.get('password', False)

        if User.objects.filter(username=username).exists():
            user = authenticate(username=username, password=password)
            if user is not None:
                if user.is_active:
                    auth_login(request, user)
                    # Redirect to a success page.
                    return redirect('/taskManager/')
```

<a id="finding-csrf-001"></a>

### [LOW] 多个口令相关端点被 csrf_exempt 豁免 CSRF 防护

- 编号：`CSRF-001`
- 类别：`csrf`
- CWE：`CWE-352`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

forgot_password 与 change_password 被 csrf_exempt 豁免 CSRF 校验（profile_by_id、reset_password 同被豁免，见相应 finding），允许跨站触发口令相关操作。

**触发条件。** 攻击者页面提交跨站表单到 /taskManager/forgot_password/ 或 /taskManager/change_password/ 即会以受害者会话执行。

**影响。** 攻击者页面可代受害者触发 forgot_password（对任意邮箱发送重置邮件，造成骚扰或作为暴力枚举重置令牌的前置步骤）；change_password 同样可被跨站触发（虽需旧口令，仍属不必要的暴露）。profile_by_id、reset_password 的 csrf_exempt 分别见 AUTHZ-001、AUTH-001。

**修复。** 移除敏感端点上的 @csrf_exempt（forgot_password、change_password、reset_password、profile_by_id），恢复全局 CsrfViewMiddleware 保护。

**复核员指出的最弱一环。** 最弱一环是 change_password 的实际影响：需受害者提交正确旧口令，跨站表单无法得知旧口令，攻击面是否被夸大。核实结果：@csrf_exempt 标注（views.py:779、813）逐行确认；finding 本身已如实说明 change_password 需旧口令、影响有限，影响面主要落在 forgot_password 可跨站触发重置邮件（并可反复刷新 reset_token，作为 AUTH-001 爆破的前置）；profile_by_id、reset_password 的豁免归属对应 finding，未重复计分。

**判定历史。**

- 复核员同意：重读 views.py:779-834。事实准确、影响描述克制（未夸大为改密劫持），low 定级与实际暴露相符。（最弱一环：最弱一环是 change_password 的实际影响：需受害者提交正确旧口令，跨站表单无法得知旧口令，攻击面是否被夸大。核实结果：@csrf_exempt 标注（views.py:779、813）逐行确认；finding 本身已如实说明 change_password 需旧口令、影响有限，影响面主要落在 forgot_password 可跨站触发重置邮件（并可反复刷新 reset_token，作为 AUTH-001 爆破的前置）；profile_by_id、reset_password 的豁免归属对应 finding，未重复计分。）

**证据。**

`taskManager/views.py:779-780`

```
@csrf_exempt
def forgot_password(request):
```

`taskManager/views.py:813-814`

```
@csrf_exempt
def change_password(request):
```

<a id="finding-info-001"></a>

### [LOW] 登录接口用户名枚举（错误文案可区分账号是否存在）

- 编号：`INFO-001`
- 类别：`sensitive_data`
- CWE：`CWE-203`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

登录接口对“用户名不存在”和“口令错误”显示不同错误信息，可枚举已注册用户名。

**触发条件。** 匿名 POST /taskManager/login/ 提交不同 username，观察返回文案区分账号存在性。

**数据流。** 来源：POST 参数 username（views.py:392）→ views.py:395 User.objects.filter(username=username).exists() 分支 → 响应分别渲染 'invalid_username'（views.py:410-413）与 'failed_login'（views.py:407-409），login.html:6-15 对两种情况显示不同文案。入口：匿名。

**影响。** 攻击者可通过登录接口探测哪些用户名存在，缩小后续口令爆破/钓鱼目标范围。

**修复。** 对“用户名不存在”与“口令错误”返回相同的提示文案，或统一为“用户名或口令错误”。

**复核员指出的最弱一环。** 最弱一环是两个分支的响应是否真可区分（若模板对两种上下文渲染相同文案则枚举不成立）。核实结果：login 视图（views.py:395-413）对“用户存在但口令错”渲染 {'failed_login': False}，对“用户不存在”渲染 {'invalid_username': False}；login.html:6-15 对两者输出不同标题（"Login failed" vs "Invalid Username"），匿名可稳定区分。

**判定历史。**

- 复核员同意：重读 views.py:390-418 与 login.html:1-25。用户名枚举属实，影响仅为侦察辅助，low 准确。另外注意到 forgot_password 两个分支文案相同（:804 与 :807），auditor 未对其过度断言，处理得当。（最弱一环：最弱一环是两个分支的响应是否真可区分（若模板对两种上下文渲染相同文案则枚举不成立）。核实结果：login 视图（views.py:395-413）对“用户存在但口令错”渲染 {'failed_login': False}，对“用户不存在”渲染 {'invalid_username': False}；login.html:6-15 对两者输出不同标题（"Login failed" vs "Invalid Username"），匿名可稳定区分。）

**证据。**

`taskManager/views.py:391-395`

```
    if request.method == 'POST':
        username = request.POST.get('username', False)
        password = request.POST.get('password', False)

        if User.objects.filter(username=username).exists():
```

`taskManager/templates/taskManager/login.html:6-15`

```
        {% if failed_login == False %}

        <h3>Login failed. Please try again</h3>

        {% endif %}
        {% if invalid_username == False %}

        <h3>Invalid Username. Please try again</h3>

        {% endif %}
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

覆盖了 settings.py（版本/中间件/会话/哈希/DEBUG/静态目录）、根路由与 taskManager_urls.py 全部 URL 映射、views.py 全部 841 行（全部视图逐一手工核对）、misc.py、forms.py、models.py、fixtures 默认账号、以及全部主要模板（base、base_backend、login、register、upload、search、settings、task_details、profile、profile_view、dashboard、manage_groups、messages、tutorials 等）。pattern_scan 的 15 条线索已全部 triage（11 条挂到 finding，4 条教程页文档类 benign）；复核员提出的 3 个 gap（注册 mass assignment 提权、上传文件落 Web 可服务目录、登录无爆破防护）已全部核实并补写为 AUTHZ-004、FILE-001、AUTH-002 后关闭。未深挖 migrations 与 Django 自带 admin 配置（未发现自定义覆盖）。

## 局限

本审计为纯静态代码审查：未实际运行应用，未验证 sqlite 单语句执行下的注入效果细节，也未做密码重置令牌空间精确枚举或在线爆破实测（AUTH-001 的利用现实性依赖窗口内请求量，confidence 已标 medium）；fixtures 默认口令哈希强度未经破解验证；未审计第三方依赖树（仅确认 requirements.txt 固定 Django==1.8.3，其自身含大量历史 CVE）；FILE-001 的同源伺服行为依赖 DEBUG=True 的 runserver 部署方式（runapp.sh 确如此运行）。

## 复核意见

逐条重读了所有证据位置及上下文：misc.py 全文、settings.py 全文、views.py 全部相关视图（upload/download/task_*/note_*/project_*/profile_by_id/reset_password/forgot_password/change_password/tm_settings/login/logout_view/manage_groups/register/search）、forms.py 全文、taskManager_urls.py 路由、task_details.html/base_backend.html/search.html/settings.html/login.html 模板、fixtures/users.json。16 条 confirmed 全部 agree：来源、可达性、entry_role、中间校验缺失、配置生效性均与代码吻合；仅描述性瑕疵两处已记录（DESER-001 的验签/反序列化先后顺序表述、AUTHZ-002 remediation 关于白名单的措辞），不影响结论与定级。抽查 leads 中 L11-L15 的 benign 判断属实（tutorials/partials/*.html 为 HTML 实体转义后的教学文字，非模板表达式）。已记录 3 条缺口：G1 register 质量赋值（UserForm 未排除 is_superuser/is_staff，匿名可注册超级用户，属高风险遗漏）、G2 上传文件无类型校验且落入 Web 可服务的 static 目录（同源存储型内容注入）、G3 登录无速率限制可在线爆破。仍存疑但不足以推翻的点：XSS-004 的 XSS 部分接近 self-XSS（靠信息泄露维度支撑 medium）；AUTH-001 的现实利用受 10 分钟窗口与请求量制约（auditor 已用 confidence=medium 校准）；REDIR-001 的 medium 处于常见区间上沿。

## 复核缺口

- `G1`（已回应）遗漏高风险：register 存在质量赋值提权。forms.py:71-76 的 UserForm（ModelForm on User）exclude 仅排除 ['groups','user_permissions','last_login','date_joined','is_active']，未排除 is_superuser 和 is_staff，二者仍是表单字段；views.py:421-445 register 视图对匿名开放且直接 user_form.save()，POST 中夹带 is_superuser=on 即可自助注册超级用户，无需经过 manage_groups。与 AUTHZ-002 是不同入口，应单列。
  - 审计员回应：已重新 read_file forms.py:71-81 与 views.py:421-463 并 search_code 确认：UserForm.exclude 不含 is_superuser/is_staff，register 视图（views.py:429-434）匿名可 user_form.save()。新增 AUTHZ-004（critical，mass assignment 自助注册超级用户）。
- `G2`（已回应）遗漏中风险：上传文件无类型/内容校验且落在 Web 可服务的 static 目录。misc.py:26-27 上传目录为 taskManager/static/taskManager/uploads（app 的 static 目录，staticfiles 已安装、DEBUG=True 下直接以 /static/ 伺服）；upload 视图的 name 仅经 CharField(max_length=300) 校验，攻击者可指定任意扩展名（如 x.html），上传 HTML/JS 后通过同源 /static/ URL 直接访问，构成存储型内容注入/XSS。这是与 RCE-001（shell 注入）不同的后果维度，未单列。
  - 审计员回应：已重新 read_file misc.py:24-41 与 settings.py:84-110 并 search_code 确认：上传落盘于应用 static/taskManager/uploads 且返回 /static/... URL，无扩展名校验，DEBUG=True 下由 staticfiles/runserver 伺服。新增 FILE-001（medium，任意文件上传至 Web 可服务目录）。
- `G3`（已回应）遗漏低-中风险：login 视图（views.py:390-418）无速率限制、无锁定/验证码，可无限在线爆破口令；与 INFO-001 的用户名枚举、CRYPTO-001 的 MD5 哈希形成完整攻击链，但现有发现均未提及在线爆破这一面。
  - 审计员回应：已重新 read_file views.py:390-409 并 search_code 确认：login 直接 authenticate，全库无 django-axes/ratelimit/锁定逻辑。新增 AUTH-002（low，登录接口无爆破防护）。

## 运行警告

- run interrupted: Error code: 429 - {'error': {'message': 'Your credit balance is running low for account <org-<redacted>>, please recharge immediately to avoid service disruption', 'type': 'exceeded_current_quota_error'}}
