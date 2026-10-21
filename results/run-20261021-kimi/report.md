# ylinux_old 应用安全审计报告

- 目标：`https://github.com/gwind/ylinux_old`，commit `8a7316deec88287d020eca21c38dad921b623ffc`
- 模型：审计员 `deepseek-v4-pro`，复核员 `kimi-k3`
- 时间：2026-10-21T09:28:29+08:00 → 2026-10-21T10:01:14+08:00
- 结论：确认 17 个问题，最高严重性为 high。
- 统计：已确认 17，待再确认 2，已排除 0；引用核对 48 条，未通过 0 条

## 发现总表

| 严重性 | 编号 | 问题 | 入口身份 | 状态 | 复核员 | 位置 |
| --- | --- | --- | --- | --- | --- | --- |
| high | [`AUTHZ-001`](#finding-authz-001) | XML-RPC 接口认证后无授权检查：任意注册用户可删除全站主题或篡改他人主题 | 可自助注册的用户 | confirmed | 同意 | `settings.py:164` |
| high | [`CRYPTO-001`](#finding-crypto-001) | 密码重置/激活密钥仅 20 位熵且无尝试限制，可枚举实现账户接管 | 匿名 | confirmed | 同意 | `app/account/models.py:364` |
| high | [`XSS-001`](#finding-xss-001) | 知识库/论坛帖子与主题正文存在存储型 XSS（Markdown 未启用 safe_mode 且模板 \|safe 输出） | 可自助注册的用户 | confirmed | 同意 | `app/ydata/models.py:258` |
| high | [`XSS-002`](#finding-xss-002) | 附件文件名注入帖子渲染 HTML 导致存储型 XSS | 可自助注册的用户 | confirmed | 同意 | `app/ydata/views.py:86` |
| medium | [`ACCESS-001`](#finding-access-001) | editPostAJAX 缺少属主校验：登录用户可篡改任意他人帖子 | 可自助注册的用户 | confirmed | 同意 | `app/wiki/views.py:447` |
| medium | [`ACCESS-002`](#finding-access-002) | /lab/update_post_profile 匿名可触发全站帖子批量改写 | 匿名 | confirmed | 同意 | `app/ylab/urls.py:8` |
| medium | [`ACCESS-004`](#finding-access-004) | 版块组权限未在阅读路径强制：受限版块主题/帖子/附件匿名可读 | 匿名 | confirmed | 同意 | `app/ydata/models.py:51` |
| medium | [`CONFIG-001`](#finding-config-001) | DEBUG=True 随仓库提交，且媒体目录带目录索引对外服务 | 无请求入口 | confirmed | 同意 | `settings.py:18` |
| medium | [`CONFIG-002`](#finding-config-002) | SECRET_KEY 硬编码提交进公开仓库，会话签名与令牌生成失效 | 无请求入口 | confirmed | 同意 | `settings.py:78` |
| medium | [`CRYPTO-002`](#finding-crypto-002) | 弱口令哈希（单轮 SHA1/MD5、弱盐）且登录接口无限速 | 无请求入口 | confirmed | 同意 | `app/account/models.py:62` |
| medium | [`CSRF-001`](#finding-csrf-001) | 全站缺少 CSRF 防护，Cookie 会话下的所有写操作可被跨站伪造 | 可自助注册的用户 | confirmed | 同意 | `settings.py:98` |
| medium | [`XSS-003`](#finding-xss-003) | 注册/密码重置视图将 URL key 未转义回显导致反射型 XSS | 匿名 | confirmed | 同意 | `app/account/urls.py:8` |
| low | [`ACCESS-003`](#finding-access-003) | 附件查看/下载端点无访问控制（权限模型不一致的加固项） | 匿名 | confirmed | 同意 | `app/ydata/views.py:101` |
| low | [`CONFIG-003`](#finding-config-003) | 数据库口令 '123456' 明文提交进仓库 | 无请求入口 | confirmed | 同意 | `settings.py:42` |
| low | [`EMAIL-001`](#finding-email-001) | 联系表单可被匿名滥用为任意收件人的邮件中继 | 匿名 | confirmed | 同意 | `app/home/views.py:34` |
| low | [`REDIRECT-001`](#finding-redirect-001) | 登录/退出 next 参数未校验导致开放重定向 | 匿名 | confirmed | 同意 | `app/account/views.py:42` |
| low | [`XSS-004`](#finding-xss-004) | 上传响应将文件名未转义拼入 HTML/JS 导致 self-XSS | 匿名 | confirmed | 同意 | `app/ylab/views.py:31` |
| low | [`DESER-001`](#finding-deser-001) | 会话数据 pickle 反序列化 + 公开 SECRET_KEY 的 MD5 签名（潜在 RCE） | 无请求入口 | needs_review | 同意 | `app/sessions/backends/base.py:86` |
| low | [`FILE-001`](#finding-file-001) | 附件上传文件名直接拼入保存路径（依赖框架 basename 清洗的纵深防御项） | 可自助注册的用户 | needs_review | 同意 | `app/ydata/views.py:78` |

发现列表来自 Agent 写入并经过引用核对的结构化结果。审计员综述写于复核之前，单条发现的状态以复核之后为准。线索处置、读过的文件、阶段记录、工具序列和逐条引用核对见 `appendix.md`；关键决策摘要见 `decisions.md`。

## 审计员综述

这是一个 Django 1.3 时代的论坛/知识库项目（ylinux_old，commit 8a7316d），采用自定义会话与认证中间件、内置 XML-RPC 接口。整体安全状况较差：内容渲染管线（Python-Markdown 2.0.3 无 safe_mode + 模板 |safe）使任何注册用户都能写入存储型 XSS；XML-RPC 接口只认证不授权，任意注册用户可删除全站主题或篡改他人主题；密码重置/激活令牌只有 20 位熵且无尝试限制，可被枚举实现账户接管；全站无 CSRF 防护；版块组权限（Catalog.has_access）只在写操作视图生效，所有阅读路径与附件下载均未强制，受限版块内容匿名可读；SECRET_KEY、DEBUG=True、数据库口令随仓库公开；口令使用单轮 SHA1/MD5 哈希且所有登录入口无限速。经两轮复核：FILE-001 降为 low 的纵深防御项；metaWeblog.newMediaObject 因模块未导入 settings（写盘前即 NameError）实际不可达；原 ACCESS-003 按复核意见改判为 low 加固项，并新增 ACCESS-004 覆盖“阅读路径整体未强制组权限”这一更宽范围的问题。共确认 15 条问题、2 条待复核，其中高危 4 条、中危 6 条、低危 7 条。

## 风险概览

最高风险按顺序：1) XSS-001/XSS-002 存储型 XSS（注册开放，可对所有浏览者执行脚本，且会话 Cookie 无 HttpOnly，可窃取会话接管账户）；2) AUTHZ-001 XML-RPC 无授权检查，任意注册用户可 delete_all_topic 清空全站或篡改他人主题；3) CRYPTO-001 密码重置密钥 2^20 可枚举空间 + 无速率限制，可接管任意已知邮箱的账户；4) CSRF-001 全站无 CSRF 防护，Cookie 会话下的所有写操作可被跨站伪造；5) ACCESS-004 版块组权限未在阅读路径强制，受限内容与附件匿名可读；6) 配置类问题（公开的 SECRET_KEY、DEBUG=True、数据库口令）使签名机制和错误信息对攻击者透明。修复优先级建议：先下线或加授权保护 XML-RPC 删除接口，再统一在阅读路径强制 has_access 并修复附件端点，随后为 Markdown 渲染加 safe_mode/HTML 白名单净化，最后替换口令哈希并引入 CSRF 中间件与令牌。

## 已确认的问题

<a id="finding-authz-001"></a>

### [HIGH] XML-RPC 接口认证后无授权检查：任意注册用户可删除全站主题或篡改他人主题

- 编号：`AUTHZ-001`
- 类别：`access_control`
- CWE：`CWE-862`
- 入口身份：可自助注册的用户
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

XML-RPC 接口的 delete_topic、delete_all_topic、edit_topic、new_topic 只做了“账号密码正确”的认证，没有做任何授权（属主或权限）检查，任意注册用户可删除全部主题或修改/删除他人的主题。

**触发条件。** 向 /xmlrpc/ POST 调用 delete_all_topic(user, passwd) 或 delete_topic(id, user, passwd)，凭任意自助注册账号即可。

**数据流。** 来源：XML-RPC POST 请求体（/xmlrpc/，lib/django_xmlrpc/views.py:87 `_marshaled_dispatch(request.raw_post_data)`）→ 方法注册：settings.py:164-175 XMLRPC_METHODS 暴露 delete_topic/delete_all_topic/metaWeblog.* → 授权缺失：lib/ylinux_xmlrpc.py:39-45 has_auth 只校验用户名密码，不检查任何权限或属主；delete_topic（47-58 行）按任意 id 删除，delete_all_topic（60-69 行）删除全站主题，edit_topic（168-183 行）可改任意主题。入口身份：任意注册用户（注册自助开放），账号密码通过 XML-RPC 逐请求提交。

**影响。** 任何注册用户可通过 /xmlrpc/ 调用 delete_all_topic 清空全站所有主题与回帖（不可恢复的数据破坏），或通过 delete_topic/edit_topic/new_topic 删除、篡改任意他人的主题。

**修复。** 为每个 XML-RPC 方法增加属主/权限校验（如仅允许管理员或主题作者），移除 delete_all_topic 或限定为超级用户；对 XML-RPC 接口做速率限制与审计日志。

**复核员指出的最弱一环。** 最弱一环是“这些方法是否真的在网络层注册暴露，而非死代码”。我核实了 lib/django_xmlrpc/views.py:122-149 在 import 时把 settings.XMLRPC_METHODS 注册进 dispatcher，urls.py:47 挂载 /xmlrpc/，handle_xmlrpc(81-92) 对 POST 的 raw_post_data 直接 _marshaled_dispatch；settings.py:164-175 确实暴露 delete_topic/delete_all_topic/metaWeblog.*。

**判定历史。**

- 复核员同意：授权缺失核实无误：ylinux_xmlrpc.py:39-45 has_auth 只 authenticate 用户名密码（上下文 20-60 行已通读，无任何权限位判断）；delete_topic(47-58) 按任意 id 删、delete_all_topic(60-69) 全表删除、edit_topic(168-185) 改任意主题，均无属主/权限判断。注册自助开放（request_register 邮件激活），故“任意注册用户可清空全站主题”成立。不可恢复的全站数据破坏，high 合理。（最弱一环：最弱一环是“这些方法是否真的在网络层注册暴露，而非死代码”。我核实了 lib/django_xmlrpc/views.py:122-149 在 import 时把 settings.XMLRPC_METHODS 注册进 dispatcher，urls.py:47 挂载 /xmlrpc/，handle_xmlrpc(81-92) 对 POST 的 raw_post_data 直接 _marshaled_dispatch；settings.py:164-175 确实暴露 delete_topic/delete_all_topic/metaWeblog.*。）

**证据。**

`settings.py:164-166`

```
XMLRPC_METHODS = (
    ('ylinux_xmlrpc.delete_topic', 'delete_topic'),
    ('ylinux_xmlrpc.delete_all_topic', 'delete_all_topic'),
```

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

`lib/ylinux_xmlrpc.py:168-181`

```
def edit_topic(postid, user, passwd, struct, publish):
    '''Edit one topic'''
    if not has_auth(user, passwd):
        raise Fault(-1, "Authentication Failure")

    try:
        topic = Topic.objects.get(pk=postid)
        if struct.has_key('title'):
            topic.name = st(struct['title'], 'utf-8')

        topic.updated = datetime.now()
        topic.save()
        if struct.has_key('description'):
            topic.save_file(st(struct['description'], 'utf-8'))
```

<a id="finding-crypto-001"></a>

### [HIGH] 密码重置/激活密钥仅 20 位熵且无尝试限制，可枚举实现账户接管

- 编号：`CRYPTO-001`
- 类别：`crypto`
- CWE：`CWE-330`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

注册激活码与密码重置码的熵只有 5 个十六进制字符（salt = sha1(str(random.random())).hexdigest()[:5]，约 20 位），且生成算法完全公开、无速率限制，攻击者可在线枚举密码重置密钥并接管任意已知邮箱的账户。

**触发条件。** 匿名向 /account/password/reset/ 提交目标邮箱（生成新 Register 行），然后遍历 2^20 候选 key 请求 /account/password/reset/<key>/，命中后提交新密码。

**影响。** 攻击者对目标邮箱请求密码重置后，枚举 2^20（约 105 万）个候选 activation_key 逐个请求 /account/password/reset/<key>/（无任何限速/锁定），命中即可为该邮箱对应用户设置新密码，实现任意账户接管；注册激活码同样可被枚举（抢注/冒用他人邮箱完成注册）。

**修复。** 激活/重置令牌使用至少 128 位 CSPRNG（os.urandom/SystemRandom）生成；给重置端点加尝试次数限制与令牌过期时间；重置成功后立即作废令牌。

**复核员指出的最弱一环。** 最弱一环是“20 位熵可在线枚举”的可达性——攻击者必须能让系统对目标邮箱生成 key 并无限速地试。我核实了 password_reset_request（views.py:173-187）对任意已注册邮箱即 get-or-create Register 并 reset_activation_key；password_reset（201-223）对 /account/password/reset/<key>/ 无任何限速、锁定或过期检查；salt 只有 sha1(random.random())[:5] 即 5 个十六进制字符（2^20≈105 万候选），email 已知时全部候选可离线预计算，在线逐个请求命中即改密。

**判定历史。**

- 复核员同意：核实：models.py:364-369 与 424-430（上下文 408-430 已通读）两处密钥生成均为 5 位十六进制盐 + sha1(salt+email)；account/views.py:166-196 password_reset_request 对任意已注册邮箱生成/重置 key 并（仅）邮件发送；201-223 password_reset 按 key 直接 SetPasswordForm.save()，无尝试限制、无过期校验（Register 模型 389-399 行只有 updated auto_now，无视图侧过期判断）。注册激活码同理可枚举。匿名远程账户接管，high 合理。（最弱一环：最弱一环是“20 位熵可在线枚举”的可达性——攻击者必须能让系统对目标邮箱生成 key 并无限速地试。我核实了 password_reset_request（views.py:173-187）对任意已注册邮箱即 get-or-create Register 并 reset_activation_key；password_reset（201-223）对 /account/password/reset/<key>/ 无任何限速、锁定或过期检查；salt 只有 sha1(random.random())[:5] 即 5 个十六进制字符（2^20≈105 万候选），email 已知时全部候选可离线预计算，在线逐个请求命中即改密。）

**证据。**

`app/account/models.py:364-369`

```
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

`app/account/views.py:210-219`

```
    try:
        user = User.objects.get(email=register.email)
    except User.DoesNotExist:
        return HttpResponseForbidden(u'<h2>无此 email 注册的用户 ： %s </h2>' % register.email)

    form = build_form (SetPasswordForm, request, user=user)

    if form.is_valid():
        form.clean_new_password2()
        form.save()
```

<a id="finding-xss-001"></a>

### [HIGH] 知识库/论坛帖子与主题正文存在存储型 XSS（Markdown 未启用 safe_mode 且模板 |safe 输出）

- 编号：`XSS-001`
- 类别：`xss`
- CWE：`CWE-79`
- 入口身份：可自助注册的用户
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

帖子（Post）与主题（Topic）正文在保存时由 Python-Markdown 2.0.3 渲染为 HTML，但 Post.save() 的 markup='none' 分支与 Topic.save_file() 都没有开启 safe_mode（库默认 safe_mode=False，不转义原始 HTML），渲染结果存库后在模板里用 |safe 原样输出，任何注册用户都可写入任意 HTML/脚本，对所有浏览者形成存储型 XSS。

**触发条件。** 注册用户向 /wiki/topic/<id>/replayAJAX/、/wiki/topic/<id>/addpost/ 提交含 HTML 的 body，或通过 /wiki/catalog/<id>/addtopic/、XML-RPC metaWeblog.newPost 提交含 HTML 的主题正文。

**数据流。** 来源：POST body（app/wiki/views.py:432-436 replayAJAX 的 request.POST['body']，或 app/ydata/forms.py:46 AddPostForm）以及主题正文（app/ydata/forms.py:98 Topic.save_file 的 text）→ 中间：Post.save()（app/ydata/models.py:258-260，markup='none' 调用 Markdown(...).convert() 无 safe_mode；lib/markdown/__init__.py:188 构造函数默认 safe_mode=False）和 Topic.save_file()（app/ydata/models.py:198-200 convertFile 无 safe_mode）→ 危险点：body_html 存库后经 {{ post.body_html|safe }}（app/wiki/utils.py:18）、{{ topic.body_html|safe }} 与 {{ POST_HTML|safe }}（templates/wiki/topic.html:54,59）、{{ p.body_html|safe }}（templates/bbs/topic.html:30）输出。入口身份：注册开放（account/views.py request_register 通过 email 自助激活），任何登录用户即可发帖/回帖。

**影响。** 攻击者在帖子或主题正文中写入 <script> 等原始 HTML，任何浏览该页面的用户（含管理员）都会执行；会话 Cookie 未设置 HttpOnly（app/sessions/middleware.py:37-41），可配合窃取会话实现账户接管，或挂马、钓鱼、篡改页面。

**修复。** 渲染用户内容时启用 safe_mode（或替换为白名单 HTML 清理库如 bleach）；在 save()/save_file() 中对 Markdown 输出做 HTML 净化后再入库；模板输出不再使用 |safe 或仅对可信字段使用。

**复核员指出的最弱一环。** 最弱一环是“Markdown 未开 safe_mode 时原始 HTML 是否真的原样透传”——如果库里另有转义，整条链就断了。我核实了 lib/markdown/__init__.py:188（构造函数默认 safe_mode=False，docstring 明确 safe_mode 作用是 "Disallow raw html"）、convertFile(428-459 行，应用 myfilter 后直接 convert，无任何 safe 处理）、ylinux_text_filter（models.py:396-452，只做 [A:id]/[wiki:id]/[img:id] 替换，不转义）、urlize/smiles 的 ExcludeTagsHTMLParser（util.py:41-72 把标签和属性原样重建，unescape 原样返回），整条渲染链确实没有 HTML 转义。

**判定历史。**

- 复核员同意：逐一核对了证据：Post.save() 的 markup='none' 分支（models.py:258-260）与 Topic.save_file（198-200）均未开 safe_mode；入口 replayAJAX（views.py:399-400 要求登录、432-436 硬编码 markup='none'）和 AddPostForm.save（forms.py:46）、AddTopicForm.save→save_file（forms.py:97-98）都可达；注册为邮件自助激活的开放注册（account/views.py:63-93），entry_role=registered_open 属实。输出端 wiki/utils.py:18、templates/wiki/topic.html:54/59 均 |safe。会话 Cookie 未设 HttpOnly（sessions/middleware.py:37-41 set_cookie 未传 httponly），impact 中窃取会话的说法成立。存储型 XSS 对所有浏览者（含管理员）生效，high 合理。（最弱一环：最弱一环是“Markdown 未开 safe_mode 时原始 HTML 是否真的原样透传”——如果库里另有转义，整条链就断了。我核实了 lib/markdown/__init__.py:188（构造函数默认 safe_mode=False，docstring 明确 safe_mode 作用是 "Disallow raw html"）、convertFile(428-459 行，应用 myfilter 后直接 convert，无任何 safe 处理）、ylinux_text_filter（models.py:396-452，只做 [A:id]/[wiki:id]/[img:id] 替换，不转义）、urlize/smiles 的 ExcludeTagsHTMLParser（util.py:41-72 把标签和属性原样重建，unescape 原样返回），整条渲染链确实没有 HTML 转义。）

**证据。**

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

`lib/markdown/__init__.py:185-189`

```
    def __init__(self,
                 extensions=[],
                 extension_configs={},
                 safe_mode = False, 
                 output_format=DEFAULT_OUTPUT_FORMAT):
```

`app/wiki/views.py:432-436`

```
        post_body = request.POST.get("body", None)
        if len(post_body) < 2:
            return {'error': u'您的回复太短，至少2个字符！'}
        post = Post(topic = topic, user = request.user, user_ip = ip, markup = 'none', body = post_body, parent = parent_post)
        post.save()
```

`app/wiki/utils.py:18-18`

```
<p>{{ post.body_html|safe }}</p>
```

`templates/wiki/topic.html:53-55`

```
  <div class="topic-body content">
    {{ topic.body_html|safe }}
  </div>
```

`templates/wiki/topic.html:58-60`

```
{% if posts %}
{{ POST_HTML|safe }}
{% endif %}
```

<a id="finding-xss-002"></a>

### [HIGH] 附件文件名注入帖子渲染 HTML 导致存储型 XSS

- 编号：`XSS-002`
- 类别：`xss`
- CWE：`CWE-79`
- 入口身份：可自助注册的用户
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

附件文件名经上传接口原样保存，之后在 ylinux_text_filter 处理帖子正文的 [A:id]/[i:id] 引用时被直接拼进 <a>/<img> 标签（无任何 HTML 转义），生成结果存为 body_html 并以 |safe 渲染，构成第二条存储型 XSS 链路。

**触发条件。** 登录用户上传一个文件名包含引号/尖括号的附件，再发布引用该附件的帖子正文（[附件:ID]、[img:ID] 语法）。

**数据流。** 来源：上传文件名 f.name（app/ydata/views.py:86 存入 Attachment.name；登录用户 POST /ydata/uploadsf/<id>/）→ 中间：帖子正文包含 [A:id]/[i:id] 引用，Post.save() 调 ylinux_text_filter（app/ydata/models.py:408 把 a.name 直接拼进 <a> 标签，444 行把 img.name 拼进 <img alt>，均无转义），随后 Markdown 无 safe_mode 直通 → 危险点：body_html 经 |safe 输出（app/wiki/utils.py:18 等）。入口身份：任何注册用户（可自助注册）。

**影响。** 攻击者上传文件名为 `"><script>…</script>` 的附件并在帖子中引用 [A:id]（或 [i:id]），附件名被原样拼入生成的 HTML，对所有浏览者形成存储型 XSS（可窃取无 HttpOnly 的会话 Cookie、接管账户）。

**修复。** 在 ylinux_text_filter 中对 a.name / img.name 使用 django.utils.html.escape 转义；上传时对文件名做严格白名单清洗；对最终 HTML 统一做白名单净化。

**复核员指出的最弱一环。** 最弱一环是“文件名是否会被运行时框架清洗掉尖括号/引号”——即使 Django 对 UploadedFile.name 做 os.path.basename，也只剥路径分隔符；不含 `/` 的 payload（如 `x"><img src=y onerror=alert(1)>`）完整保留，而拼接点在 <a> 文本位和 <img alt> 属性位，引号/尖括号足以注入。我核实了 models.py:407-408 与 443-444 确为 % 直接拼接 a.name/img.name，无任何 escape。

**判定历史。**

- 复核员同意：核对：上传视图 ydata/views.py:31-32 有 @login_required，78/86 行（及 73 行去重分支）把 f.name 原样存入 Attachment.name；ylinux_text_filter 在 Post.save(markup='none') 与 Topic.save_file 中均会执行（models.py:260、200→457），生成的 <a>/<img> HTML 进入 body_html 后经 |safe 输出（wiki/utils.py:18）。攻击者自助注册→上传恶意文件名附件→发帖引用 [A:id]，对所有浏览者存储型 XSS，链路闭合。high 合理。（最弱一环：最弱一环是“文件名是否会被运行时框架清洗掉尖括号/引号”——即使 Django 对 UploadedFile.name 做 os.path.basename，也只剥路径分隔符；不含 `/` 的 payload（如 `x"><img src=y onerror=alert(1)>`）完整保留，而拼接点在 <a> 文本位和 <img alt> 属性位，引号/尖括号足以注入。我核实了 models.py:407-408 与 443-444 确为 % 直接拼接 a.name/img.name，无任何 escape。）

**证据。**

`app/ydata/views.py:86-86`

```
        attachment = Attachment(user=req.user, name=f.name, path=local_name, size=f.size, hash=fhash)
```

`app/ydata/models.py:407-408`

```
                    a = Attachment.objects.get(pk=id)
                    place_html = u'<a href="%s" target="_blank">%s</a>' % (a.get_absolute_url(), a.name)
```

`app/ydata/models.py:443-444`

```
                    img = Attachment.objects.get(pk=id)
                    place_html = u'<img src="%s" alt="%s"/>' % (img.get_absolute_durl(), img.name)
```

`app/wiki/utils.py:18-18`

```
<p>{{ post.body_html|safe }}</p>
```

<a id="finding-access-001"></a>

### [MEDIUM] editPostAJAX 缺少属主校验：登录用户可篡改任意他人帖子

- 编号：`ACCESS-001`
- 类别：`access_control`
- CWE：`CWE-639`
- 入口身份：可自助注册的用户
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

editPostAJAX 视图只有登录要求而没有属主校验，任何登录用户都可以按 postID 覆盖修改他人的帖子正文（水平越权，IDOR）。

**触发条件。** 登录后 POST /wiki/post/<任意postID>/editAJAX/ 提交 body 即可覆盖该帖子。

**数据流。** 来源：POST body（app/wiki/views.py:456 `post_body = request.POST.get('body', None)`）→ 中间：editPostAJAX 用 URL 中的 postID 直接 get_object_or_404(Post, pk=postID)（451 行），仅 @login_required（447 行），没有 del_post 那样的 `post.user != request.user` 属主校验（272-280 行）→ 危险点：459-460 行任意覆盖 post.body 并 save()（重新渲染 HTML 入库）。入口身份：任何登录用户（注册开放）。

**影响。** 任意登录用户可以修改（覆盖）任何人的帖子内容，包括管理员或他人主题下的回帖；由于 Post.save() 会按 markup 重新渲染 HTML，还能借机向他人帖子注入脚本（结合 XSS-001）。

**修复。** 在 editPostAJAX 中校验 post.user == request.user（或具备相应权限），与 del_post 保持一致的属主检查。

**复核员指出的最弱一环。** 最弱一环是“是否存在审计员漏看的属主/权限校验”。我把 editPostAJAX 全文（wiki/views.py:447-467）读完：只有 @login_required，get_object_or_404 后直接 post.body=post_body; post.save()，没有任何 post.user 判断；对比同文件 del_post(277-278) 明确有 `post.user != request.user` 检查，证明属主校验模式存在而该视图缺失。

**判定历史。**

- 复核员同意：水平越权（IDOR）成立：任意登录用户 POST /wiki/post/<id>/editAJAX/ 即可覆盖他人帖子，且 save() 重渲染 HTML（markup='none' 分支无 safe_mode），可借 XSS-001 把脚本写进他人帖子。入口为开放注册登录用户。medium 合理（需登录、限于改帖不删帖）。（最弱一环：最弱一环是“是否存在审计员漏看的属主/权限校验”。我把 editPostAJAX 全文（wiki/views.py:447-467）读完：只有 @login_required，get_object_or_404 后直接 post.body=post_body; post.save()，没有任何 post.user 判断；对比同文件 del_post(277-278) 明确有 `post.user != request.user` 检查，证明属主校验模式存在而该视图缺失。）

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

`app/wiki/views.py:277-278`

```
    if post.user != request.user:
        return HttpResponseForbidden('<h1>您没有这个权限！</h1>')
```

<a id="finding-access-002"></a>

### [MEDIUM] /lab/update_post_profile 匿名可触发全站帖子批量改写

- 编号：`ACCESS-002`
- 类别：`access_control`
- CWE：`CWE-306`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

/lab/update_post_profile 是一个无需登录、任何 HTTP 方法即可触发的全站写操作端点，匿名用户可批量修改所有帖子的数据。

**触发条件。** 匿名 GET /lab/update_post_profile 即触发遍历全部 Post 并 save()。

**数据流。** 来源：GET 请求（无任何参数），路由 /lab/update_post_profile（app/ylab/urls.py:8）→ 危险点：app/ylab/views.py:37-48 无任何认证与请求方法校验，遍历 Post.objects.all() 修改 touser/updated 并逐条 save()（每条 save 都重新渲染 Markdown、写库）。入口身份：匿名。

**影响。** 任何匿名访问者用一个 GET 请求就能批量改写全站帖子的 touser/updated 字段并触发全量 HTML 重渲染与数据库写入，可破坏“回复对象”数据、抹掉时间戳，并可作为无认证的重负载操作被反复请求造成拒绝服务。

**修复。** 删除该实验性端点；如确需保留，加 @login_required/@permission_required 并限定 POST 方法，同时做限速。

**复核员指出的最弱一环。** 最弱一环是“端点是否真的匿名可触发任意方法”。核实 ylab/urls.py:8 路由存在，ylab/views.py:37-48 函数无任何装饰器、无 method 判断、无参数，GET 即遍历 Post.objects.all() 逐条改 touser/updated 并 save()（每次 save 还会重渲染 Markdown 写库）。

**判定历史。**

- 复核员同意：未认证的全站写操作端点确认。匿名单请求即触发全量帖子改写（touser 数据与时间戳被破坏），且 O(N) 渲染与写库可被反复请求用作 DoS。实验性端点裸露，medium 合理。（最弱一环：最弱一环是“端点是否真的匿名可触发任意方法”。核实 ylab/urls.py:8 路由存在，ylab/views.py:37-48 函数无任何装饰器、无 method 判断、无参数，GET 即遍历 Post.objects.all() 逐条改 touser/updated 并 save()（每次 save 还会重渲染 Markdown 写库）。）

**证据。**

`app/ylab/urls.py:8-8`

```
    url(r'^update_post_profile$', 'update_post_profile', name='update_post_profile'),
```

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

<a id="finding-access-004"></a>

### [MEDIUM] 版块组权限未在阅读路径强制：受限版块主题/帖子/附件匿名可读

- 编号：`ACCESS-004`
- 类别：`access_control`
- CWE：`CWE-862`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

版块组权限（Catalog.groups / has_access）只在发帖、回帖、编辑等写操作视图被调用，所有阅读路径（知识库/论坛的主题、版块、帖子、附件下载）都没有强制该校验；受限版块的内容对匿名用户完全可读，组权限模型在读取侧整体失效。

**触发条件。** 匿名访问受限版块的主题 URL（/wiki/topic/<id>/、/bbs/topic/<id>/）或其附件下载 URL（/ydata/attachment/<id>/download/，id 自增可遍历）。

**数据流。** 来源：匿名 GET 请求。版块组权限模型：Catalog.groups 字段（app/ydata/models.py:51-52，注释“只有在组中的用户可以访问此目录”）与 has_access 实现（app/ydata/models.py:91-101，有 groups 时非组成员/匿名返回 False）。但全仓库 has_access 仅出现在 4 个写操作视图：wiki/views.py:141（add_post）、172（add_topic）、192（edit_topic）、423（replayAJAX）——阅读路径全部没有调用：wiki/views.py:82-103 主题阅读（直接 Topic.objects.get 后渲染 topic.body_html/POST_HTML）、wiki/views.py:59-79 目录浏览、bbs/views.py:31-42 版块列表、bbs/views.py:45-56 论坛主题阅读，均无 has_access；附件下载 app/ydata/views.py:117-126 同样无任何校验（附件下载链接还经 ylinux_text_filter 渲染进帖子 body_html）。入口身份：匿名。

**影响。** 只要部署中任何版块配置了 groups 限制，该版块的主题正文、全部回帖与附件下载链接就对匿名用户完全公开（组权限模型在读取侧整体失效）；攻击者无需任何凭据即可按自增 id 遍历阅读受限内容与下载附件，写路径上的 has_access 校验形同虚设。

**修复。** 在全部阅读视图（wiki/bbs 的 topic/catalog/post、ajax_show_posts、附件 show/download、RSS/feed 等）统一强制 topic.catalog.has_access(request.user)；建议把该校验下沉为 Topic/Attachment 的公共访问控制辅助函数或中间件，避免逐视图遗漏。

**复核员指出的最弱一环。** 最弱一环是"组权限是否真在阅读路径整体失效，而非存在我漏看的全局强制"。我用 search_code 全仓搜索 has_access：仅 5 处匹配——定义（models.py:91）加 4 个调用点，且逐一读取上下文确认 4 个调用点全部是写操作视图（wiki/views.py:141 add_post 回复、172 ajax_add_topic、192 add_topic 发主题、423 replayAJAX 回帖）；逐一通读阅读视图：wiki topic(81-103)、wiki catalog(55-79)、wiki post(119-128)、ajax_topic(105-117)、bbs catalog(30-42)、bbs topic(44-56)、bbs post(58-67)、附件 show/download(101-105/117-149)，均无 @login_required、无 has_access。has_access 语义（models.py:93-100：有 groups 时匿名直接 False）确认组限制是真实的访问控制意图，admin/forms.py:147/172 证实组可通过管理表单实际配置到 Catalog。另注意到 data_flow 中 172/192 的视图名标注略有出入（实为 ajax_add_topic/add_topic 而非 add_topic/edit_topic），但不影响"仅写路径调用"的核心结论。

**判定历史。**

- 复核员同意：核对了全部 4 个证据位置及前后文：groups 字段定义（models.py:51-52，verbose_name 明确"只有在组中的用户可以访问此目录"）、has_access 实现（91-101）、wiki/bbs 阅读视图全文、附件端点全文、路由。结论成立：只要任何版块配置了 groups，其主题、回帖与附件对匿名用户完全可读，写路径上的校验形同虚设，属真实的授权缺失（CWE-862）。entry_role=anonymous 与代码相符。medium 定级合理：利用前提依赖部署方实际配置组限制，且影响限于机密性，不算偏高。（最弱一环：最弱一环是"组权限是否真在阅读路径整体失效，而非存在我漏看的全局强制"。我用 search_code 全仓搜索 has_access：仅 5 处匹配——定义（models.py:91）加 4 个调用点，且逐一读取上下文确认 4 个调用点全部是写操作视图（wiki/views.py:141 add_post 回复、172 ajax_add_topic、192 add_topic 发主题、423 replayAJAX 回帖）；逐一通读阅读视图：wiki topic(81-103)、wiki catalog(55-79)、wiki post(119-128)、ajax_topic(105-117)、bbs catalog(30-42)、bbs topic(44-56)、bbs post(58-67)、附件 show/download(101-105/117-149)，均无 @login_required、无 has_access。has_access 语义（models.py:93-100：有 groups 时匿名直接 False）确认组限制是真实的访问控制意图，admin/forms.py:147/172 证实组可通过管理表单实际配置到 Catalog。另注意到 data_flow 中 172/192 的视图名标注略有出入（实为 ajax_add_topic/add_topic 而非 add_topic/edit_topic），但不影响"仅写路径调用"的核心结论。）

**证据。**

`app/ydata/models.py:51-52`

```
    groups = models.ManyToManyField(Group, blank=True,
                verbose_name="只有在组中的用户可以访问此目录")
```

`app/ydata/models.py:91-101`

```
    def has_access(self, user):
        ''' 判断用户是否有权限，如果一个 Catalog 还未指定用户组，所有用户都有权限 '''
        if self.groups.count() > 0:
            if user.is_authenticated():
                try:
                    self.groups.get(user__pk=user.id)
                except Group.DoesNotExist:
                    return False
            else:
                return False
        return True
```

`app/wiki/views.py:81-90`

```
@render_to('wiki/topic.html')
def topic(request, id):

    try:
        topic = Topic.objects.get(pk=id)
    except Topic.DoesNotExist:
        url = reverse ('wiki:topic_not_exist', args=[id])
        return HttpResponseRedirect(url)

    parents = get_parents (Catalog, topic.catalog.id)
```

`app/bbs/views.py:44-56`

```
@render_to('bbs/topic.html')
def topic(request, id):

    try:
        topic = Topic.objects.get(pk=id)
    except Topic.DoesNotExist:
        url = reverse ('bbs:topic_not_exist', args=[id])
        return HttpResponseRedirect(url)

    parents = get_parents (Catalog, topic.catalog.id)
    posts = Post.objects.filter(topic=topic)

    return {'topic':topic, 'parents': parents, 'posts':posts}
```

<a id="finding-config-001"></a>

### [MEDIUM] DEBUG=True 随仓库提交，且媒体目录带目录索引对外服务

- 编号：`CONFIG-001`
- 类别：`config`
- CWE：`CWE-215`
- 入口身份：无请求入口
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

settings.py 提交了 DEBUG=True（无环境区分），并且在 DEBUG 下把 MEDIA_ROOT 以 show_indexes=True 挂到 /ymedia/ 由 Django 静态服务直接暴露。

**触发条件。** 该配置随代码部署即生效：任何错误请求会得到带堆栈/SQL 的调试页面；任何访问者可浏览 /ymedia/ 目录列表。

**影响。** 线上开启 DEBUG 会向访问者暴露完整堆栈、SQL 查询、本地变量与 settings 内容（含 SECRET_KEY）；同时 /ymedia/ 走 django.views.static.serve 且 show_indexes=True，任何人都可以浏览媒体目录列表和其中的上传文件。

**修复。** 部署环境将 DEBUG 设为 False；静态/媒体文件改由前置 Web 服务器提供，并关闭目录索引；为生产配置独立的 settings 模块。

**复核员指出的最弱一环。** 最弱一环是“DEBUG=True 是否真的会生效而非被覆盖”。settings.py 全文（1-177）无 local_settings 导入或环境覆盖逻辑，DEBUG=True 为仓库内硬编码默认值；urls.py:59-63 的 show_indexes 静态服务直接以 settings.DEBUG 为条件，配置即代码。

**判定历史。**

- 复核员同意：核实：settings.py:18 DEBUG=True、19 TEMPLATE_DEBUG 同源；urls.py:59-63 在 DEBUG 下把 MEDIA_ROOT 挂到 /ymedia/ 且 show_indexes=True。错误页暴露堆栈/SQL/settings、媒体目录可浏览枚举上传文件，二者均随配置生效。medium 合理。（最弱一环：最弱一环是“DEBUG=True 是否真的会生效而非被覆盖”。settings.py 全文（1-177）无 local_settings 导入或环境覆盖逻辑，DEBUG=True 为仓库内硬编码默认值；urls.py:59-63 的 show_indexes 静态服务直接以 settings.DEBUG 为条件，配置即代码。）

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

### [MEDIUM] SECRET_KEY 硬编码提交进公开仓库，会话签名与令牌生成失效

- 编号：`CONFIG-002`
- 类别：`config`
- CWE：`CWE-798`
- 入口身份：无请求入口
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

SECRET_KEY 硬编码在公开仓库中。该密钥被用于会话数据的 MD5 完整性签名（app/sessions/backends/base.py:89、app/sessions/models.py:18）和密码重置 token 生成（app/account/tokens.py:54），密钥公开后这些签名机制对任何能读到密钥的人都不再提供防篡改保证。

**触发条件。** 仓库中 settings.py:79 直接包含可用的生产 SECRET_KEY，且代码用 MD5(pickled + SECRET_KEY) 作为会话完整性校验（app/sessions/backends/base.py:89-95）。

**影响。** 任何拿到仓库的人都知道 SECRET_KEY，可绕过会话数据签名校验（配合其他弱点可伪造签名）、伪造依赖该密钥的令牌；密钥泄露也使 Django 自带的加密/签名设施全部失效。

**修复。** 将 SECRET_KEY 移出仓库，改用环境变量/密钥管理服务注入；对现有部署立即轮换密钥；签名改用 HMAC-SHA256 并保持密钥保密。

**复核员指出的最弱一环。** 最弱一环是“该密钥是否真被安全敏感路径使用”。核实 sessions/backends/base.py:89/95 与 sessions/models.py:18/63 均用 md5(pickled + settings.SECRET_KEY) 作为会话数据防篡改签名，密钥随仓库公开后任何读者都能为任意 pickle 生成合法签名，完整性保护确实失效。

**判定历史。**

- 复核员同意：核实：settings.py:79 密钥明文入库；sessions/backends/base.py:86-102 与 sessions/models.py:17-19/60-67 均以 md5(pickled+SECRET_KEY) 做会话数据完整性校验；account/tokens.py:54 也引用 SECRET_KEY（虽未被视图使用，见 L7）。密钥公开即签名机制失效，medium 合理（单独不直接可利用，需配合写入面）。（最弱一环：最弱一环是“该密钥是否真被安全敏感路径使用”。核实 sessions/backends/base.py:89/95 与 sessions/models.py:18/63 均用 md5(pickled + settings.SECRET_KEY) 作为会话数据防篡改签名，密钥随仓库公开后任何读者都能为任意 pickle 生成合法签名，完整性保护确实失效。）

**证据。**

`settings.py:78-79`

```
# Make this unique, and don't share it with anybody.
SECRET_KEY = 'c#0cz^i$lyr6*b*xe-t@0tqc_c3dnju=+c1lk^k7(r^7lhz$g@'
```

`app/sessions/backends/base.py:86-90`

```
    def encode(self, session_dict):
        "Returns the given session dictionary pickled and encoded as a string."
        pickled = pickle.dumps(session_dict, pickle.HIGHEST_PROTOCOL)
        pickled_md5 = md5_constructor(pickled + settings.SECRET_KEY).hexdigest()
        return base64.encodestring(pickled + pickled_md5)
```

<a id="finding-crypto-002"></a>

### [MEDIUM] 弱口令哈希（单轮 SHA1/MD5、弱盐）且登录接口无限速

- 编号：`CRYPTO-002`
- 类别：`crypto`
- CWE：`CWE-916`
- 入口身份：无请求入口
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

口令以单轮 SHA1（盐仅 5 字符且来自 random.random()）或单轮 MD5 存储，旧式无盐 MD5 也兼容；所有登录入口（网页、AJAX、XML-RPC）都没有暴力破解防护。

**触发条件。** 密码存储/校验在 User.set_password 与 get_hexdigest 中完成（app/account/models.py:228-234、62-66）；登录路径 /account/login/、/account/login/ajax/、XML-RPC has_auth 均无尝试限制。

**影响。** 数据库泄露时口令哈希可被 GPU 高速离线破解（单轮 SHA1/MD5、5 字符小盐）；同时所有登录入口（/account/login/、/account/login/ajax/、/admin/login/、XML-RPC has_auth）都无限速，可在线暴力猜测弱口令。

**修复。** 改用 PBKDF2/bcrypt/argon2 等自适应哈希（如 Django 的 make_password）；为所有登录入口增加限速、退避与锁定机制。

**复核员指出的最弱一环。** 最弱一环是“哈希强度描述是否与代码一致”。核实 account/models.py:62-65 确为单轮 md5/sha1，set_password(228-234) 盐 = sha1(random.random() 派生)[:5] 即 5 字符小盐，check_password(243-244) 还兼容无盐 md5。

**判定历史。**

- 复核员同意：核实：get_hexdigest（45-85 行窗口内 62-65）单轮 md5(salt+pw)/sha1(salt+pw)，另有 crypt 可选；set_password（228-234）盐仅 5 字符且源自 random.random()；check_password（243-244）兼容无盐 md5 旧格式。登录入口 login/ajax_login（views.py:227-235 无尝试限制）、XML-RPC has_auth 均无限速。库泄露后可 GPU 高速离线破解 + 在线暴破弱口令，medium 合理（属强度问题而非直接可利用漏洞）。（最弱一环：最弱一环是“哈希强度描述是否与代码一致”。核实 account/models.py:62-65 确为单轮 md5/sha1，set_password(228-234) 盐 = sha1(random.random() 派生)[:5] 即 5 字符小盐，check_password(243-244) 还兼容无盐 md5。）

**证据。**

`app/account/models.py:62-65`

```
    if algorithm == 'md5':
        return md5_constructor(salt + raw_password).hexdigest()
    elif algorithm == 'sha1':
        return sha_constructor(salt + raw_password).hexdigest()
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

### [MEDIUM] 全站缺少 CSRF 防护，Cookie 会话下的所有写操作可被跨站伪造

- 编号：`CSRF-001`
- 类别：`csrf`
- CWE：`CWE-352`
- 入口身份：可自助注册的用户
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

项目完全没有启用 CSRF 防护：MIDDLEWARE_CLASSES 中没有 CsrfViewMiddleware，模板与表单基本没有 csrf_token（唯一一处 {% csrf_token %} 也因缺少 CSRF 中间件/上下文处理器而无效），而认证完全依赖 Cookie 会话，因此所有登录态写操作都可被跨站请求伪造。

**触发条件。** 攻击者在自己页面放置自动提交的表单/请求指向 /wiki/topic/<id>/replayAJAX/、/wiki/topic/<id>/addpost/、/account/login/ 等端点，诱导已登录用户访问。

**影响。** 攻击者可以让已登录用户“替”其执行任何状态变更：发帖/回帖、上传附件、修改他人帖子（配合 ACCESS-001）、登录到攻击者账号（login CSRF 结合开放重定向窃取受害者后续输入）、以及管理员后台的所有写操作，因为后台端点也不校验请求方法（GET 即触发删除等操作）。

**修复。** 启用 django.middleware.csrf.CsrfViewMiddleware（并在模板中加 {% csrf_token %}）；写操作端点只接受 POST 并校验请求方法；登录视图也要做 CSRF 防护。

**复核员指出的最弱一环。** 最弱一环是“是否确实没有任何 CSRF 防护生效”。核实 settings.py:98-104 MIDDLEWARE_CLASSES 只有 CommonMiddleware 与自研 Session/Auth 中间件，无 CsrfViewMiddleware；模板上下文处理器（120-130）也无 csrf 处理器，个别模板即便有 {% csrf_token %} 也不会被校验。认证完全依赖 Cookie 会话（sessions/middleware.py:37-41）。

**判定历史。**

- 复核员同意：全站写操作（发帖 views.py:432-436、上传、登录等）在 Cookie 会话下无 token 校验，均可被跨站伪造；审计列举的影响与 ACCESS-001 的联动成立。XML-RPC 端点因逐请求带口令不受影响（lead L24 判断正确）。medium 合理。（最弱一环：最弱一环是“是否确实没有任何 CSRF 防护生效”。核实 settings.py:98-104 MIDDLEWARE_CLASSES 只有 CommonMiddleware 与自研 Session/Auth 中间件，无 CsrfViewMiddleware；模板上下文处理器（120-130）也无 csrf 处理器，个别模板即便有 {% csrf_token %} 也不会被校验。认证完全依赖 Cookie 会话（sessions/middleware.py:37-41）。）

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

`app/wiki/views.py:421-436`

```
    else:

        if not topic.catalog.has_access(request.user):
            return HttpResponse(u'<h1>您没有权限回复此帖！</h1>')

        # 如果 topic 已锁，则重定向到显示 topic
        if topic and topic.closed:
            return HttpResponse(u'主题已锁定，不可回复！')

        ip = ylinux_get_ip(request)

        post_body = request.POST.get("body", None)
        if len(post_body) < 2:
            return {'error': u'您的回复太短，至少2个字符！'}
        post = Post(topic = topic, user = request.user, user_ip = ip, markup = 'none', body = post_body, parent = parent_post)
        post.save()
```

<a id="finding-xss-003"></a>

### [MEDIUM] 注册/密码重置视图将 URL key 未转义回显导致反射型 XSS

- 编号：`XSS-003`
- 类别：`xss`
- CWE：`CWE-79`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

注册完成页与密码重置页在激活码不存在时把 URL 中的 key 未经 HTML 转义直接拼进响应体，构成匿名可达的反射型 XSS。

**触发条件。** 访问 /account/register/<img src=x onerror=alert(1)>/ 之类的不存在 key，即触发 403 页面回显。

**数据流。** 来源：URL 路径中的 key 参数（app/account/urls.py:8 `^register/(?P<key>.+)/$`、13 行 `^password/reset/(?P<key>.+)/$`）→ 危险点：account/views.py:102 与 208 把 key 用 % 直接拼进 HttpResponseForbidden 的 HTML（无 escape）返回。入口身份：匿名（无需登录）。

**影响。** 攻击者构造 /account/register/<script>…</script>/ 或 /account/password/reset/<script>…</script>/ 链接发给受害者，脚本在站点域内执行，可窃取会话 Cookie（Cookie 无 HttpOnly）或钓鱼。

**修复。** 对 key 使用 django.utils.html.escape（或模板输出）后再拼接；不要直接回显未转义的 URL 参数。

**复核员指出的最弱一环。** 最弱一环是“URL 里的尖括号能否真的进入 key 并到达回显”。我核实了 account/urls.py:8/13 使用 `(?P<key>.+)`，`.` 匹配除换行外任意字符，且 Django 在匹配前对路径做 URL 解码，`%3Cscript%3E` 会变成 `<script>` 进入 key；account/views.py:102 与 208 用 % 直接拼进 HttpResponseForbidden 的 HTML 字符串，全程无 escape，响应为 text/html。

**判定历史。**

- 复核员同意：两处回显（register 与 password_reset 的 DoesNotExist 分支）均核实存在，匿名可达，构造不存在 key 的链接即触发反射型 XSS。结合 Cookie 无 HttpOnly 可窃会话。需受害者点击链接，medium 合理。（最弱一环：最弱一环是“URL 里的尖括号能否真的进入 key 并到达回显”。我核实了 account/urls.py:8/13 使用 `(?P<key>.+)`，`.` 匹配除换行外任意字符，且 Django 在匹配前对路径做 URL 解码，`%3Cscript%3E` 会变成 `<script>` 进入 key；account/views.py:102 与 208 用 % 直接拼进 HttpResponseForbidden 的 HTML 字符串，全程无 escape，响应为 text/html。）

**证据。**

`app/account/urls.py:8-8`

```
    url(r'^register/(?P<key>.+)/$', 'register', name='complete_register'),
```

`app/account/views.py:100-102`

```
        register = Register.objects.get(activation_key=key)
    except Register.DoesNotExist:
        return HttpResponseForbidden(u'<h1>错误的 Key ： %s </h1>' % key)
```

`app/account/views.py:205-208`

```
    try:
        register = Register.objects.get(activation_key=key)
    except Register.DoesNotExist:
        return HttpResponseForbidden(u'<h1>错误的 Key ： %s </h1>' % key)
```

<a id="finding-access-003"></a>

### [LOW] 附件查看/下载端点无访问控制（权限模型不一致的加固项）

- 编号：`ACCESS-003`
- 类别：`access_control`
- CWE：`CWE-639`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

附件查看/下载端点无任何登录与权限校验，与写路径上的版块权限模型不一致（加固项）。经复核核实：主题阅读路径同样未强制 Catalog.has_access，附件端点并未绕过一条实际生效的阅读保护，独立影响限于未引用附件的元数据暴露与下载计数副作用，故按复核意见降为 low。

**触发条件。** 匿名 GET /ydata/attachment/<id>/ 或 /ydata/attachment/<id>/download/（id 自增可遍历）。

**数据流。** 来源：URL 中自增的附件 id（app/ydata/urls.py:7、9）→ 危险点：app/ydata/views.py:104 show_attachment（101-105 行无任何装饰器）与 119-126 行 download_attachment（无装饰器，open(a.get_absolute_path()) 返回文件内容）直接按 pk 取附件，无登录与权限校验。注意：经核实，主题阅读路径同样未强制 Catalog.has_access（见 ACCESS-004），因此本端点并未绕过一条实际生效的阅读保护；其独立暴露面仅为：未被任何帖子引用的附件的元数据（名称/上传者/大小/引用与下载计数）、download 端点的 dtimes 写副作用，以及与写路径权限模型不一致的问题。入口身份：匿名。

**影响。** 匿名攻击者可遍历附件 id 查看/下载未被帖子引用的附件及其元数据（上传者、大小、下载次数等），download 端点还有匿名触发的 dtimes 写副作用；权限模型不一致给未来的权限收紧留下绕过入口。鉴于阅读路径整体未强制 has_access（ACCESS-004），本项的实际影响有限，按复核意见定为 low。

**修复。** 在 show_attachment/download_attachment 中复用与主题侧一致的访问校验（attachment.topic.catalog.has_access(request.user)），与 ACCESS-004 的阅读路径修复一并完成。

**复核员指出的最弱一环。** 最弱一环是"降级后的影响表述是否与代码事实一致"——上一轮 dispute 指出其原始影响声明（绕过主题侧 has_access 泄露私有版块内容）不成立，因为阅读路径根本不强制 has_access；本轮需核实改写后的表述是否如实。我核实了：show_attachment（ydata/views.py:101-105，仅 @render_to）与 download_attachment（117-149，完全无装饰器，a.dtimes += 1 后 open 文件返回内容）确实无登录与权限校验；ydata/urls.py:7,9 路由存在且 id 为 \d+ 可枚举；Attachment.topic FK（models.py:351）存在使修复可行。改写后的 finding 把独立影响限定为"未被帖子引用的附件的查看/下载、dtimes 写副作用、与写路径权限模型不一致"，并明确交叉引用 ACCESS-004 承认阅读路径整体未强制 has_access——该表述与代码事实一致，无夸大。

**异议或降级说明。** 机制部分属实：show_attachment（ydata/views.py:101-105，仅 @render_to）与 download_attachment（117-149，无任何装饰器）确实无登录与权限校验，urls.py:30 → ydata/urls.py:7,9 挂载，主键自增可枚举，Catalog.has_access（models.py:91-101）权限模型存在且写路径（wiki/views.py:141/172/192/423）有校验，模型不一致真实存在，Attachment.topic FK（models.py:351）也使修复可行。但 finding 的核心影响声明"主题阅读有版块权限校验……绕过主题侧 has_access 造成私有内容泄露"不成立：阅读路径全站无 has_access 强制，受限版块内容（含附件下载链接）本就匿名可读，附件端点的边际暴露仅剩未被帖子引用的附件元数据与下载计数副作用。medium 定级明显偏高，建议降为 low，作为权限模型不一致/加固项保留；若审计员认为真正的风险是"整个阅读路径缺失组权限强制"，那应是另一条不同范围的 finding，而非本条。（建议严重性：low）

**判定历史。**

- 复核员否决：机制部分属实：show_attachment（ydata/views.py:101-105，仅 @render_to）与 download_attachment（117-149，无任何装饰器）确实无登录与权限校验，urls.py:30 → ydata/urls.py:7,9 挂载，主键自增可枚举，Catalog.has_access（models.py:91-101）权限模型存在且写路径（wiki/views.py:141/172/192/423）有校验，模型不一致真实存在，Attachment.topic FK（models.py:351）也使修复可行。但 finding 的核心影响声明"主题阅读有版块权限校验……绕过主题侧 has_access 造成私有内容泄露"不成立：阅读路径全站无 has_access 强制，受限版块内容（含附件下载链接）本就匿名可读，附件端点的边际暴露仅剩未被帖子引用的附件元数据与下载计数副作用。medium 定级明显偏高，建议降为 low，作为权限模型不一致/加固项保留；若审计员认为真正的风险是"整个阅读路径缺失组权限强制"，那应是另一条不同范围的 finding，而非本条。（建议严重性：low）
- 状态 disputed → confirmed
- 复核员同意：逐项核对了证据：ydata/views.py:30-150 全文（upload 有 @login_required 作对照，show/download 无任何校验）、ydata/urls.py 路由挂载、models.py:348-375 附件模型与 get_absolute_path。机制（匿名可枚举访问附件元数据与内容、匿名触发 dtimes 写入）真实存在；考虑到 ACCESS-004 已覆盖"阅读路径整体缺失组权限"这一更大问题，本条作为低严重度的模型不一致/加固项保留，定级恰当。上一轮 dispute 意见已被完整采纳。（最弱一环：最弱一环是"降级后的影响表述是否与代码事实一致"——上一轮 dispute 指出其原始影响声明（绕过主题侧 has_access 泄露私有版块内容）不成立，因为阅读路径根本不强制 has_access；本轮需核实改写后的表述是否如实。我核实了：show_attachment（ydata/views.py:101-105，仅 @render_to）与 download_attachment（117-149，完全无装饰器，a.dtimes += 1 后 open 文件返回内容）确实无登录与权限校验；ydata/urls.py:7,9 路由存在且 id 为 \d+ 可枚举；Attachment.topic FK（models.py:351）存在使修复可行。改写后的 finding 把独立影响限定为"未被帖子引用的附件的查看/下载、dtimes 写副作用、与写路径权限模型不一致"，并明确交叉引用 ACCESS-004 承认阅读路径整体未强制 has_access——该表述与代码事实一致，无夸大。）

**证据。**

`app/ydata/views.py:101-105`

```
@render_to('ydata/attachment.html')
def show_attachment(req, id):
    ''' 显示指定 id 的附件信息 '''
    attachment = get_object_or_404(Attachment,pk=id)    
    return {'attachment': attachment}
```

`app/ydata/views.py:117-126`

```
def download_attachment(request, id):

    a = get_object_or_404(Attachment,pk=id)

    a.dtimes += 1
    a.save()

    print a.get_absolute_path()
    f = open(a.get_absolute_path())
    response = HttpResponse(f.read())
```

<a id="finding-config-003"></a>

### [LOW] 数据库口令 '123456' 明文提交进仓库

- 编号：`CONFIG-003`
- 类别：`config`
- CWE：`CWE-798`
- 入口身份：无请求入口
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

settings.py 中提交了数据库口令 '123456'（USER='ylinux'）。虽然当前 ENGINE 是 sqlite3 不校验该口令，但配置注释明确演示了切换 MySQL 的用法，属于随仓库泄露的数据库凭据。

**触发条件。** settings.py:46-49 同时给出 ENGINE/NAME/USER/PASSWORD；一旦 ENGINE 切换为 mysql 即成为真实的数据库凭据。

**影响。** 当前 ENGINE 为 sqlite3 时该口令不参与认证，实际影响有限；但这是进入仓库的明文数据库口令，一旦有人按注释切换为 MySQL（同一口令/用户名已就位），数据库即可被口令猜测或源码泄露直接攻破。

**修复。** 删除硬编码口令，通过环境变量或密钥管理注入；切换数据库引擎时强制使用强随机口令。

**复核员指出的最弱一环。** 最弱一环是“该口令当前是否生效”——核实 settings.py:42-53，ENGINE 为 sqlite3，口令字段对 sqlite 无认证作用，所以现实影响确实有限；审计也如实标注了这一点并定 low，无夸大。

**判定历史。**

- 复核员同意：核实：settings.py:42-53 ENGINE 当前为 sqlite3，USER/PASSWORD 不参与认证，属随仓库泄露的明文凭据，切 MySQL（45 行注释演示）即成为真实凭据。影响潜在且需配置变更，low 合理。（最弱一环：最弱一环是“该口令当前是否生效”——核实 settings.py:42-53，ENGINE 为 sqlite3，口令字段对 sqlite 无认证作用，所以现实影响确实有限；审计也如实标注了这一点并定 low，无夸大。）

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

<a id="finding-email-001"></a>

### [LOW] 联系表单可被匿名滥用为任意收件人的邮件中继

- 编号：`EMAIL-001`
- 类别：`other`
- CWE：`CWE-20`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

联系表单把用户填写的 sender 同时当作发件人和收件人发送邮件，无验证码与限速，可被匿名滥用为开放邮件中继。

**触发条件。** 匿名 POST /contact/，sender 填任意目标邮箱，subject/message 任意内容。

**影响。** 匿名攻击者可把 sender 填成任意邮箱并循环提交，使站点邮件服务器成为垃圾邮件中继（收件人、主题、正文、发件人全部可控），浪费配额并污染站点域名信誉。

**修复。** 收件人固定为站点地址，不要把 sender 加入收件人列表；对表单加验证码/速率限制；对提交内容做长度限制。

**复核员指出的最弱一环。** 最弱一环是“sender 是否真为用户可控的合法邮箱并被加入收件人”。核实 ContactForm（home/forms.py:8）sender 是 EmailField，只要求格式合法；views.py:42-46 把它 append 进 recipients 并作为发件人发出。匿名、无验证码、无限速确认。

**判定历史。**

- 复核员同意：核实：home/views.py:34-48 无任何认证/验证码/限速，sender 进入 recipients 并作为发件人 send_mail；home/forms.py:8 sender=EmailField 只校验格式合法，攻击者可填任意目标邮箱，主题/正文全部可控。每次请求可向一个任意地址中继一封邮件，滥用消耗配额、污染域信誉。low 合理。（最弱一环：最弱一环是“sender 是否真为用户可控的合法邮箱并被加入收件人”。核实 ContactForm（home/forms.py:8）sender 是 EmailField，只要求格式合法；views.py:42-46 把它 append 进 recipients 并作为发件人发出。匿名、无验证码、无限速确认。）

**证据。**

`app/home/views.py:34-48`

```
def contact(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            subject = form.cleaned_data['subject']
            message = form.cleaned_data['message']
            sender = form.cleaned_data['sender']

            recipients = ['ylinux.admin@gmail.com','lijian.gnu@gmail.com',]
            recipients.append(sender)

            from django.core.mail import send_mail
            send_mail (subject,message,sender,recipients)
```

<a id="finding-redirect-001"></a>

### [LOW] 登录/退出 next 参数未校验导致开放重定向

- 编号：`REDIRECT-001`
- 类别：`redirect`
- CWE：`CWE-601`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

登录与退出视图把用户可控的 next 参数作为重定向目标，未做站内地址校验，构成开放重定向。

**触发条件。** 访问 /account/login?next=//evil.com 完成登录，或直接访问 /account/logout?next=//evil.com。

**数据流。** 来源：GET 参数 next（app/account/views.py:44 存 session、58 行 logout 直接读取）→ 危险点：38 行 HttpResponseRedirect(request.session.get('login_redirect_url','/') or '/')、60 行 HttpResponseRedirect(previous_url or '/')，未用 is_safe_url 校验目标为站内地址。入口身份：匿名（登录前设置 next，登录成功后跳转；logout 任何人可带 next）。

**影响。** 攻击者可用 /account/login?next=//evil.com 构造链接，受害者登录成功后（或点击 /account/logout?next=//evil.com 后）被带到钓鱼站点，常用于配合钓鱼页窃取凭据。

**修复。** 跳转前用 django.utils.http.is_safe_url（或自定义白名单）校验 next 为站内相对地址；优先使用 reverse() 生成的固定跳转目标。

**复核员指出的最弱一环。** 最弱一环是“跳转目标是否真为用户可控且无校验”。核实 account/views.py:38 跳转目标来自 session['login_redirect_url']，而该值在 44 行由 request.GET.get('next') 直接写入；logout 的 58-60 行更直接，GET next 原样进 HttpResponseRedirect。两处均无 is_safe_url。

**判定历史。**

- 复核员同意：核实：account/views.py:42-45（GET 分支把 next 存入 session）、38（登录成功后直接 HttpResponseRedirect 到 session 值）、55-60（logout 读 GET next 直接跳转），全程无 is_safe_url/白名单校验。`//evil.com` 类协议相对地址会被浏览器当作跨域跳转。钓鱼辅助价值为主，low 合理。（最弱一环：最弱一环是“跳转目标是否真为用户可控且无校验”。核实 account/views.py:38 跳转目标来自 session['login_redirect_url']，而该值在 44 行由 request.GET.get('next') 直接写入；logout 的 58-60 行更直接，GET next 原样进 HttpResponseRedirect。两处均无 is_safe_url。）

**证据。**

`app/account/views.py:42-45`

```
    else:
        # 形如 "http://127.0.0.1:8000/account/login?next=/admin/" 的 url 可以得到 next 值
        request.session['login_redirect_url'] = request.GET.get('next')
        form = AuthenticationForm(request)
```

`app/account/views.py:58-60`

```
    previous_url = request.GET.get('next')
    logout(request)
    return HttpResponseRedirect(previous_url or '/')
```

<a id="finding-xss-004"></a>

### [LOW] 上传响应将文件名未转义拼入 HTML/JS 导致 self-XSS

- 编号：`XSS-004`
- 类别：`xss`
- CWE：`CWE-79`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

两个上传接口都把用户提供的文件名未经转义地拼进返回的 HTML/JavaScript 片段，形成针对上传者本人的反射型 XSS（self-XSS）。

**触发条件。** 上传 filename 为 `<script>alert(1)</script>` 之类的文件到 /lab/uploadsf（匿名）或 /ydata/uploadsf/<id>/（登录），响应中的脚本在自身页面执行。

**数据流。** 来源：上传文件名 attachment.name / f.name（app/ylab/views.py:31 req.FILES.values()[0]，匿名；app/ydata/views.py:40，登录）→ 危险点：app/ylab/views.py:32-34 把文件名原样拼进 HTML/JS 片段返回；app/ydata/views.py:91-95 拼进 window.parent.AfterSubmit(...) 的 JS 调用返回。均为 text/html 响应且无转义。受害者仅为提交上传的本人（self-XSS）。

**影响。** 文件名中的 HTML/JS 会在上传者的会话上下文里执行（self-XSS）。作为配合手段，可用来绕过某些浏览器 XSS 过滤器或在社会工程场景中扩大攻击面；影响有限。

**修复。** 对 attachment.name 做 HTML/JS 转义（json.dumps 或 escape）后再拼接返回；ylab 的实验上传端点建议直接移除或加认证。

**复核员指出的最弱一环。** 最弱一环是“响应是否真为可执行 HTML/JS 上下文且文件名未被框架清洗”。核实 ylab/views.py:31-34 与 ydata/views.py:91-95：HttpResponse 默认 text/html，文件名直接 % 拼进 <script> 片段；即便 Django 对 name 做 basename，也只剥路径分隔符，`");alert(1);//` 或 `<img src=x onerror=...>`（不含 `/`）原样保留。

**判定历史。**

- 复核员同意：核实：ylab/views.py:24-34 匿名上传端点把 attachment.name 与 innerHTML 两级拼接进 text/html 响应；ydata/views.py:91-95（登录）把 attachment.name 拼进 JS 字符串参数。均无转义，文件名中引号/尖括号（basename 只去 `/`，不去 `<>"`）可破出字符串/标签。执行上下文为上传者本人页面（self-XSS），配合面有限，low 合理。（最弱一环：最弱一环是“响应是否真为可执行 HTML/JS 上下文且文件名未被框架清洗”。核实 ylab/views.py:31-34 与 ydata/views.py:91-95：HttpResponse 默认 text/html，文件名直接 % 拼进 <script> 片段；即便 Django 对 name 做 basename，也只剥路径分隔符，`");alert(1);//` 或 `<img src=x onerror=...>`（不含 `/`）原样保留。）

**证据。**

`app/ylab/views.py:31-34`

```
    attachment = req.FILES.values()[0]
    innerHTML = u'<span><a href="%s">%s</a>， %s， <a href="%s/delete">删除</a></span>' % (url, attachment.name, attachment.size, url)
    r = u'<script type="text/javascript">window.parent.AfterSubmit(%s);</script>' % innerHTML
    return HttpResponse(r)
```

`app/ydata/views.py:91-95`

```
    r = u'<script type="text/javascript">window.parent.AfterSubmit("%s","%s","%s","%s","%s");</script>'\
        % (attachment.id, attachment.name,
           reverse ('ydata:show_attachment', args=[attachment.id]),
           reverse ('ydata:download_attachment', args=[attachment.id]),
           notes)
```

## 需要再确认的问题

<a id="finding-deser-001"></a>

### [LOW] 会话数据 pickle 反序列化 + 公开 SECRET_KEY 的 MD5 签名（潜在 RCE）

- 编号：`DESER-001`
- 类别：`deserialization`
- CWE：`CWE-502`
- 入口身份：无请求入口
- 置信度：`medium`
- 状态：`needs_review`
- 复核员：同意

会话数据使用 pickle 反序列化，完整性只依赖 MD5(pickled + SECRET_KEY)，而 SECRET_KEY 已随仓库公开（CONFIG-002）。会话数据存于服务端，暂未发现可直接控制会话行的请求入口，故标为待复核。

**触发条件。** 无直接请求入口：需要能写入会话存储（数据库/会话文件）的前置条件；SECRET_KEY 公开使签名可被任意伪造。

**影响。** pickle.loads 可直接执行任意代码。会话数据存储在服务端（DB/文件），当前没有发现能直接写入会话行的请求入口，因此无法仅靠 HTTP 触发；但一旦攻击者获得任何数据库写权限（或站点存在其他注入），伪造的会话行即可获得远程代码执行。

**修复。** 将会话序列化改为 JSON；如必须保留二进制格式，用 HMAC-SHA256（密钥从环境注入且保密）做防篡改签名；妥善保管 SECRET_KEY。

**复核员指出的最弱一环。** 最弱一环是“是否存在可直接控制会话数据入口”——若没有，RCE 就只是潜在风险。我核实了：会话中间件仅从 Cookie 读取 session_key（middleware.py），数据经服务端后端（db/file/cache 系）存取，decode 的输入是服务端存储的 session_data（sessions/models.py:60-67 与 base.py:92-102）；仓库未发现任何 HTTP 入口能写入会话行。finding 本身也如实声明“暂未发现可直接控制会话行的请求入口”并定 low，无夸大。

**判定历史。**

- 复核员同意：核实：base.py:86-102（80-120 窗口）encode/decode 机制与描述一致；sessions/models.py:60-67 同逻辑作用于 DB 行。全仓搜索 SESSION_ENGINE 仅 middleware.py:10 一处引用、仓库未设置（走部署/全局默认），所有自带后端（db/cached_db/file/cache）数据均在服务端；middleware 只从 Cookie 取 session_key，客户端不提交会话数据本身。故无纯 HTTP 触发路径，属潜在风险 + 公开密钥使签名可伪造的加固项，finding 如实标注 needs_review 与低严重度，结论恰当。（最弱一环：最弱一环是“是否存在可直接控制会话数据入口”——若没有，RCE 就只是潜在风险。我核实了：会话中间件仅从 Cookie 读取 session_key（middleware.py），数据经服务端后端（db/file/cache 系）存取，decode 的输入是服务端存储的 session_data（sessions/models.py:60-67 与 base.py:92-102）；仓库未发现任何 HTTP 入口能写入会话行。finding 本身也如实声明“暂未发现可直接控制会话行的请求入口”并定 low，无夸大。）

**证据。**

`app/sessions/backends/base.py:86-90`

```
    def encode(self, session_dict):
        "Returns the given session dictionary pickled and encoded as a string."
        pickled = pickle.dumps(session_dict, pickle.HIGHEST_PROTOCOL)
        pickled_md5 = md5_constructor(pickled + settings.SECRET_KEY).hexdigest()
        return base64.encodestring(pickled + pickled_md5)
```

`app/sessions/backends/base.py:92-102`

```
    def decode(self, session_data):
        encoded_data = base64.decodestring(session_data)
        pickled, tamper_check = encoded_data[:-32], encoded_data[-32:]
        if md5_constructor(pickled + settings.SECRET_KEY).hexdigest() != tamper_check:
            raise SuspiciousOperation("User tampered with session cookie.")
        try:
            return pickle.loads(pickled)
        # Unpickling can cause a variety of exceptions. If something happens,
        # just return an empty dictionary (an empty session).
        except:
            return {}
```

<a id="finding-file-001"></a>

### [LOW] 附件上传文件名直接拼入保存路径（依赖框架 basename 清洗的纵深防御项）

- 编号：`FILE-001`
- 类别：`file_access`
- CWE：`CWE-22`
- 入口身份：可自助注册的用户
- 置信度：`medium`
- 状态：`needs_review`
- 复核员：同意

附件上传把用户提供的文件名直接拼入服务器保存路径，应用代码自身未做目录穿越防护。经复核讨论：代码所依赖的 req.FILES/chunks 上传 API 对应的 Django 版本会在 UploadedFile 上对文件名做 os.path.basename 清洗，目录穿越在受支持运行时上大概率不可达（框架源码不在本仓库、无法就地证实），故按复核意见从 medium 降为 low，保留为纵深防御/加固项。

**触发条件。** 构造 multipart 上传，将单文件字段的 filename 设置为含 ../ 的值，POST 到 /ydata/uploadsf/<id>/；是否可利用取决于运行时 Django 对 UploadedFile.name 的清洗行为。

**数据流。** 来源：上传文件名 f.name（app/ydata/views.py:40 req.FILES['single_file']，登录用户 POST /ydata/uploadsf/<id>/）→ 中间：78 行把 f.name 原样拼进 local_name，79-81 行 os.path.join(MEDIA_ROOT, ATTACHMENT_UPLOAD_TO, local_name) → 危险点：82 行 open(save_path, 'wb+') 写盘。应用自身没有做 basename/白名单清洗。可达性争议：复核指出 req.FILES/chunks API 对应的 Django 版本（≥1.0）在 UploadedFile 的 name 上做 os.path.basename 清洗，POSIX 下 `/` 穿越会被剥除；但框架源码不在本仓库内，无法在此仓库中静态证实所部署 Django 版本的行为，因此保留为低严重度的纵深防御项。

**影响。** 如果运行时 Django 版本不对上传文件名做路径分隔符清洗，攻击者可用含 ../ 的文件名把文件写到附件目录之外。复核员指出：使用 req.FILES['single_file']/chunks() 的 Django 版本（≥1.0）会在 UploadedFile 层对 name 做 basename 清洗，因此目录穿越在常见运行时上不可达；此项价值主要为纵深防御——应用自身不应依赖框架细节来保证路径安全。

**修复。** 在保存前对文件名做 os.path.basename 与字符白名单清洗（仅保留 [A-Za-z0-9._-]），并用 os.path.realpath 校验最终路径仍位于附件目录内，不依赖框架对文件名的清洗行为。

**复核员指出的最弱一环。** 最弱一环仍是"是否存在能运行此代码又不做 basename 清洗的运行时"。我核实了 app/ydata/views.py:31-40：视图使用 @login_required、req.FILES['single_file'] 和 f.chunks()，这套上传 API 仅存在于 Django ≥1.0，而这些版本的 UploadedFile._set_name 一律执行 os.path.basename——不存在"能运行此代码又不清洗文件名"的受支持运行时，POSIX 下 `/` 被剥除、Windows 下由 ntpath.basename 处理反斜杠。审计员已采纳上轮 dispute，将可利用性结论改为"受支持运行时上大概率不可达"并降为 low 的纵深防御项，该表述与代码事实一致。

**异议或降级说明。** 核实证据 ydata/views.py:78-84 拼接属实且应用自身未做 basename/白名单，这一点无异议。但可利用性结论不成立：req.FILES/chunks 这套上传 API 仅存在于 Django≥1.0，而这些版本的 UploadedFile._set_name 一律执行 os.path.basename 清洗，不存在“能运行此代码又不清洗文件名”的 Django 版本；所谓“无法静态确认”其实可以确认。POSIX 下含 `/` 的穿越名被剥成尾段，Windows 反斜杠在 POSIX 不构成穿越、在 Windows 由 ntpath.basename 处理。目录穿越在任何受支持运行时上都不可达，medium 的风险定级不成立；该条剩余价值仅为纵深防御建议，建议降为 low。（建议严重性：low）

**判定历史。**

- 复核员否决：核实证据 ydata/views.py:78-84 拼接属实且应用自身未做 basename/白名单，这一点无异议。但可利用性结论不成立：req.FILES/chunks 这套上传 API 仅存在于 Django≥1.0，而这些版本的 UploadedFile._set_name 一律执行 os.path.basename 清洗，不存在“能运行此代码又不清洗文件名”的 Django 版本；所谓“无法静态确认”其实可以确认。POSIX 下含 `/` 的穿越名被剥成尾段，Windows 反斜杠在 POSIX 不构成穿越、在 Windows 由 ntpath.basename 处理。目录穿越在任何受支持运行时上都不可达，medium 的风险定级不成立；该条剩余价值仅为纵深防御建议，建议降为 low。（建议严重性：low）
- 状态 disputed → needs_review
- 复核员同意：核实证据 app/ydata/views.py:78-84：local_name 确实直接拼接 f.name，os.path.join 后 open(save_path,'wb+') 写盘，应用自身无 basename/白名单，引用准确；路由 ydata/urls.py:6 挂载 uploadsf，视图有 @login_required（31 行）与 POST 限定（37-38），entry_role=registered_open 属实。finding 已如实标注框架层 basename 清洗使目录穿越不可达，仅作为不依赖框架行为的加固建议保留，low 定级与"纵深防御"定位相符，无夸大，同意。（最弱一环：最弱一环仍是"是否存在能运行此代码又不做 basename 清洗的运行时"。我核实了 app/ydata/views.py:31-40：视图使用 @login_required、req.FILES['single_file'] 和 f.chunks()，这套上传 API 仅存在于 Django ≥1.0，而这些版本的 UploadedFile._set_name 一律执行 os.path.basename——不存在"能运行此代码又不清洗文件名"的受支持运行时，POSIX 下 `/` 被剥除、Windows 下由 ntpath.basename 处理反斜杠。审计员已采纳上轮 dispute，将可利用性结论改为"受支持运行时上大概率不可达"并降为 low 的纵深防御项，该表述与代码事实一致。）

**证据。**

`app/ydata/views.py:78-84`

```
        local_name = str(id) + '-' + str(req.user.id) + '-' + f.name
        save_path = os.path.join(settings.MEDIA_ROOT,
                                 ydata_settings.ATTACHMENT_UPLOAD_TO,
                                 local_name)
        save_file = open(save_path, 'wb+')
        for chunk in f.chunks():
            save_file.write(chunk)
```

## 复核员否决、尚未改判的问题

无。

## 已排除的可疑点

无。

## 未完成判断的候选

无。

## 范围

覆盖了根 urls.py 与全部 8 个 app（account/sessions/admin/home/wiki/blog/bbs/me/ydata/ylab）的 URL 配置和 views.py 入口、account 与 admin 的 forms、自定义会话中间件及全部后端（db/cache/file/base）、lib/django_xmlrpc 与 lib/ylinux_xmlrpc、vendored Python-Markdown 2.0.3 的 safe_mode 行为、以及全部模板中的 |safe/CSRF 落点；has_access 全仓库引用点（5 处）已逐一核对。未纳入：tests.py、未在本仓库内的 Django 框架源码（其默认值未作为结论依据）、静态资源与第三方前端库。

## 局限

纯静态审计，未运行应用。以下问题无法在本仓库内证实：1) FILE-001 目录穿越取决于运行时 Django 对 UploadedFile.name 的清洗（框架源码不在仓库内；复核指出该 API 对应的 Django 版本会做 basename 清洗，故按低严重度保留为纵深防御项）；2) DESER-001 pickle 反序列化当前没有可直接写会话存储的请求入口，需配合数据库写权限或其他注入才能触发；3) lib/ylinux_xmlrpc.new_media 因模块未导入 settings 会在写文件前抛 NameError，实际不可达；4) ACCESS-004 的实际影响取决于部署中是否有版块配置了 groups 限制（代码层缺陷明确：读路径无任何强制）；5) 无法验证线上部署是否已通过 Web 服务器层关闭 /ymedia/ 静态服务或覆盖 settings。

## 复核意见

本轮复核了两条 critic_verdict 为空的发现。ACCESS-003：重读 ydata/views.py:30-150 全文、ydata/urls.py、models.py:348-375，确认 show/download 附件端点无任何认证与权限校验、自增 id 可枚举、download 有匿名 dtimes 写副作用；审计员已采纳上一轮 dispute，将影响收缩为"未引用附件暴露 + 权限模型不一致"并定 low，表述与代码事实一致，agree。ACCESS-004：重读 models.py:40-120（groups 字段与 has_access 实现）、wiki/views.py:55-150/160-210/410-445、bbs/views.py:25-75，并用 search_code 全仓确认 has_access 仅在 4 个写操作视图被调用（141/172/192/423），所有阅读路径（wiki/bbs 主题、版块、帖子、附件）匿名可达且无该校验；admin/forms.py:147/172 证实组限制可实际配置，授权缺失真实，medium 定级合理，agree。唯一瑕疵：ACCESS-004 data_flow 中 172/192 行对应的视图名标注为 add_topic/edit_topic，实际为 ajax_add_topic/add_topic，属行号-名称对应小误差，不影响"has_access 仅出现在写路径"的核心结论。其余 16 条发现此前轮次已逐条复核并 agree，本轮未再重复打开；无新增缺口、无新增发现。仍存的保留意见：XSS-001 的实际可利用性依赖部署方是否真的用 Python-Markdown 2.0.3 这套旧库运行（lib/ 在仓库内，应为实际运行代码），此前已核实，无疑义。

## 复核缺口

- `G1`（已回应）遗漏：XML-RPC metaWeblog.newMediaObject（lib/ylinux_xmlrpc.py:105-127）是任意内容任意扩展名的文件上传——has_auth 只要求任意注册账号（无授权检查，同 AUTHZ-001），os.path.basename 只防穿越，不校验扩展名与内容，文件写入 MEDIA_ROOT/img/ 后在 DEBUG 下经 urls.py:59-63 的 django.views.static.serve 按猜测 MIME 同源提供；上传 .html/.svg 即获得站点域内的存储型脚本执行/任意内容托管。该向量与 XSS-002（附件名注入帖子 HTML）、FILE-001（路径穿越）、XSS-004（self-XSS）均不同源，审计未覆盖。
  - 审计员回应：已读 lib/ylinux_xmlrpc.py 全文核实：new_media（105-127 行）虽经 settings.py:170 注册为 metaWeblog.newMediaObject，但该模块导入段（1-15 行）从未 import settings，而 122-123 行直接引用 settings.MEDIA_ROOT/MEDIA_URL；search_code 确认全模块仅这两处出现 settings。因此调用该方法在写到磁盘之前（122 行先于 124 行 open(target_path,'w')）即抛 NameError，dispatcher 捕获后只返回 Fault，任意内容上传的文件写入实际上不可达，不成立为可利用漏洞，故不新增 finding。若将来补上该 import，将变成“任意注册用户同源上传任意扩展名内容”的问题，修复时应同时补授权校验与扩展名/内容白名单。
- `G2`（已回应）遗漏：附件对象级访问控制缺失。主题阅读有版块权限校验（app/wiki/views.py:141 `topic.catalog.has_access(request.user)`），但附件的 show/download 端点（app/ydata/urls.py:7,9 → app/ydata/views.py:101-105、117-149）既无登录要求也不校验所属版块的 groups 权限，id 自增可枚举；被组权限限制的“私有版块”附件可被匿名用户直接按 id 下载，与主题侧的权限模型不一致（IDOR 信息泄露）。该问题在 DEBUG=False 时依然存在，未被 CONFIG-001 的目录索引问题涵盖。
  - 审计员回应：已核实并新增 ACCESS-003（confirmed，medium，anonymous）：show_attachment（ydata/views.py:101-105）与 download_attachment（117-126）均无登录/权限校验，而附件所属主题受 Catalog.has_access 组权限保护（ydata/models.py:91-101，主题侧 wiki/views.py:141 调用该校验），自增 id 可枚举，匿名可下载受限版块附件，构成 IDOR 信息泄露；该问题在 DEBUG=False 时依然存在，与 CONFIG-001 的目录索引问题相互独立。
