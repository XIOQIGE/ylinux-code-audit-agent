# django.nV 应用安全审计报告

- 目标：`https://github.com/nVisium/django.nV`，commit `a48901f106da4888417339b7b44b8ed56b64c63f`
- 模型：审计员 `deepseek-v4-pro`，复核员 `deepseek-v4-pro`
- 时间：2026-10-21T09:28:29+08:00 → 2026-10-21T09:43:30+08:00
- 结论：确认 22 个问题，最高严重性为 critical。
- 统计：已确认 22，待再确认 0，已排除 0；引用核对 41 条，未通过 0 条

## 发现总表

| 严重性 | 编号 | 问题 | 入口身份 | 状态 | 复核员 | 位置 |
| --- | --- | --- | --- | --- | --- | --- |
| critical | [`AUTH-001`](#finding-auth-001) | 注册表单批量赋值：POST 附加 is_superuser/is_staff 即可匿名创建超级用户 | 匿名 | confirmed | 同意 | `taskManager/forms.py:71` |
| critical | [`AUTH-002`](#finding-auth-002) | profile_by_id 无鉴权 IDOR + csrf_exempt：匿名改任意用户密码实现账户接管 | 匿名 | confirmed | 同意 | `taskManager/views.py:710` |
| critical | [`CMDI-001`](#finding-cmdi-001) | 上传文件名进入 os.system 拼接，导致未认证命令注入（RCE） | 匿名 | confirmed | 同意 | `taskManager/views.py:177` |
| critical | [`SESSION-001`](#finding-session-001) | 签名 Cookie 会话 + PickleSerializer + 仓库内硬编码 SECRET_KEY 可伪造会话并反序列化 RCE | 匿名 | confirmed | 同意 | `taskManager/settings.py:23` |
| critical | [`SQLI-001`](#finding-sqli-001) | upload 视图用 % 格式化拼接 INSERT 语句，未认证 SQL 注入 | 匿名 | confirmed | 同意 | `taskManager/views.py:181` |
| high | [`ACCESS-002`](#finding-access-002) | 项目/任务/笔记的编辑与删除端点无鉴权、无归属校验（匿名 IDOR 写操作） | 匿名 | confirmed | 同意 | `taskManager/views.py:299` |
| high | [`CONFIG-002`](#finding-config-002) | SECRET_KEY 硬编码在仓库中（配置类，独立于会话反序列化记录） | 无请求入口 | confirmed | 同意 | `taskManager/settings.py:23` |
| high | [`FILE-001`](#finding-file-001) | download 视图无鉴权且路径取自数据库，可任意文件读取（路径穿越） | 匿名 | confirmed | 同意 | `taskManager/views.py:206` |
| high | [`RESET-001`](#finding-reset-001) | 密码重置令牌只有 6 位数字且无速率限制，可暴力枚举接管账户 | 匿名 | confirmed | 同意 | `taskManager/views.py:788` |
| high | [`XSS-003`](#finding-xss-003) | task_details 页面 task.title/task.text 经 \|safe 渲染，存储型 XSS | 匿名 | confirmed | 同意 | `taskManager/views.py:246` |
| medium | [`ACCESS-001`](#finding-access-001) | manage_groups POST 分支缺少权限检查：普通用户可提升任意用户到管理员组 | 可自助注册的用户 | confirmed | 同意 | `taskManager/views.py:116` |
| medium | [`ACCESS-003`](#finding-access-003) | task_details/profile_view 读侧 IDOR：匿名读取任意任务与用户资料 | 匿名 | confirmed | 同意 | `taskManager/views.py:593` |
| medium | [`CONFIG-001`](#finding-config-001) | DEBUG/TEMPLATE_DEBUG 开启并提交进仓库，错误页泄露敏感信息 | 无请求入口 | confirmed | 同意 | `taskManager/settings.py:26` |
| medium | [`CRYPTO-001`](#finding-crypto-001) | 口令使用 MD5 哈希存储，内置超管口令可被快速离线破解 | 无请求入口 | confirmed | 同意 | `taskManager/settings.py:100` |
| medium | [`CSRF-001`](#finding-csrf-001) | profile_by_id 改密端点豁免 CSRF，可被跨站请求改密 | 可自助注册的用户 | confirmed | 同意 | `taskManager/views.py:710` |
| medium | [`FILE-002`](#finding-file-002) | 上传文件名无校验且可路径穿越写入静态目录 | 匿名 | confirmed | 同意 | `taskManager/misc.py:24` |
| medium | [`REDIRECT-001`](#finding-redirect-001) | logout 端点开放重定向 | 匿名 | confirmed | 同意 | `taskManager/views.py:385` |
| medium | [`XSS-001`](#finding-xss-001) | search 页面 {{q\|safe}} 反射型 XSS | 匿名 | confirmed | 同意 | `taskManager/views.py:661` |
| medium | [`XSS-002`](#finding-xss-002) | tm_settings 页面 {{v\|safe}} 渲染 request.META：请求头反射 XSS 与环境信息泄露 | 匿名 | confirmed | 同意 | `taskManager/views.py:837` |
| medium | [`XSS-004`](#finding-xss-004) | 用户名经 \|safe 渲染到全站导航栏，存储型 XSS | 可自助注册的用户 | confirmed | 同意 | `taskManager/templates/taskManager/base_backend.html:57` |
| low | [`CONFIG-003`](#finding-config-003) | 会话 Cookie 未设 HttpOnly，XSS 可直接窃取会话 | 无请求入口 | confirmed | 同意 | `taskManager/settings.py:108` |
| info | [`COMP-001`](#finding-comp-001) | 使用已停止维护的 Django 1.8.3，存在已知未修复漏洞 | 无请求入口 | confirmed | 同意 | `requirements.txt:1` |

下面的发现由 Agent 写入，每条引用都回到源码核对过。审计员综述写在复核之前，单条发现的状态以复核后为准。线索处置、读过的文件、阶段记录、工具序列和引用核对见 `appendix.md`，关键决策见 `decisions.md`。

## 审计员综述

django.nV 是一个刻意构造的不安全 Django 1.8.3 应用（README 要求 Python 3.4+），本次审计确认了大量高危应用安全问题。最严重的是多条匿名可达的远程代码执行链路：上传端点把用户文件名拼进 os.system（命令注入）与原生 SQL INSERT（SQL 注入）；会话使用 signed_cookies + PickleSerializer，且 SECRET_KEY 硬编码在公开仓库中，可伪造会话 Cookie 触发 pickle 反序列化 RCE。认证与授权层面几乎失守：注册表单可批量赋值 is_superuser/is_staff 匿名创建超级用户；profile_by_id 无鉴权且 csrf_exempt，匿名即可改任意用户密码；密码重置令牌只有 6 位数字且无速率限制可被暴力枚举；项目/任务/笔记的编辑、删除、查看端点均无登录与归属校验（写侧与读侧 IDOR）；manage_groups 的 POST 分支缺少权限检查可提升任意用户到管理员组。模板多处 |safe 输出形成反射型与存储型 XSS，配合 SESSION_COOKIE_HTTPONLY=False 可窃取会话。配置方面 DEBUG=True、MD5 口令哈希、开放重定向、上传文件无校验等问题进一步放大风险。仓库代码明确标注为教学用途，绝不应以当前形态部署。

## 风险概览

最高风险：1) 匿名 RCE 三链路（CMDI-001 命令注入、SESSION-001 pickle 会话伪造、SQLI-001 原生 SQL 注入，后者配合 download 实现任意文件读取）；2) 匿名账户接管多条路径（AUTH-001 超级用户注册、AUTH-002 profile_by_id 改密、RESET-001 令牌暴力枚举、ACCESS-002 匿名增删改任意业务对象）；3) 多处 XSS（含匿名可注入的存储型 XSS）配合 HttpOnly=False 的会话 Cookie 形成会话劫持；4) 读侧 IDOR（ACCESS-003）泄露任意任务与用户资料；5) 弱口令哈希（MD5）使内置 admin/seth 等超管口令可被离线破解；6) DEBUG、硬编码 SECRET_KEY、开放重定向、无校验文件上传等配置与实现问题。多数问题无需任何账号即可触发，且相互叠加放大。

## 已确认的问题

<a id="finding-auth-001"></a>

### [CRITICAL] 注册表单批量赋值：POST 附加 is_superuser/is_staff 即可匿名创建超级用户

- 编号：`AUTH-001`
- 类别：`access_control`
- CWE：`CWE-915`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

UserForm 未排除 is_superuser/is_staff，模板没渲染这些字段但攻击者可直接 POST，ModelForm.save() 会按提交值创建超级用户，构成批量赋值特权提升。

**触发条件。** POST /taskManager/register/ 附带 username/password 以及 is_superuser=on、is_staff=on。

**数据流。** 公开注册端点 POST 数据（可附加 is_superuser/is_staff 字段）→ UserForm 为 ModelForm 且 exclude 仅排除了 groups/user_permissions/last_login/date_joined/is_active（taskManager/forms.py:71-75），is_superuser、is_staff 仍为表单字段 → user_form.save() 将提交值写入用户记录（taskManager/views.py:429-434）。入口身份：anonymous（/taskManager/register/ 公开且无需激活）。

**影响。** 匿名攻击者注册即得 is_superuser/is_staff 账号，直接登录 /admin/ 并完全控制应用与数据。

**修复。** UserForm 显式 fields = ['username','email','first_name','last_name','password']（白名单），或排除 is_superuser/is_staff/is_active 等特权字段；注册后按最低权限建用户，特权字段只允许管理员在 admin 中修改。

**复核员指出的最弱一环。** 最需核实的是 ModelForm 是否真的把 is_superuser/is_staff 纳入字段并落库。重读 forms.py:71-75：exclude 仅列 groups/user_permissions/last_login/date_joined/is_active，is_superuser、is_staff 未被排除、必被 ModelForm 自动生成；register（views.py:429-434）user_form.save() 后 445 行 user.save() 持久化，POST 附带的值生效。

**判定历史。**

- 复核员同意：核实 forms.py:71-75（exclude 未列 is_superuser/is_staff，ModelForm 自动纳入这两个可编辑字段）与 views.py:421-445（user_form.save() 落库、436 行 set_password 修正哈希、445 行 save 持久化）。注册端点公开（urls.py:31），is_active 被排除故默认 True，匿名 POST 附 is_superuser=on&is_staff=on 即创建超级用户，critical 合理。（最弱一环：最需核实的是 ModelForm 是否真的把 is_superuser/is_staff 纳入字段并落库。重读 forms.py:71-75：exclude 仅列 groups/user_permissions/last_login/date_joined/is_active，is_superuser、is_staff 未被排除、必被 ModelForm 自动生成；register（views.py:429-434）user_form.save() 后 445 行 user.save() 持久化，POST 附带的值生效。）

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

<a id="finding-auth-002"></a>

### [CRITICAL] profile_by_id 无鉴权 IDOR + csrf_exempt：匿名改任意用户密码实现账户接管

- 编号：`AUTH-002`
- 类别：`access_control`
- CWE：`CWE-639`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

profile_by_id 无登录与归属校验且 csrf_exempt，任何人对任意 user_id 提交 POST 即可直接设置该账号的新密码（及用户名），构成匿名账户接管。

**触发条件。** POST /taskManager/profile/<目标用户ID>，携带 password=<新密码>（profile.html 的表单就是提交到该 URL）。

**数据流。** URL 参数 user_id → User.objects.get(pk=user_id)（taskManager/views.py:712），视图无 is_authenticated、无“当前用户==目标用户”校验且 @csrf_exempt → POST 中 password 字段直接 user.set_password(...) 并 save（views.py:726-732）。入口身份：anonymous。

**影响。** 匿名攻击者把任意用户（含 fixture 中的 admin/seth 超级用户）的密码改掉并以其身份登录，实现任意账户接管。

**修复。** profile_by_id 只允许登录用户编辑自己（user_id 必须等于 request.user.id），移除 @csrf_exempt，密码修改走独立端点并要求旧密码/二次认证。

**复核员指出的最弱一环。** 最需核实的是该视图是否真的既无登录校验也无"只能改自己"校验、且 password 直接落库。views.py:710-732 实锤：@csrf_exempt、无 is_authenticated、User.objects.get(pk=user_id) 取任意用户、726-727 对 POST password 直接 set_password 并 save；form.is_valid() 门槛仅 ProfileForm（first_name/last_name/email/picture 全可选），匿名 POST 可通过。

**判定历史。**

- 复核员同意：核实 views.py:710-732 与 urls.py:43-44（profile/(user_id) 路由）。任意用户（含 fixture 超级用户 admin/seth）可被匿名改密接管，critical 合理。（最弱一环：最需核实的是该视图是否真的既无登录校验也无"只能改自己"校验、且 password 直接落库。views.py:710-732 实锤：@csrf_exempt、无 is_authenticated、User.objects.get(pk=user_id) 取任意用户、726-727 对 POST password 直接 set_password 并 save；form.is_valid() 门槛仅 ProfileForm（first_name/last_name/email/picture 全可选），匿名 POST 可通过。）

**证据。**

`taskManager/views.py:710-712`

```
@csrf_exempt
def profile_by_id(request, user_id):
    user = User.objects.get(pk=user_id)
```

`taskManager/views.py:718-727`

```
            if request.POST.get('username') != user.username:
                user.username = request.POST.get('username')
            if request.POST.get('first_name') != user.first_name:
                user.first_name = request.POST.get('first_name')
            if request.POST.get('last_name') != user.last_name:
                user.last_name = request.POST.get('last_name')
            if request.POST.get('email') != user.email:
                user.email = request.POST.get('email')
            if request.POST.get('password'):
                user.set_password(request.POST.get('password'))
```

<a id="finding-cmdi-001"></a>

### [CRITICAL] 上传文件名进入 os.system 拼接，导致未认证命令注入（RCE）

- 编号：`CMDI-001`
- 类别：`injection`
- CWE：`CWE-78`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

store_uploaded_file 把用户可控的 title 直接拼进 os.system 的 shell 命令行；upload 视图无任何登录校验，profile_by_id 又通过用户名到达同一 sink，攻击者可在服务器上执行任意命令。

**触发条件。** POST /taskManager/<project_id>/upload/ 的 name 参数（views.py:178）被原样用作 mv 目标文件名；profile_by_id 的 username 加扩展名同样到达该 sink（views.py:729-730）。

**数据流。** POST 参数 name（taskManager/views.py:178，upload 视图无登录/权限校验；CSRF token 可从 GET 表单页获取）→ store_uploaded_file(name, file)（views.py:179）→ title 直接拼接进 os.system("mv " + tmp + " " + dir + "/" + title)（taskManager/misc.py:33-39）。第二入口：profile_by_id 中 user.username + "." + 扩展名（views.py:729-730）作为 title 到达同一 sink，且该视图 @csrf_exempt。入口身份：anonymous。

**影响。** 匿名攻击者可在应用服务器上执行任意 shell 命令，彻底控制服务器、数据库与所有用户数据。

**修复。** 不要用 os.system 移动上传文件：改用 shutil.move/os.rename；文件名用随机生成值（如 uuid4），绝不拼接用户输入；给 upload 与 profile_by_id 加登录与归属校验；用 subprocess 列表参数并在任何情况下避免把用户输入送入 shell。

**复核员指出的最弱一环。** 最需要核实的是"匿名可达且 title 原样进入 os.system"。我重读了 views.py:170-201：upload 视图对 GET/POST 均无 is_authenticated 检查，GET 分支把带 {% csrf_token %} 的 upload.html（第 13 行）返回给匿名者，token 可取得；misc.py:33-39 把 title 无引号、无转义直接拼进 "mv ... dir/title"。第二条入口 profile_by_id（views.py:710-732，@csrf_exempt）在 728-730 用 POST 可控的 user.username + 扩展名调用同一函数，同样成立。

**判定历史。**

- 复核员同意：sink 为 os.system 字符串拼接（misc.py:33-39），title 在 upload 路径来自 POST name（views.py:178，仅过 ProjectFileForm 的 name/file 必填校验，无任何清洗），在 profile_by_id 路径来自 POST username（views.py:718-719 后立即在 728-730 使用），两入口均无登录校验且 CSRF token 可匿名获取（upload.html:13）。载荷带 ';' 或 '&&' 即可执行任意命令，不受 mv 目标是否合法影响。critical 合理。（最弱一环：最需要核实的是"匿名可达且 title 原样进入 os.system"。我重读了 views.py:170-201：upload 视图对 GET/POST 均无 is_authenticated 检查，GET 分支把带 {% csrf_token %} 的 upload.html（第 13 行）返回给匿名者，token 可取得；misc.py:33-39 把 title 无引号、无转义直接拼进 "mv ... dir/title"。第二条入口 profile_by_id（views.py:710-732，@csrf_exempt）在 728-730 用 POST 可控的 user.username + 扩展名调用同一函数，同样成立。）

**证据。**

`taskManager/views.py:177-179`

```
        if form.is_valid():
            name = request.POST.get('name', False)
            upload_path = store_uploaded_file(name, request.FILES['file'])
```

`taskManager/misc.py:31-41`

```
    # A1: Injection (shell)
    # Let's avoid the file corruption race condition!
    os.system(
        "mv " +
        uploaded_file.temporary_file_path() +
        " " +
        "%s/%s" %
        (upload_dir_path,
         title))

    return '/static/taskManager/uploads/%s' % (title)
```

<a id="finding-session-001"></a>

### [CRITICAL] 签名 Cookie 会话 + PickleSerializer + 仓库内硬编码 SECRET_KEY 可伪造会话并反序列化 RCE

- 编号：`SESSION-001`
- 类别：`deserialization`
- CWE：`CWE-502`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

会话后端为 signed_cookies，序列化器为 PickleSerializer，而 SECRET_KEY 明文写死在公开仓库的 settings.py 中。攻击者可用该密钥对恶意 pickle 负载签名生成会话 Cookie，服务器反序列化时执行任意代码。

**触发条件。** SECRET_KEY（settings.py:24）公开 → 攻击者自签含恶意对象的 sessionid Cookie → signed_cookies 后端用 PickleSerializer 反序列化。

**数据流。** 客户端提交的 sessionid Cookie → django.contrib.sessions.backends.signed_cookies 用 PickleSerializer（settings.py:104/109）对签名数据 pickle.loads 反序列化；签名密钥 SECRET_KEY 硬编码于公开仓库（settings.py:24）→ 攻击者自行签名恶意 pickle → 反序列化即代码执行。入口身份：anonymous（无需账号）。

**影响。** 攻击者可伪造任意用户（含管理员）的会话，或构造恶意 pickle 使服务器执行任意代码（RCE）。

**修复。** 会话改用服务端存储（如 django.contrib.sessions.backends.db/cache）并把 SESSION_SERIALIZER 换回 JSONSerializer；SECRET_KEY 改为环境变量注入且不在仓库出现，已有部署应轮换密钥。

**复核员指出的最弱一环。** 最需核实的是"已知 SECRET_KEY + signed_cookies + PickleSerializer ⇒ 攻击者自签 pickle 被执行"。settings.py:24 硬编码密钥、104 用 signed_cookies、109 用 PickleSerializer，三者同文件实锤；Django 1.8 的签名校验只验证 HMAC，验签后即 pickle.loads，攻击者持密钥可伪造任意会话并触发反序列化 RCE，链条成立。

**判定历史。**

- 复核员同意：重读 settings.py:23-24、103-109 确认三要素齐备，MIDDLEWARE_CLASSES 含 SessionMiddleware（settings.py:45）。这是 Django 已知组合缺陷（CWE-502），匿名可达、直接 RCE，critical 合理。（最弱一环：最需核实的是"已知 SECRET_KEY + signed_cookies + PickleSerializer ⇒ 攻击者自签 pickle 被执行"。settings.py:24 硬编码密钥、104 用 signed_cookies、109 用 PickleSerializer，三者同文件实锤；Django 1.8 的签名校验只验证 HMAC，验签后即 pickle.loads，攻击者持密钥可伪造任意会话并触发反序列化 RCE，链条成立。）

**证据。**

`taskManager/settings.py:23-24`

```
# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '0yxzudryd8)-%)(fz&7q-!v&cq1u6vbfoc4u7@u_&i)b@4eh^q'
```

`taskManager/settings.py:103-109`

```
# A2: Broken Auth and Session Management
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"

EMAIL_PORT = 1025

# Needs compatibility with older Django!
SESSION_SERIALIZER = "django.contrib.sessions.serializers.PickleSerializer"
```

<a id="finding-sqli-001"></a>

### [CRITICAL] upload 视图用 % 格式化拼接 INSERT 语句，未认证 SQL 注入

- 编号：`SQLI-001`
- 类别：`injection`
- CWE：`CWE-89`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

upload 视图把用户提交的 name 和由其派生的 upload_path 用 % 直接拼进 INSERT 语句后通过 cursor.execute 执行，且该视图无任何鉴权，攻击者可注入任意 SQL。

**触发条件。** POST /taskManager/<project_id>/upload/，name 与 upload_path 均含用户输入，被拼进 INSERT（views.py:183-185）。

**数据流。** POST 参数 name（taskManager/views.py:178，无登录校验）→ upload_path = '/static/taskManager/uploads/' + name（misc.py:41，由 store_uploaded_file 返回）→ "insert into taskManager_file ('name','path','project_id') values ('%s','%s',%s)" % (name, upload_path, project_id) 交由 connection.cursor().execute 执行（views.py:181-185）。入口身份：anonymous（CSRF token 可从 GET 表单页获得）。

**影响。** 匿名攻击者可注入任意 SQL：例如向 taskManager_file 表写入任意 path，配合无鉴权的 download 视图实现任意文件读取；或篡改、破坏数据库内容。

**修复。** 删除原生 SQL，改用 ORM（File.objects.create(name=..., path=..., project=proj)）；若必须用原生 SQL，用 execute(sql, params) 参数化占位符（%s 不带引号），禁止把用户输入用 % 格式化进语句；同时给视图加登录校验。

**复核员指出的最弱一环。** 最需核实的是 name/upload_path 是否真的未转义进入 SQL 语句。重读 views.py:181-185：INSERT 用 % 直接把 name 与 upload_path（misc.py:41 派生自 name）格式化进语句后交 connection.cursor().execute，值周围只有单引号、无任何转义或参数化；name 含单引号即可闭合字符串并注入，即使 sqlite3 单语句执行，也能改写 INSERT 的 values（如写任意 path），发现所述影响成立。

**判定历史。**

- 复核员同意：核实了 views.py:170-201（upload 无鉴权、name 来自 POST）、misc.py:41（upload_path 由 name 派生）、settings.py:66-68（SQLite 后端）。未发现任何转义/参数化。任意路径写入 + 无鉴权 download 的后果链与 FILE-001 交叉印证。critical 合理。（最弱一环：最需核实的是 name/upload_path 是否真的未转义进入 SQL 语句。重读 views.py:181-185：INSERT 用 % 直接把 name 与 upload_path（misc.py:41 派生自 name）格式化进语句后交 connection.cursor().execute，值周围只有单引号、无任何转义或参数化；name 含单引号即可闭合字符串并注入，即使 sqlite3 单语句执行，也能改写 INSERT 的 values（如写任意 path），发现所述影响成立。）

**证据。**

`taskManager/views.py:181-185`

```
            #A1 - Injection (SQLi)
            curs = connection.cursor()
            curs.execute(
                "insert into taskManager_file ('name','path','project_id') values ('%s','%s',%s)" %
                (name, upload_path, project_id))
```

<a id="finding-access-002"></a>

### [HIGH] 项目/任务/笔记的编辑与删除端点无鉴权、无归属校验（匿名 IDOR 写操作）

- 编号：`ACCESS-002`
- 类别：`access_control`
- CWE：`CWE-862`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

task_edit/task_delete/task_complete/project_edit/project_delete/note_edit/note_delete（以及 task_create/project_create/note_create）都没有登录与对象归属检查，匿名即可按 ID 修改或删除任意项目、任务、笔记。

**触发条件。** 例如 GET /taskManager/<project_id>/project_delete/ 或 POST /taskManager/<project_id>/task_edit/<task_id>（CSRF token 可从表单页 GET 取得）。

**数据流。** URL 中的 project_id/task_id/note_id → 直接 Project/Task/Notes.objects.get(pk=...) 后 save/delete，全程无 is_authenticated、无“对象归属当前用户”校验：task_delete（views.py:299-306）、project_delete（views.py:376-380，接受 GET）、task_edit（views.py:273-294）、task_complete（views.py:311-319）、note_edit（views.py:554-576）、note_delete（views.py:581-590）、project_edit（views.py:350-371）。入口身份：anonymous（删除类端点甚至可用 GET 触发，无需 CSRF token）。

**影响。** 匿名攻击者可枚举 ID 修改/删除任何用户的项目、任务与笔记（数据破坏、内容篡改，且可配合 XSS-003 注入存储型脚本）。

**修复。** 所有写操作视图要求登录（@login_required），校验对象归属（task.project.users_assigned / project.users_assigned 包含 request.user 或请求者有对应权限），删除操作限制为 POST 并保留 CSRF 保护。

**复核员指出的最弱一环。** 最需核实的是这些端点是否确实全部无鉴权、且删除端点可用 GET 触发。task_delete(299-306)、task_complete(311-319) 无任何 is_authenticated/归属检查；project_delete(376-380) 直接 delete 且可 GET 触发；task_edit(273-294)、project_edit(350-371)、note_edit(554-576)、note_delete(581-590) 同样只按 pk 取对象后写/删，唯一条件校验是 task.project==proj 这类对象关系，而非请求者身份。

**判定历史。**

- 复核员同意：重读 views.py:273-319、350-380、554-590 及 urls.py:63-84 路由。匿名可枚举 ID 篡改/删除任意项目、任务、笔记；删除类端点 GET 可达（无 CSRF 门槛）。high 合理。（最弱一环：最需核实的是这些端点是否确实全部无鉴权、且删除端点可用 GET 触发。task_delete(299-306)、task_complete(311-319) 无任何 is_authenticated/归属检查；project_delete(376-380) 直接 delete 且可 GET 触发；task_edit(273-294)、project_edit(350-371)、note_edit(554-576)、note_delete(581-590) 同样只按 pk 取对象后写/删，唯一条件校验是 task.project==proj 这类对象关系，而非请求者身份。）

**证据。**

`taskManager/views.py:299-306`

```
def task_delete(request, project_id, task_id):
    proj = Project.objects.get(pk=project_id)
    task = Task.objects.get(pk=task_id)
    if proj is not None:
        if task is not None and task.project == proj:
            task.delete()

    return redirect('/taskManager/' + project_id + '/')
```

`taskManager/views.py:376-380`

```
def project_delete(request, project_id):
    # IDOR
    project = Project.objects.get(pk=project_id)
    project.delete()
    return redirect('/taskManager/dashboard')
```

<a id="finding-config-002"></a>

### [HIGH] SECRET_KEY 硬编码在仓库中（配置类，独立于会话反序列化记录）

- 编号：`CONFIG-002`
- 类别：`config`
- CWE：`CWE-798`
- 入口身份：无请求入口
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

SECRET_KEY 明文硬编码并随仓库公开，等于把会话签名与框架全部签名能力的根密钥交给攻击者。

**触发条件。** 任何能看到仓库的人即获得 settings.py:24 中的密钥；该密钥用于 signed_cookies 会话签名（settings.py:104）。

**影响。** 密钥公开使攻击者能自签会话 Cookie（配合 PickleSerializer 实现 RCE，见 SESSION-001），并伪造 messages 等签名数据。

**修复。** SECRET_KEY 从环境变量/密钥管理读取，禁止写入版本库；已泄露的部署必须轮换密钥并使旧会话失效。

**复核员指出的最弱一环。** 最需核实的是该密钥是否真的被框架签名机制使用（否则只是摆设）。settings.py:24 硬编码 SECRET_KEY，settings.py:104 SESSION_ENGINE=signed_cookies 用该密钥对会话签名，同文件闭环；仓库内明文即对所有能看代码者公开。

**判定历史。**

- 复核员同意：核实 settings.py:23-24、103-104。CWE-798 成立，与 SESSION-001 同根因但作为配置问题独立记录可接受；high 合理（密钥公开直接等价于会话签名能力失控）。（最弱一环：最需核实的是该密钥是否真的被框架签名机制使用（否则只是摆设）。settings.py:24 硬编码 SECRET_KEY，settings.py:104 SESSION_ENGINE=signed_cookies 用该密钥对会话签名，同文件闭环；仓库内明文即对所有能看代码者公开。）

**证据。**

`taskManager/settings.py:23-24`

```
# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '0yxzudryd8)-%)(fz&7q-!v&cq1u6vbfoc4u7@u_&i)b@4eh^q'
```

<a id="finding-file-001"></a>

### [HIGH] download 视图无鉴权且路径取自数据库，可任意文件读取（路径穿越）

- 编号：`FILE-001`
- 类别：`file_access`
- CWE：`CWE-22`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

download 直接 open(模块目录 + File.path) 并回传内容，无登录与归属校验；File.path 在上传时由用户 title 拼接生成（可含 ../），更可通过 SQLI-001 直接注入任意路径，形成匿名任意文件读取。

**触发条件。** GET /taskManager/download/<file_id>/：File.path 的值可通过上传时 name 中的 ../ 段（misc.py:41）或 SQLI-001 注入任意路径。

**数据流。** 上传时用户 title → File.path（taskManager/misc.py:41，'/static/taskManager/uploads/%s' % title）→ download 视图无鉴权地 File.objects.get(pk=file_id) 并 open(os.path.dirname(os.path.realpath(__file__)) + file.path, 'rb') 回读（taskManager/views.py:206-217）；title 含 ../ 时穿越出 uploads 目录，或经 SQLI-001（views.py:183-185）直接写任意 path。入口身份：anonymous。

**影响。** 匿名攻击者可读取服务器任意可读文件（源代码、数据库文件 db.sqlite3、凭证、系统配置等）。

**修复。** download 要求登录并校验 File.project 与当前用户的归属；路径用白名单目录 + os.path.basename 校验，或改为把文件存成随机名并只允许解析 uploads 目录内的绝对路径（用 os.path.realpath 校验前缀）；杜绝 SQL 注入（见 SQLI-001）。

**复核员指出的最弱一环。** 最需核实的是 file.path 能否真的带出 uploads 目录。misc.py:41 返回 '/static/taskManager/uploads/%s' % title，title 含 ../ 时 open(模块目录 + file.path)（views.py:209-213）经路径归一化即可逃出；叠加 SQLI-001 还能直接写任意 path。download 视图 206-217 无 is_authenticated、无归属校验，直接回读。

**判定历史。**

- 复核员同意：核实 views.py:206-217（无鉴权、路径字符串拼接后 open 并回传）、misc.py:41（path 由用户 title 派生）、urls.py:23-24（download 路由）。读取方向任意文件读取成立，high 合理（上限受 OS 文件权限约束，未标 critical 恰当）。（最弱一环：最需核实的是 file.path 能否真的带出 uploads 目录。misc.py:41 返回 '/static/taskManager/uploads/%s' % title，title 含 ../ 时 open(模块目录 + file.path)（views.py:209-213）经路径归一化即可逃出；叠加 SQLI-001 还能直接写任意 path。download 视图 206-217 无 is_authenticated、无归属校验，直接回读。）

**证据。**

`taskManager/views.py:206-217`

```
def download(request, file_id):

    file = File.objects.get(pk=file_id)
    abspath = open(
        os.path.dirname(
            os.path.realpath(__file__)) +
        file.path,
        'rb')
    response = HttpResponse(content=abspath.read())
    response['Content-Type'] = mimetypes.guess_type(file.path)[0]
    response['Content-Disposition'] = 'attachment; filename=%s' % file.name
    return response
```

`taskManager/misc.py:41-41`

```
    return '/static/taskManager/uploads/%s' % (title)
```

<a id="finding-reset-001"></a>

### [HIGH] 密码重置令牌只有 6 位数字且无速率限制，可暴力枚举接管账户

- 编号：`RESET-001`
- 类别：`auth`
- CWE：`CWE-307`
- 入口身份：匿名
- 置信度：`medium`
- 状态：`confirmed`
- 复核员：同意

密码重置令牌是 6 位十进制数字（空间≤10^6）、有效期 10 分钟，reset_password 为匿名 + csrf_exempt 且无速率限制，攻击者可在窗口内暴力枚举令牌接管任意账户。

**触发条件。** 先 POST /taskManager/forgot_password/ 携带目标邮箱生成令牌（有效期 10 分钟），再向 /taskManager/reset_password/ 枚举 reset_token 与 new_password。

**数据流。** 目标邮箱 → POST /taskManager/forgot_password/（@csrf_exempt，views.py:779-780）→ 生成 6 位十进制数字令牌（os.urandom(6) 的每个字节经 str() 变十进制串后取前 6 字符，空间 ≤10^6，views.py:788-794）→ POST /taskManager/reset_password/（@csrf_exempt，无速率限制/失败锁定，views.py:739-744）按 reset_token 精确匹配后直接 set_password（views.py:766-770）。Python 3.4+（README.md:8、16）。入口身份：anonymous。

**影响。** 知道目标邮箱的攻击者可在令牌有效期（10 分钟）内枚举最多 10^6 个候选值（平均约 50 万次请求，端点无任何限速/锁定）改掉任意账户密码，实现账户接管。

**修复。** 用 secrets.token_urlsafe(32)（或至少 20 字节的 hex/urlsafe 令牌）生成不可预测令牌；对 reset_password 端点做速率限制与失败锁定；令牌比较用恒定时间比较；重置成功后使所有会话失效。

**复核员指出的最弱一环。** 最站不住的一环是"令牌空间≤10^6 且可在 10 分钟内无限制枚举"。我重读了 views.py:779-809：README.md:8/16 要求 Python 3.4+/python3，因此 os.urandom(6) 返回 bytes、迭代得 0-255 的整数、str(x) 为十进制串，res[:6] 恒为 6 位十进制数字，空间上界确为 10^6（实际分布还小于此，只对攻击者更有利）；有效期 10 分钟在 views.py:796 实锤。再看 views.py:739-775 的 reset_password：@csrf_exempt（739）、全程无 is_authenticated、按 reset_token 精确匹配后 766-770 直接 set_password，无任何速率限制、失败锁定或尝试次数记录；taskManager_urls.py:39-42 直接映射到视图、无装饰器。全空间 10 分钟需约 1.7k req/s、期望值减半，在无任何节流的本地/内网场景下可行。

**判定历史。**

- 复核员同意：核实了令牌生成（views.py:788-794，Python 3 下 bytes→int→str 的拼接确实产出 6 位十进制数字）、有效期（796，10 分钟）、校验端点（739-775，@csrf_exempt + 匿名 + 无节流 + 无锁定）、路由（taskManager_urls.py:39-42 无中间校验）。前提"知道目标邮箱"在发现中已明示，fixture 用户邮箱公开可得。无速率限制使 10^6 枚举在窗口内可行，账户接管成立，high 合理。（最弱一环：最站不住的一环是"令牌空间≤10^6 且可在 10 分钟内无限制枚举"。我重读了 views.py:779-809：README.md:8/16 要求 Python 3.4+/python3，因此 os.urandom(6) 返回 bytes、迭代得 0-255 的整数、str(x) 为十进制串，res[:6] 恒为 6 位十进制数字，空间上界确为 10^6（实际分布还小于此，只对攻击者更有利）；有效期 10 分钟在 views.py:796 实锤。再看 views.py:739-775 的 reset_password：@csrf_exempt（739）、全程无 is_authenticated、按 reset_token 精确匹配后 766-770 直接 set_password，无任何速率限制、失败锁定或尝试次数记录；taskManager_urls.py:39-42 直接映射到视图、无装饰器。全空间 10 分钟需约 1.7k req/s、期望值减半，在无任何节流的本地/内网场景下可行。）

**证据。**

`taskManager/views.py:788-794`

```
            # Generate secure random 6 digit number
            res = ""
            nums = [x for x in os.urandom(6)]
            for x in nums:
                res = res + str(x)

            reset_token = res[:6]
```

`taskManager/views.py:739-747`

```
@csrf_exempt
def reset_password(request):

    if request.method == 'POST':

        reset_token = request.POST.get('reset_token')

        try:
            userprofile = UserProfile.objects.get(reset_token = reset_token)
```

`README.md:8-8`

```
First, make sure Python 3.4+ is installed on your machine. On OSX, this can be installed with Homebrew (eg. `brew install python3`). If you receive an error about conflicting PYTHONPATH, try updating the variable to reflect your python version.
```

<a id="finding-xss-003"></a>

### [HIGH] task_details 页面 task.title/task.text 经 |safe 渲染，存储型 XSS

- 编号：`XSS-003`
- 类别：`xss`
- CWE：`CWE-79`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

任务标题与正文在详情页用 |safe 渲染，而创建/编辑端无鉴权，任何匿名者可注入并让其他用户触发存储型 XSS。

**触发条件。** POST /taskManager/<project_id>/task_create/ 提交含 <script> 的 task_title/text，受害者访问对应任务详情页。

**数据流。** POST 参数 text/task_title（taskManager/views.py:246-261，task_create 无鉴权；task_edit 同样无鉴权 views.py:282-289）→ Task.title/Task.text 落库 → task_details.html 以 {{task.title|safe}}、{{task.text|safe}} 渲染（templates/taskManager/task_details.html:12、48）。注入与查看均 anonymous 可达。

**影响。** 匿名攻击者写入的脚本会在管理员或任意用户打开任务详情页时执行，窃取会话、冒充管理员执行操作。

**修复。** 去掉 task_details.html 中两个 |safe；若确需富文本，使用经过白名单过滤的 HTML 清洗（如 bleach）；给 task_create/task_edit 加登录与归属校验。

**复核员指出的最弱一环。** 最需核实的是 |safe 确在渲染处、且写入端无鉴权。task_details.html 第 12 行 {{task.title|safe}}、第 48 行 {{task.text|safe}} 实锤；task_create（views.py:246-261）与 task_edit（282-289）均无登录检查，POST 值直存数据库。

**判定历史。**

- 复核员同意：核实 views.py:240-294（task_create/task_edit 均无 is_authenticated，text/task_title 直接落库）、task_details.html:11-12 与 47-48（两处 |safe）。匿名写入 + 无归属校验的详情页渲染，存储型 XSS 成立，high 合理。（最弱一环：最需核实的是 |safe 确在渲染处、且写入端无鉴权。task_details.html 第 12 行 {{task.title|safe}}、第 48 行 {{task.text|safe}} 实锤；task_create（views.py:246-261）与 task_edit（282-289）均无登录检查，POST 值直存数据库。）

**证据。**

`taskManager/views.py:246-261`

```
        text = request.POST.get('text', False)
        task_title = request.POST.get('task_title', False)
        now = timezone.now()
        task_duedate = timezone.now() + datetime.timedelta(weeks=1)
        if request.POST.get('task_duedate') != '':
            task_duedate = datetime.datetime.fromtimestamp(
                int(request.POST.get('task_duedate', False)))

        task = Task(
            text=text,
            title=task_title,
            start_date=now,
            due_date=task_duedate,
            project=proj)

        task.save()
```

`taskManager/templates/taskManager/task_details.html:11-12`

```
                <!--A3: Cross Site Scripting (XSS) -->
                {{task.title|safe}}
```

`taskManager/templates/taskManager/task_details.html:47-48`

```
                                  <!--A3: Cross Site Scripting (XSS) -->
                                  {{task.text|safe}}
```

<a id="finding-access-001"></a>

### [MEDIUM] manage_groups POST 分支缺少权限检查：普通用户可提升任意用户到管理员组

- 编号：`ACCESS-001`
- 类别：`access_control`
- CWE：`CWE-862`
- 入口身份：可自助注册的用户
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

manage_groups 的 POST 分支缺少 can_change_group 权限检查（GET 分支有），任意登录用户可把任何用户拉入 admin_g 等特权组，属于缺失的功能级访问控制。

**触发条件。** 登录后 POST /taskManager/manage_groups/，accesslevel=admin_g、userid=<任意用户ID>。

**数据流。** 登录用户 POST /taskManager/manage_groups/：POST 分支仅检查 is_authenticated（views.py:116-138），无 has_perm('can_change_group')（该权限检查只存在于 GET 分支 views.py:155）→ post_data["accesslevel"] 可为 admin_g/project_managers/team_member，post_data["userid"] 任意用户 → specified_user.groups.add(grp)。入口身份：registered_open（注册开放且无需激活）。

**影响。** 任何自助注册的普通用户都能把自己或他人加入 admin_g/project_managers 组，获得应用内管理员角色（admin_level 判断、角色展示、任务可见性旁路），破坏角色模型。

**修复。** POST 分支同样要求 has_perm('can_change_group')；组名白名单校验之外还应校验请求者是否有权授予该组；建议用 Django 权限系统 + 视图装饰器统一控制。

**复核员指出的最弱一环。** 最需核实的是 POST 分支是否真的缺 can_change_group、且 admin_g 是否有实际特权。views.py:116-138 POST 分支只查 is_authenticated() 就直接 groups.add；同函数 GET 分支（155）才有 has_perm('can_change_group')。admin_g 在 dashboard/profile_view/task_details（views.py:471、497、603）授予 admin_level/角色与任务可见性旁路，提权有实际含义。注册开放使"任意登录用户"门槛极低。

**判定历史。**

- 复核员同意：核实 views.py:112-165、471/497/603-618 的 admin_g 消费点。功能级访问控制缺失属实；因需要已登录会话、且应用内权限（非全站管理员）有限，medium 合理。（最弱一环：最需核实的是 POST 分支是否真的缺 can_change_group、且 admin_g 是否有实际特权。views.py:116-138 POST 分支只查 is_authenticated() 就直接 groups.add；同函数 GET 分支（155）才有 has_perm('can_change_group')。admin_g 在 dashboard/profile_view/task_details（views.py:471、497、603）授予 admin_level/角色与任务可见性旁路，提权有实际含义。注册开放使"任意登录用户"门槛极低。）

**证据。**

`taskManager/views.py:116-138`

```
    if user.is_authenticated():

        user_list = User.objects.order_by('date_joined')

        if request.method == 'POST':

            post_data = request.POST.dict()

            accesslevel = post_data["accesslevel"].strip()

            if accesslevel in ['admin_g', 'project_managers', 'team_member']:

                # Create the group if it doesn't already exist
                try:
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

`taskManager/views.py:154-163`

```
        else:
            if user.has_perm('can_change_group'):
                return render_to_response(
                    'taskManager/manage_groups.html',
                    {
                        'users': user_list,
                        'logged_in': True},
                    RequestContext(request))
            else:
                return redirect('/taskManager/', {'permission': False})
```

<a id="finding-access-003"></a>

### [MEDIUM] task_details/profile_view 读侧 IDOR：匿名读取任意任务与用户资料

- 编号：`ACCESS-003`
- 类别：`access_control`
- CWE：`CWE-639`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

task_details 与 profile_view 按 URL 中的 ID 直接取对象渲染，无登录与归属校验，匿名可读取任意任务内容与任意用户资料（读侧 IDOR）。

**触发条件。** GET /taskManager/<project_id>/<task_id>/ 或 /taskManager/profile_view/<user_id>，直接枚举 ID。

**数据流。** URL 参数 task_id → task_details 直接 Task.objects.get(pk=task_id) 后渲染完整任务（views.py:593-625），assigned_to/logged_in/admin_level 只是计算出的布尔标记、未用于任何权限判断；URL 参数 user_id → profile_view 直接 User.objects.get(pk=user_id) 渲染资料（views.py:491-508，含邮箱等字段）。两视图均无 is_authenticated 与归属校验。入口身份：anonymous。

**影响。** 匿名攻击者按 ID 枚举即可读取任意用户的任务内容（标题/正文以 |safe 渲染，叠加 XSS-003）与任意用户的资料（姓名、邮箱等），造成业务数据与个人信息泄露。

**修复。** task_details/profile_view 要求登录并校验归属（任务/用户资料仅对分配成员或请求者本人可见）；不要把 assigned_to 当权限、仅作界面标记；敏感资料字段（邮箱等）限制展示范围。

**复核员指出的最弱一环。** 最站不住的一环是"assigned_to/logged_in 只是界面标记、不构成访问控制，内容仍无条件渲染"。我重读了 views.py:593-625：logged_in（599-600）、admin_level、pmanager_level、assigned_to 全部只是计算出的布尔值塞进模板上下文，视图里没有任何权限分支、无 redirect、无 is_authenticated 门槛；task = Task.objects.get(pk=task_id)（595）只按 task_id 取值，project_id 参数甚至完全未参与校验。再看 task_details.html 全文 1-106：{{task.title|safe}}（12）、{{task.text|safe}}（48）、笔记表格（78-88）均为无条件渲染，没有一处 {% if logged_in %} / {% if assigned_to %} 包裹内容，匿名访问者照单全收。profile_view（491-508）同样无 is_authenticated，profile_view.html:9/23 无条件输出姓名与邮箱；taskManager_urls.py:45-46、65-66 路由直接映射、无装饰器。

**判定历史。**

- 复核员同意：核实了 task_details（views.py:593-625）与 profile_view（views.py:491-508）均无登录/归属校验，且两个模板对任务标题、正文、笔记、用户姓名邮箱一律无条件渲染（task_details.html:12/48/78-88、profile_view.html:9/23），assigned_to 等标志未用于任何内容隐藏；URL 映射（taskManager_urls.py:45-46、65-66）无中间层鉴权。匿名按 ID 枚举即可读取任意任务与用户资料，读侧 IDOR 成立，medium 恰当。（最弱一环：最站不住的一环是"assigned_to/logged_in 只是界面标记、不构成访问控制，内容仍无条件渲染"。我重读了 views.py:593-625：logged_in（599-600）、admin_level、pmanager_level、assigned_to 全部只是计算出的布尔值塞进模板上下文，视图里没有任何权限分支、无 redirect、无 is_authenticated 门槛；task = Task.objects.get(pk=task_id)（595）只按 task_id 取值，project_id 参数甚至完全未参与校验。再看 task_details.html 全文 1-106：{{task.title|safe}}（12）、{{task.text|safe}}（48）、笔记表格（78-88）均为无条件渲染，没有一处 {% if logged_in %} / {% if assigned_to %} 包裹内容，匿名访问者照单全收。profile_view（491-508）同样无 is_authenticated，profile_view.html:9/23 无条件输出姓名与邮箱；taskManager_urls.py:45-46、65-66 路由直接映射、无装饰器。）

**证据。**

`taskManager/views.py:593-604`

```
def task_details(request, project_id, task_id):

    task = Task.objects.get(pk=task_id)

    logged_in = True

    if not request.user.is_authenticated():
        logged_in = False

    admin_level = False
    if request.user.groups.filter(name='admin_g').exists():
        admin_level = True
```

`taskManager/views.py:605-625`

```
    pmanager_level = False
    if request.user.groups.filter(name='project_managers').exists():
        pmanager_level = True

    assigned_to = False
    if task.users_assigned.filter(username=request.user.username).exists():
        assigned_to = True
    elif admin_level:
        assigned_to = True
    elif pmanager_level:
        project_users = task.project.users_assigned
        if project_users.filter(username=request.user.username).exists():
            assigned_to = True

    return render(request,
                  'taskManager/task_details.html',
                  {'task': task,
                   'assigned_to': assigned_to,
                   'logged_in': logged_in,
                   'completed_task': "Yes" if task.completed else "No"})
```

`taskManager/views.py:491-508`

```
def profile_view(request, user_id):
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return redirect("/taskManager/dashboard")

    if request.user.groups.filter(name='admin_g').exists():
        role = "Admin"
    elif request.user.groups.filter(name='project_managers').exists():
        role = "Project Manager"
    else:
        role = "Team Member"

    sorted_projects = Project.objects.filter(
        users_assigned=request.user.id).order_by('title')

    return render(request, 'taskManager/profile_view.html',
                  {'user': user, 'role': role, 'project_list': sorted_projects})
```

<a id="finding-config-001"></a>

### [MEDIUM] DEBUG/TEMPLATE_DEBUG 开启并提交进仓库，错误页泄露敏感信息

- 编号：`CONFIG-001`
- 类别：`config`
- CWE：`CWE-215`
- 入口身份：无请求入口
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

settings.py 中 DEBUG=True 且 TEMPLATE_DEBUG=True 被提交，生产运行会暴露调试页与敏感配置。

**触发条件。** 任何请求触发未捕获异常（如 task_edit 缺参数）即回显 Django 调试页；ALLOWED_HOSTS=[] 也暗示未按生产标准部署。

**影响。** 生产环境开启 DEBUG 后，任何未处理异常都回显完整堆栈、局部变量与配置片段（含 SECRET_KEY、数据库路径等），大幅降低后续攻击门槛。

**修复。** 生产环境设 DEBUG=False、TEMPLATE_DEBUG=False，并配置 ALLOWED_HOSTS；调试信息只留在日志文件中。

**复核员指出的最弱一环。** 最需核实的是 DEBUG/TEMPLATE_DEBUG 是否真的被提交且无环境覆盖。settings.py:28-29 明文置 True，无环境变量回退，ALLOWED_HOSTS=[]（31 行）印证未按生产标准部署；DEBUG=True 时 Django 1.8 的异常页会回显堆栈、局部变量与 settings 内容。

**判定历史。**

- 复核员同意：核实 settings.py:26-31。CWE-215 成立。对本训练应用而言 medium 处于可接受上限（SECRET_KEY 本就公开，泄露增益有限），不构成严重性明显偏高，维持 medium。（最弱一环：最需核实的是 DEBUG/TEMPLATE_DEBUG 是否真的被提交且无环境覆盖。settings.py:28-29 明文置 True，无环境变量回退，ALLOWED_HOSTS=[]（31 行）印证未按生产标准部署；DEBUG=True 时 Django 1.8 的异常页会回显堆栈、局部变量与 settings 内容。）

**证据。**

`taskManager/settings.py:26-29`

```
# A5: Security Misconfiguration
# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True
TEMPLATE_DEBUG = True
```

<a id="finding-crypto-001"></a>

### [MEDIUM] 口令使用 MD5 哈希存储，内置超管口令可被快速离线破解

- 编号：`CRYPTO-001`
- 类别：`crypto`
- CWE：`CWE-916`
- 入口身份：无请求入口
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

口令哈希被强制降级为加盐 MD5（MD5PasswordHasher），fixtures 中的超级用户口令也以 md5$ 形式入库，离线破解成本极低。

**触发条件。** settings.py 强制 MD5PasswordHasher，所有 set_password 都产出 md5$<salt>$<hash>（见 fixtures/users.json:9）。

**影响。** 一旦数据库泄露，加盐 MD5 可被快速离线破解，内置的 admin/seth 等超级用户口令被还原，导致全站沦陷。

**修复。** 改用默认的 PBKDF2 并提高迭代次数（或 Argon2/bcrypt）；用 migrate_hashers 类流程在登录时平滑迁移存量 MD5 哈希；重置 fixture 账号密码。

**复核员指出的最弱一环。** 最需核实的是 PASSWORD_HASHERS 覆盖是否生效、fixture 口令是否为 md5$ 形式。settings.py:101 明确指定 MD5PasswordHasher 为唯一 hasher，所有 set_password 产出加盐 MD5；fixtures/users.json:9 的 admin 口令正是 md5$<salt>$<hash> 格式。离线破解成本低属实。

**判定历史。**

- 复核员同意：核实 settings.py:100-101、fixtures/users.json:1-20。CWE-916 成立；影响依赖数据库泄露这一前提，medium 合理。（最弱一环：最需核实的是 PASSWORD_HASHERS 覆盖是否生效、fixture 口令是否为 md5$ 形式。settings.py:101 明确指定 MD5PasswordHasher 为唯一 hasher，所有 set_password 产出加盐 MD5；fixtures/users.json:9 的 admin 口令正是 md5$<salt>$<hash> 格式。离线破解成本低属实。）

**证据。**

`taskManager/settings.py:100-101`

```
# A6: Sensitive Data Exposure
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
```

`fixtures/users.json:8-9`

```
      "username" : "admin",
      "password": "md5$c77N8n6nJPb1$3b35343aac5e46740f6e673521aa53dc",
```

<a id="finding-csrf-001"></a>

### [MEDIUM] profile_by_id 改密端点豁免 CSRF，可被跨站请求改密

- 编号：`CSRF-001`
- 类别：`csrf`
- CWE：`CWE-352`
- 入口身份：可自助注册的用户
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

profile_by_id 是修改用户密码的敏感端点却 csrf_exempt，攻击者可伪造跨站表单在受害者浏览器中改掉其密码。

**触发条件。** 已登录受害者访问攻击者页面，页面自动提交 POST /taskManager/profile/<user_id>（password 字段任意）。

**数据流。** 受害者浏览器中被植入的表单 → POST /taskManager/profile/<user_id>（@csrf_exempt，taskManager/views.py:710，无 CSRF token 校验）→ password 参数被直接 set_password 保存（views.py:726-727），会话 Cookie 由浏览器自动携带。入口身份：registered_open（受害者需已登录）。

**影响。** 攻击者诱导已登录用户访问恶意页面即可让浏览器代其发起改密请求，账号被锁定/接管。

**修复。** 移除 @csrf_exempt，恢复 CsrfViewMiddleware 保护（模板中已用 {% csrf_token %}）；改密操作额外要求当前密码或二次验证。

**复核员指出的最弱一环。** 最需核实的是 csrf_exempt 是否真的使改密免 CSRF 校验，以及跨站表单能否指定新密码。views.py:710 的 @csrf_exempt 对该视图整体生效（CsrfViewMiddleware 在 settings.py:47 已启用，仅此处豁免）；726-727 用 POST password 直接 set_password。攻击者页自动提交的表单可携带任意 password 值，浏览器自动带 Cookie，改密成立。

**判定历史。**

- 复核员同意：核实 views.py:710-732、settings.py:44-52。敏感端点 CSRF 豁免属实；虽与 AUTH-002 同端点，但作为独立 CWE-352 弱点记录 medium 恰当。（最弱一环：最需核实的是 csrf_exempt 是否真的使改密免 CSRF 校验，以及跨站表单能否指定新密码。views.py:710 的 @csrf_exempt 对该视图整体生效（CsrfViewMiddleware 在 settings.py:47 已启用，仅此处豁免）；726-727 用 POST password 直接 set_password。攻击者页自动提交的表单可携带任意 password 值，浏览器自动带 Cookie，改密成立。）

**证据。**

`taskManager/views.py:710-712`

```
@csrf_exempt
def profile_by_id(request, user_id):
    user = User.objects.get(pk=user_id)
```

`taskManager/views.py:726-727`

```
            if request.POST.get('password'):
                user.set_password(request.POST.get('password'))
```

<a id="finding-file-002"></a>

### [MEDIUM] 上传文件名无校验且可路径穿越写入静态目录

- 编号：`FILE-002`
- 类别：`file_access`
- CWE：`CWE-434`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

上传文件名、路径与扩展名完全由用户控制且写入 /static/ 目录，无任何内容校验（命令注入之外独立的任意文件写入/同源内容托管问题）。

**触发条件。** POST /taskManager/<project_id>/upload/，name 形如 ../../x.html 或任意 .html 扩展名。

**数据流。** POST 参数 name（taskManager/views.py:178，无鉴权）→ store_uploaded_file 以 upload_dir + '/' + title 作为落盘路径且不校验扩展名/内容（taskManager/misc.py:26-39）→ 上传目录位于 /static/ 下，文件由同源 URL 直接伺服。入口身份：anonymous（CSRF token 可从 GET 表单页获得）。

**影响。** 匿名攻击者可向静态目录写入任意扩展名文件（含 ../ 穿越到静态目录其他位置），在应用同源下托管任意 HTML/JS，实施存储型 XSS、钓鱼或静态资源篡改。

**修复。** 文件名服务端随机生成并固定白名单扩展名；校验真实内容类型；写入目录固定且用 realpath 校验；上传目录禁止脚本执行（X-Content-Type-Options、静态目录与上传目录分离）。

**复核员指出的最弱一环。** 最需核实的是写入目录是否真在静态伺服范围内、文件名/扩展名是否全无校验。misc.py:24-41：upload_dir 为 taskManager/static/taskManager/uploads（staticfiles 的 AppDirectoriesFinder 在 DEBUG 下伺服 app 的 static 目录），返回路径 '/static/taskManager/uploads/%s'；title 无白名单、无扩展名/内容校验，../ 与任意 .html 均可写；settings.py:58-59 强制 TemporaryFileUploadHandler，temp 源文件存在，mv 链路完整。

**判定历史。**

- 复核员同意：核实 misc.py:24-41、settings.py:58-59、upload.html（表单含 name/file 字段）。同源托管任意内容成立；在 CMDI-001/SQLI-001 已覆盖更高后果的前提下，独立记 medium 恰当。（最弱一环：最需核实的是写入目录是否真在静态伺服范围内、文件名/扩展名是否全无校验。misc.py:24-41：upload_dir 为 taskManager/static/taskManager/uploads（staticfiles 的 AppDirectoriesFinder 在 DEBUG 下伺服 app 的 static 目录），返回路径 '/static/taskManager/uploads/%s'；title 无白名单、无扩展名/内容校验，../ 与任意 .html 均可写；settings.py:58-59 强制 TemporaryFileUploadHandler，temp 源文件存在，mv 链路完整。）

**证据。**

`taskManager/misc.py:24-39`

```
def store_uploaded_file(title, uploaded_file):
    """ Stores a temporary uploaded file on disk """
    upload_dir_path = '%s/static/taskManager/uploads' % (
        os.path.dirname(os.path.realpath(__file__)))
    if not os.path.exists(upload_dir_path):
        os.makedirs(upload_dir_path)

    # A1: Injection (shell)
    # Let's avoid the file corruption race condition!
    os.system(
        "mv " +
        uploaded_file.temporary_file_path() +
        " " +
        "%s/%s" %
        (upload_dir_path,
         title))
```

<a id="finding-redirect-001"></a>

### [MEDIUM] logout 端点开放重定向

- 编号：`REDIRECT-001`
- 类别：`redirect`
- CWE：`CWE-601`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

logout 端点把 GET 参数 redirect 直接交给 redirect()，无白名单校验，构成开放重定向。

**触发条件。** GET /taskManager/logout?redirect=//evil.example/ 或 https://evil.example。

**数据流。** GET 参数 redirect（taskManager/views.py:387）→ redirect(request.GET.get('redirect', '/taskManager/'))，Django 1.8 的 redirect() 不校验 scheme/host → 302 跳到任意外部 URL。入口身份：anonymous。

**影响。** 攻击者用站内链接（如 /taskManager/logout?redirect=https://evil.example）做钓鱼跳板，借用应用域名的可信度。

**修复。** 只允许站内相对路径：用 django.utils.http.is_safe_url（或升级 Django 后 redirect 自带校验）校验 redirect 目标，否则回落到固定首页。

**复核员指出的最弱一环。** 最需核实的是 Django 1.8.3 的 redirect() 是否真的不校验目标。logout_view（views.py:385-387）把 GET 参数 redirect 原样传入；Django 1.8.3 的 redirect() 对 scheme/host 无 is_safe_url 类校验（该校验是后续版本才加入的），//evil.example 或 https://evil.example 会 302 到外部。

**判定历史。**

- 复核员同意：核实 views.py:385-387、requirements.txt:1（Django==1.8.3）、urls.py:33。开放重定向属实，medium 合理。（最弱一环：最需核实的是 Django 1.8.3 的 redirect() 是否真的不校验目标。logout_view（views.py:385-387）把 GET 参数 redirect 原样传入；Django 1.8.3 的 redirect() 对 scheme/host 无 is_safe_url 类校验（该校验是后续版本才加入的），//evil.example 或 https://evil.example 会 302 到外部。）

**证据。**

`taskManager/views.py:385-387`

```
def logout_view(request):
    logout(request)
    return redirect(request.GET.get('redirect', '/taskManager/'))
```

<a id="finding-xss-001"></a>

### [MEDIUM] search 页面 {{q|safe}} 反射型 XSS

- 编号：`XSS-001`
- 类别：`xss`
- CWE：`CWE-79`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

search 页把 GET 参数 q 经 |safe 输出在 <a href> 属性里，属性逃逸即可注入脚本，匿名可达的反射型 XSS。

**触发条件。** GET /taskManager/search/?q="><script>...</script> 等属性逃逸载荷。

**数据流。** GET 参数 q（taskManager/views.py:662，search 视图无鉴权）→ 传入模板上下文（views.py:672）→ search.html 第 14 行 href 属性内 {{q|safe}} 关闭自动转义（templates/taskManager/search.html:14）。入口身份：anonymous。

**影响。** 攻击者构造链接诱导受害者点击（或利用日志/头像等载体），在受害者同源页面执行脚本：配合 SESSION_COOKIE_HTTPONLY=False 可窃取会话 Cookie、冒用身份。

**修复。** 去掉 |safe；对 URL 查询参数用 django.utils.http.urlencode 重新编码，或把 q 输出到文本位置并保持自动转义。

**复核员指出的最弱一环。** 最需核实的是 href 属性内的 |safe 能否被属性逃逸利用。search.html:14 把 GET 参数 q 原样放入 href="/taskManager/search/?q={{q|safe}}"，无任何 URL 编码或转义；q 来自 views.py:662 的 request.GET.get('q','')。

**判定历史。**

- 复核员同意：核实 views.py:661-675（q 取自 GET、未经处理进上下文、视图无鉴权）与 search.html:13-14（href 属性内 {{q|safe}}）。q 以 '"><script>...' 开头即可闭合 href 属性注入脚本，反射型 XSS 成立，medium 合理。（最弱一环：最需核实的是 href 属性内的 |safe 能否被属性逃逸利用。search.html:14 把 GET 参数 q 原样放入 href="/taskManager/search/?q={{q|safe}}"，无任何 URL 编码或转义；q 来自 views.py:662 的 request.GET.get('q','')。）

**证据。**

`taskManager/views.py:661-675`

```
def search(request):
    query = request.GET.get('q', '')

    my_project_list = Project.objects.filter(
        users_assigned=request.user.id).filter(
            title__icontains=query).order_by('title')
    my_task_list = Task.objects.filter(
        users_assigned=request.user.id).filter(
            title__icontains=query).order_by('title')
    return render(request,
                  'taskManager/search.html',
                  {'q': query,
                   'task_list': my_task_list,
                   'project_list': my_project_list,
                   'user': request.user})
```

`taskManager/templates/taskManager/search.html:13-14`

```
                    <!--A3: Cross Site Scripting (XSS) -->
                    <a href="/taskManager/search/?q={{q|safe}}" id="loading-btn" class="btn btn-warning btn-xs"><i class="fa fa-refresh"></i> Refresh</a>
```

<a id="finding-xss-002"></a>

### [MEDIUM] tm_settings 页面 {{v|safe}} 渲染 request.META：请求头反射 XSS 与环境信息泄露

- 编号：`XSS-002`
- 类别：`xss`
- CWE：`CWE-79`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

/taskManager/settings/ 把 request.META（含攻击者可控的 HTTP_* 请求头与服务器环境变量）用 |safe 原样渲染，匿名反射型 XSS + 敏感信息泄露。

**触发条件。** GET /taskManager/settings/，请求头（如 User-Agent）携带 <script> 等载荷。

**数据流。** HTTP 请求头（如 User-Agent、Referer，攻击者可控）→ request.META（taskManager/views.py:838）→ tm_settings 渲染 settings.html（views.py:839-841）→ {{v|safe}} 无转义输出所有键值（templates/taskManager/settings.html:28）。入口身份：anonymous。

**影响。** 攻击者把脚本放在任意请求头即可在受害者浏览器执行（反射型 XSS）；该页同时把服务器环境变量（PATH、HOME 等）原样泄露给匿名访问者。

**修复。** 删除该 DEBUG 页面或仅对管理员开放；去掉 |safe，对值做 HTML 转义；不要渲染整个 request.META，仅列出必要字段。

**复核员指出的最弱一环。** 最需核实的是攻击者能否把可控值塞进 request.META 并以 |safe 回显。settings.html:28 {{v|safe}} 在 {% for n,v in settings.items %} 循环里输出全部值，settings 即 views.py:838 的 request.META；Django 1.8 对 HTTP_* 头不做 HTML 清洗。

**判定历史。**

- 复核员同意：核实 views.py:837-841（request.META 直接进上下文）、settings.html:21-38（{{v|safe}} 遍历输出全部值，键名 n 转义、值 v 不转义）。HTTP_USER_AGENT/HTTP_REFERER 以原始字符串存在于 META（Django 1.8 不清洗），Referer 可由攻击者链接控制实现跨用户反射；环境变量同时泄露。medium 合理。（最弱一环：最需核实的是攻击者能否把可控值塞进 request.META 并以 |safe 回显。settings.html:28 {{v|safe}} 在 {% for n,v in settings.items %} 循环里输出全部值，settings 即 views.py:838 的 request.META；Django 1.8 对 HTTP_* 头不做 HTML 清洗。）

**证据。**

`taskManager/views.py:837-841`

```
def tm_settings(request):
    settings_list = request.META
    return render(request,
                  'taskManager/settings.html',
                  {'settings': settings_list})
```

`taskManager/templates/taskManager/settings.html:22-29`

```
                    {% for n,v in settings.items %}
                      <tr>
                          <td>
                              {{n}}
                          </td>
                          <td>
                              {{v|safe}}
                          </td>
```

<a id="finding-xss-004"></a>

### [MEDIUM] 用户名经 |safe 渲染到全站导航栏，存储型 XSS

- 编号：`XSS-004`
- 类别：`xss`
- CWE：`CWE-79`
- 入口身份：可自助注册的用户
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

所有页面的导航栏都以 |safe 渲染当前用户名，而用户名可通过 profile_by_id 匿名越权写成任意字符串，形成登录即触发的存储型 XSS。

**触发条件。** 经 POST /taskManager/profile/<用户ID> 把 username 改为 <script> 载荷，该用户登录后任意页面执行。

**数据流。** user.username 由 profile_by_id 直接写入任意 POST 值（taskManager/views.py:718-719，无鉴权 IDOR，见 AUTH-002）→ 全局模板 base_backend.html:58 与 tutorials/base.html:54 用 {{ user.username|safe }} 渲染 → 该用户每次打开页面即执行注入脚本。入口：注入 anonymous；受害者触发 registered_open。

**影响。** 用户名被植入脚本后，受害者登录并浏览任意页面都会执行（持久存储型 XSS）；配合 SESSION_COOKIE_HTTPONLY=False 直接窃取会话。

**修复。** 去掉两处 |safe；对 username 字段做格式校验（字母数字下划线等）；修复 profile_by_id 的越权写入（见 AUTH-002）。

**复核员指出的最弱一环。** 最需核实的是 username 是否可被攻击者写为脚本、且确实以 |safe 输出。tutorials/base.html:53-54 与 base_backend.html:57-58 均无转义输出 username；profile_by_id（views.py:718-719）@csrf_exempt、无鉴权地把 POST username 写入任意用户。

**判定历史。**

- 复核员同意：核实 views.py:710-732（profile_by_id 匿名把 POST username 赋给任意用户，见 AUTH-002）、base_backend.html:57-58 与 tutorials/base.html:53-54 两处 {{ user.username|safe }}。username 字段 30 字符上限可容纳 <script>alert(1)</script>，注入匿名、受害登录即触发，medium 合理。（最弱一环：最需核实的是 username 是否可被攻击者写为脚本、且确实以 |safe 输出。tutorials/base.html:53-54 与 base_backend.html:57-58 均无转义输出 username；profile_by_id（views.py:718-719）@csrf_exempt、无鉴权地把 POST username 写入任意用户。）

**证据。**

`taskManager/templates/taskManager/base_backend.html:57-58`

```
                        <!--A3: Cross Site Scripting (XSS) -->
                        <span class="username"><i class="fa fa-user fa-fw"></i> {{ user.username|safe }}</span>
```

`taskManager/templates/taskManager/tutorials/base.html:53-54`

```
                    <a data-toggle="dropdown" class="dropdown-toggle" href="#">
                        <span class="username">{{ user.username|safe }}</span>
```

`taskManager/views.py:718-719`

```
            if request.POST.get('username') != user.username:
                user.username = request.POST.get('username')
```

<a id="finding-config-003"></a>

### [LOW] 会话 Cookie 未设 HttpOnly，XSS 可直接窃取会话

- 编号：`CONFIG-003`
- 类别：`config`
- CWE：`CWE-1004`
- 入口身份：无请求入口
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

SESSION_COOKIE_HTTPONLY=False 允许页面脚本读取会话 Cookie，放大了 XSS 的后果。

**触发条件。** 该配置使 document.cookie 可读取 sessionid；触发点即 XSS-001~004。

**影响。** 任何一处 XSS（本应用存在多处）都能直接读走 sessionid，把会话 Cookie 发给攻击者，无需再绕过 HttpOnly。

**修复。** 设 SESSION_COOKIE_HTTPONLY=True（Django 默认），并考虑 SESSION_COOKIE_SECURE=True、CSRF_COOKIE_HTTPONLY 等加固。

**复核员指出的最弱一环。** 最需核实的是该配置是否真实存在并覆盖 Django 默认值（True）。settings.py:110 显式 SESSION_COOKIE_HTTPONLY=False，确实关闭了默认保护，document.cookie 可读 sessionid。

**判定历史。**

- 复核员同意：核实 settings.py:108-110。配置属实，其危害依赖前述多处 XSS 作为窃取通道，low 恰当。（最弱一环：最需核实的是该配置是否真实存在并覆盖 Django 默认值（True）。settings.py:110 显式 SESSION_COOKIE_HTTPONLY=False，确实关闭了默认保护，document.cookie 可读 sessionid。）

**证据。**

`taskManager/settings.py:108-110`

```
# Needs compatibility with older Django!
SESSION_SERIALIZER = "django.contrib.sessions.serializers.PickleSerializer"
SESSION_COOKIE_HTTPONLY = False
```

<a id="finding-comp-001"></a>

### [INFO] 使用已停止维护的 Django 1.8.3，存在已知未修复漏洞

- 编号：`COMP-001`
- 类别：`other`
- CWE：`CWE-1104`
- 入口身份：无请求入口
- 置信度：`medium`
- 状态：`confirmed`
- 复核员：同意

依赖 Django==1.8.3，早已停止维护且缺少其后多个安全修复（如 redirect() 的 URL 校验），属过时组件。

**触发条件。** requirements.txt 固定 Django==1.8.3；例如 logout 的 redirect() 在 1.8.3 没有目标校验，直接形成 REDIRECT-001。

**影响。** 1.8.3 之后 Django 修复了大量安全漏洞（CSRF、重定向校验、XSS 等），继续使用意味着继承这些已知漏洞；且框架已停止维护，无法获得安全更新。

**修复。** 升级到受支持的 Django LTS 版本并回归测试；升级前先按官方升级清单处理不兼容项。

**复核员指出的最弱一环。** 最需核实的是版本是否确为 1.8.3 且已 EOL。requirements.txt:1 固定 Django==1.8.3；1.8 系列早已停止安全支持，后续版本的修复（含 redirect 校验等）均未包含，事实无误。

**判定历史。**

- 复核员同意：核实 requirements.txt。过时组件事实成立，作为背景性发现 info 恰当。（最弱一环：最需核实的是版本是否确为 1.8.3 且已 EOL。requirements.txt:1 固定 Django==1.8.3；1.8 系列早已停止安全支持，后续版本的修复（含 redirect 校验等）均未包含，事实无误。）

**证据。**

`requirements.txt:1-1`

```
Django==1.8.3
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

覆盖范围：taskManager/settings.py、两级 URL 配置（urls.py、taskManager_urls.py）、views.py 全部 36 个端点、forms.py、models.py、misc.py、fixtures（users/notes/profiles）、requirements.txt、README、runapp/reset_db 脚本，以及全部含危险输出的模板（settings/search/task_details/base_backend/tutorials 等）与关键表单模板。migrations 目录抽查确认无自定义权限定义。未覆盖：Django 内置 admin 与静态资源目录的详细审计（vendor/static 默认跳过），以及需要运行环境才能验证的运行时行为（如 DEBUG 页实际内容、SMTP 端口 1025 的邮件投递）。

## 局限

本次为纯静态代码审计，未实际运行应用。以下结论依赖运行时行为的验证：命令注入与 pickle RCE 的实际执行需在目标环境确认（但代码路径与拼接方式已完整核对）；令牌暴力枚举的可行性取决于应用吞吐（10^6 空间、10 分钟窗口，需约千次/秒量级的请求能力）；Django 1.8.3 框架内部行为（redirect 不校验目标、signed_cookies 后端）依据该版本公开文档/源码判断，未在本仓库中直接引用框架源码；fixtures 中口令哈希能否破解取决于口令强度，仅能确认哈希算法强度不足。

## 复核意见

本轮复读了 RESET-001 与 ACCESS-003 的全部证据：views.py:739-809（reset_password/forgot_password 的令牌生成、10 分钟有效期、@csrf_exempt 与无节流）、views.py:491-508 与 593-625（profile_view/task_details 无鉴权且标志仅作模板上下文）、task_details.html 全文（任务标题/正文/笔记无条件渲染，无 {% if %} 隐藏）、profile_view.html（姓名邮箱无条件输出）、taskManager_urls.py:39-46/65-66（路由无装饰器）、README.md:8/16（Python 3.4+，证实 os.urandom 返回 bytes、令牌为 6 位十进制数字）。两条均同意：RESET-001 令牌空间上界 10^6、窗口 10 分钟、端点无任何速率限制/锁定，匿名账户接管成立，high 合理；ACCESS-003 读侧 IDOR 两处模板均无条件渲染内容，medium 恰当。其余 20 条发现已在第 1 轮复核并保持 agree，未重复审查。仍存疑虑之处：RESET-001 的可行性依赖部署层无任何反向代理节流（仓库内确实没有任何限速机制），若真实环境有 WAF 限速则严重性可下调；这一点不影响仓库代码本身的缺陷定性。

## 复核缺口

- `G1`（已回应）弱口令重置令牌可暴力破解：forgot_password（taskManager/views.py:788-794）把 os.urandom(6) 各字节的十进制串取前 6 位作为重置令牌（空间约 10^6、有效期 10 分钟），reset_password（views.py:739-775）为匿名 + @csrf_exempt 且无速率限制/失败锁定，知道目标邮箱即可在窗口内枚举令牌改掉任意账户密码（账户接管）。现有发现只覆盖了哈希强度（CRYPTO-001），未记录该令牌熵/限速问题。
  - 审计员回应：已重读 views.py:739-809 与 README.md。README 明确要求 Python 3.4+（README.md:8、16），因此在 Python 3 下 os.urandom(6) 返回 bytes、迭代得 int、str(x) 是十进制串，reset_token=res[:6] 是 6 位十进制数字（空间≤10^6）；有效期 10 分钟且 reset_password 匿名 + @csrf_exempt、无任何速率限制/失败锁定。已新增 finding RESET-001（high，CWE-307）记录该暴力枚举令牌导致的账户接管。
- `G2`（已回应）读侧 IDOR 未记录：task_details（taskManager/views.py:593-625）对任意 task_id 直接 Task.objects.get 并渲染，assigned_to/logged_in 只是传给模板的界面标记、不构成访问控制，匿名者可读取任意任务内容（标题/正文又以 |safe 渲染，与 XSS-003 叠加）；profile_view（views.py:491-508）同样把任意用户资料暴露给任何访问者。审计员只记录了写侧 IDOR（ACCESS-002），读侧数据暴露漏掉。
  - 审计员回应：已重读 views.py:491-508 与 593-625：task_details 按 task_id 直接取对象渲染，assigned_to/logged_in/admin_level 仅为布尔标记、未做任何权限分支；profile_view 按 user_id 直接渲染任意用户资料。已新增 finding ACCESS-003（medium，CWE-639）记录读侧 IDOR。
