# ylinux_old 应用安全审计报告

- 目标：`https://github.com/gwind/ylinux_old`，commit `8a7316deec88287d020eca21c38dad921b623ffc`
- 模型：审计员 `deepseek-v4-pro`，复核员 `kimi-k3`
- 时间：2026-10-21T10:55:11+08:00 → 2026-10-21T11:18:37+08:00
- 结论：确认 12 个问题，最高严重性为 critical。
- 统计：已确认 12，待再确认 1，已排除 1；引用核对 34 条，未通过 0 条

> 这次运行中途中断（原因见文末“运行警告”），复核没有做完，标“未复核”的条目只经过审计员判断。

## 发现总表

| 严重性 | 编号 | 问题 | 入口身份 | 状态 | 复核员 | 位置 |
| --- | --- | --- | --- | --- | --- | --- |
| critical | [`CRYPTO-001`](#finding-crypto-001) | 密码重置激活密钥熵值过低，可在线枚举实现任意账号接管 | 匿名 | confirmed | 未复核 | `app/account/models.py:424` |
| high | [`ACCESS-001`](#finding-access-001) | editPostAJAX 缺少属主校验，任意登录用户可篡改他人帖子 | 可自助注册的用户 | confirmed | 同意 | `app/wiki/views.py:447` |
| high | [`ACCESS-002`](#finding-access-002) | XML-RPC 接口缺少权限/属主校验，普通账号可删除或改写全站内容 | 可自助注册的用户 | confirmed | 未复核 | `lib/ylinux_xmlrpc.py:39` |
| high | [`XSS-001`](#finding-xss-001) | Markdown 渲染不转义 HTML 且模板用 \|safe 输出，导致存储型 XSS | 可自助注册的用户 | confirmed | 同意 | `app/ydata/models.py:251` |
| medium | [`ACCESS-003`](#finding-access-003) | 维护端点 update_post_profile 无认证，匿名 GET 即可全表改写帖子数据 | 匿名 | confirmed | 同意 | `app/ylab/views.py:37` |
| medium | [`CONFIG-001`](#finding-config-001) | DEBUG=True 硬编码且静态目录开启目录索引，泄露目录结构与调试信息 | 无请求入口 | confirmed | 同意 | `settings.py:18` |
| medium | [`CONFIG-002`](#finding-config-002) | SECRET_KEY 硬编码进仓库，会话完整性校验可被伪造 | 无请求入口 | confirmed | 同意 | `settings.py:78` |
| medium | [`CRYPTO-002`](#finding-crypto-002) | 口令使用弱哈希（单轮 SHA1 + 5 字符盐）存储 | 无请求入口 | confirmed | 同意 | `app/account/models.py:228` |
| medium | [`CSRF-001`](#finding-csrf-001) | 全站缺少 CSRF 防护，状态变更接口可被跨站请求触发 | 匿名 | confirmed | 同意 | `settings.py:98` |
| medium | [`XSS-002`](#finding-xss-002) | 附件上传不校验类型，DEBUG 静态服务下可投递同源存储型 XSS | 可自助注册的用户 | confirmed | 未复核 | `app/ydata/views.py:77` |
| medium | [`DESER-001`](#finding-deser-001) | 会话数据使用 pickle 反序列化且完整性密钥公开，存在伪造会话风险 | 无请求入口 | needs_review | 未复核 | `app/sessions/backends/base.py:86` |
| low | [`CONFIG-003`](#finding-config-003) | 数据库弱口令明文提交进仓库 | 无请求入口 | confirmed | 同意 | `settings.py:42` |
| low | [`REDIRECT-001`](#finding-redirect-001) | 登录/退出/后台登录存在开放重定向 | 匿名 | confirmed | 同意 | `app/account/views.py:42` |

下面的发现由 Agent 写入，每条引用都回到源码核对过。审计员综述写在复核之前，单条发现的状态以复核后为准。线索处置、读过的文件、阶段记录、工具序列和引用核对见 `appendix.md`，关键决策见 `decisions.md`。

## 审计员综述

这是一个基于 Django 1.x 的社区/知识库系统（YLinux）。整体安全状态差：模板层对用户生成内容使用 |safe 输出、Markdown 渲染不启用 safe_mode，形成可被任何自助注册用户投递的存储型 XSS（XSS-001）；附件上传不校验类型，配合仓库硬编码的 DEBUG 静态服务可投递同源存储型 XSS（XSS-002）；密码重置激活密钥只有约 20 位熵且接口无速率限制，可在线枚举实现任意账号接管（CRYPTO-001）；editPostAJAX 与 XML-RPC 接口缺少属主/权限校验，普通账号可篡改任意帖子甚至清空全站主题（ACCESS-001/002）；全站没有 CSRF 中间件且多处状态变更可由 GET 触发（CSRF-001）；DEBUG、SECRET_KEY、数据库口令均明文入库（CONFIG-001/002/003）；口令为单轮 SHA1 弱哈希（CRYPTO-002）；登录/退出存在开放重定向（REDIRECT-001）；会话使用 pickle 反序列化且完整性密钥公开（DESER-001）。原“上传路径穿越”判定经复核已撤销：Django 上传框架对文件名做 basename 消毒，穿越不可达。建议在部署前按发现逐一整改，优先处理密码重置接管与存储型 XSS。

## 风险概览

最高风险依次为：1) CRYPTO-001 密码重置密钥弱熵 + 无速率限制导致任意账号（含管理员）接管（critical）；2) XSS-001 存储型 XSS 配合无 HttpOnly 的会话 Cookie（high，可窃取会话）；3) ACCESS-002 任何注册账号一次 XML-RPC 调用清空全站主题（high）；4) ACCESS-001 任意注册用户篡改他人帖子并可注入脚本（high）；5) XSS-002 附件上传同源 XSS、CSRF-001 全站无 CSRF 防护、弱口令哈希、DEBUG/密钥入库、开放重定向等中低风险问题。

## 已确认的问题

<a id="finding-crypto-001"></a>

### [CRITICAL] 密码重置激活密钥熵值过低，可在线枚举实现任意账号接管

- 编号：`CRYPTO-001`
- 类别：`crypto`
- CWE：`CWE-330`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：未复核

密码重置激活密钥仅由 5 个十六进制字符的 salt（约 20 位熵，来自可预测的 random.random()）加 email 做一次 sha1 生成，候选空间仅 2^20；重置接口无速率限制且密钥无时效，攻击者可在线枚举实现任意账号的密码重置接管。

**触发条件。** 匿名调用 POST /account/password/reset/ 为目标 email 请求重置，随后枚举 2^20 个候选 activation_key 逐个请求 /account/password/reset/<key>/，命中后用 SetPasswordForm 设置新密码。

**数据流。** 来源：匿名 POST 任意目标 email 到 /account/password/reset/（app/account/views.py:167-174）→ 中间：register.reset_activation_key() 用 sha1(str(random.random())).hexdigest()[:5] 作为 salt，activation_key = sha1(salt+email)（app/account/models.py:424-430），密钥空间仅 16^5 ≈ 2^20；因攻击者不持有目标哈希、无法离线比对，但可用约 2^20 个候选 key 逐个在线验证（重置接口无速率限制、密钥无时效/单次失效）→ 危险点：命中 activation_key 后访问 /account/password/reset/<key>/，SetPasswordForm.save() 直接 user.set_password 并保存（app/account/forms.py:166-170）。无需登录、无需邮箱访问权。

**影响。** 攻击者对任意已知邮箱的账号发起重置请求后，枚举约 2^20 个候选 salt 生成 key 并逐个在线验证（无速率限制、密钥无失效机制），命中后即可把受害者密码改成攻击者设定的值，完成任意账号（含管理员）接管。

**修复。** 激活/重置密钥必须使用密码学安全随机源（secrets/os.urandom）生成足够熵值（≥128 位）且不可预测；对密码重置增加速率限制和短时效；重置成功后立即使旧密钥失效。

**判定历史。**

- 复核员同意：核实：app/account/models.py:424-430 salt 为 sha1(str(random.random())).hexdigest()[:5]（5 个十六进制字符，16^5≈2^20），activation_key=sha1(salt+email)，email 对攻击者已知；app/account/views.py:166-198 重置请求匿名可达、无速率限制、密钥无时效/单次失效；views.py:201-223 凭 key 直接 SetPasswordForm.save() 改密，无额外验证。措辞修正：候选 key 必须在线向 /account/password/reset/<key>/ 逐个验证（攻击者不持有目标哈希，无纯离线 oracle），"离线枚举即可还原"不精确；但 2^20 空间在线爆破在无节流、无失效机制下完全可行，任意账号（含管理员）接管成立，critical 可接受。（最弱一环：最弱一环是"离线枚举"说法：activation_key 只发往受害者邮箱并入库，攻击者无法纯离线比对，必须在线尝试约 2^20 个候选。）

**证据。**

`app/account/models.py:424-430`

```
    def reset_activation_key (self):
        ''' 重新生成 activation_key '''

        salt = sha_constructor(str(random.random())).hexdigest()[:5]
        if isinstance(self.email, unicode):
            email = self.email.encode('utf-8')
        self.activation_key = sha_constructor(salt+self.email).hexdigest()
```

`app/account/views.py:182-194`

```
        try:
            register = Register.objects.get(email=email)
            register.reset_activation_key()
            register.save()
        except Register.DoesNotExist:
            register=Register.objects.create_profile(email)

        # 发送邮件
        subject = u'YLinux.org 重置密码邮件'
        message = u"尊敬的 %s ，应您的要求，重置密码 URL 是， http://ylinux.org/account/password/reset/%s" % (email, register.activation_key)
```

`app/account/views.py:215-221`

```
    form = build_form (SetPasswordForm, request, user=user)

    if form.is_valid():
        form.clean_new_password2()
        form.save()

        return {'PASSWORD_RESET_DONE':True,}
```

<a id="finding-access-001"></a>

### [HIGH] editPostAJAX 缺少属主校验，任意登录用户可篡改他人帖子

- 编号：`ACCESS-001`
- 类别：`access_control`
- CWE：`CWE-639`
- 入口身份：可自助注册的用户
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

editPostAJAX 只要求登录，完全不做属主校验：任何注册用户对任意 postID 提交 POST 即可改写该帖子的 body 并保存。

**触发条件。** 登录后向 /wiki/post/<任意 postID>/editAJAX/ 提交 POST body 字段即可覆盖该帖子内容。

**数据流。** 来源：POST 参数 body 与 URL 中的 postID（app/wiki/views.py:456 及 app/wiki/urls.py:54 路由）→ 中间：post = get_object_or_404(Post, pk=postID)（app/wiki/views.py:451），无任何 post.user == request.user 之类的属主校验（对比 del_post 在 app/wiki/views.py:277 有校验）→ 危险点：post.body = post_body; post.save()（app/wiki/views.py:459-460）。入口 @login_required（app/wiki/views.py:447），任何自助注册账号可达。

**影响。** 任意注册用户可覆盖站内任何人的帖子内容（伪造他人发言），并可在他人帖子中注入脚本（配合 XSS-001），破坏全站内容完整性。

**修复。** 在 editPostAJAX 中校验 post.user == request.user（或授予相应权限），与 del_post 保持一致；所有按 ID 操作的写接口统一做属主/权限检查。

**复核员指出的最弱一环。** 最弱一环是属主校验是否真缺失——若 editPostAJAX 内有类似 del_post 的 post.user != request.user 检查则发现不成立。

**判定历史。**

- 复核员同意：核实 app/wiki/views.py:447-467：editPostAJAX 仅 @login_required，取 post 后直接 post.body = request.POST['body']; post.save()，全函数无 post.user == request.user 或权限检查；对照同文件 del_post（271-283）确有属主校验，证明此处是遗漏而非设计。路由 app/wiki/urls.py:54 存在。任意自助注册账号可改写任意帖子内容，配合 XSS-001 可投毒，high 合理。（最弱一环：最弱一环是属主校验是否真缺失——若 editPostAJAX 内有类似 del_post 的 post.user != request.user 检查则发现不成立。）

**证据。**

`app/wiki/views.py:447-451`

```
@login_required
@render_to('wiki/editPostAJAX.html')
def editPostAJAX(request, postID):

    post = get_object_or_404(Post, pk = postID)
```

`app/wiki/views.py:456-460`

```
    post_body = request.POST.get('body', None)
    if not post_body:
        return HttpResponse(u'error: No contents found!')
    post.body = post_body
    post.save()
```

`app/wiki/views.py:271-278`

```
@login_required
def del_post (request, id):

    post = get_object_or_404 (Post, pk=id)
    t_id = post.topic.id

    if post.user != request.user:
        return HttpResponseForbidden('<h1>您没有这个权限！</h1>')
```

<a id="finding-access-002"></a>

### [HIGH] XML-RPC 接口缺少权限/属主校验，普通账号可删除或改写全站内容

- 编号：`ACCESS-002`
- 类别：`access_control`
- CWE：`CWE-862`
- 入口身份：可自助注册的用户
- 置信度：`high`
- 状态：`confirmed`
- 复核员：未复核

XML-RPC 接口的 delete_topic/delete_all_topic/edit_topic 只验证账号密码，不校验权限和属主，任何自助注册账号都能删除全站所有主题或改写任意内容。

**触发条件。** 用任意注册账号的凭证向 /xmlrpc/ 调用 delete_topic、delete_all_topic、metaWeblog.editPost 等方法。

**数据流。** 来源：匿名可访问的 /xmlrpc/（urls.py:45-48，@csrf_exempt 的 handle_xmlrpc）→ 中间：has_auth(user, passwd) 仅做账号密码校验，不检查权限与属主（lib/ylinux_xmlrpc.py:39-45）→ 危险点：delete_topic 删除任意 id 主题（lib/ylinux_xmlrpc.py:53-55）、delete_all_topic 删除全部主题（lib/ylinux_xmlrpc.py:66）、edit_topic 修改任意 postid 主题（lib/ylinux_xmlrpc.py:174-181）、new_topic 任意发帖。任何自助注册账号即可调用，且凭证明文走 HTTP。

**影响。** 任何自助注册账号一次 XML-RPC 调用即可删除全站所有主题（delete_all_topic）、删除任意主题或改写任意主题内容（配合 XSS-001 注入脚本），全站内容可被清空或篡改，破坏面大于单帖篡改。

**修复。** 对删除/编辑类 XML-RPC 方法做属主或权限校验（如 ydata.delete_topic 权限或 user == topic.user）；限制 delete_all_topic 仅超级管理员可用；部署 HTTPS 保护 XML-RPC 凭证传输。

**异议或降级说明。** 事实链核实无误：settings.py:164-166/171 将 delete_topic、delete_all_topic、edit_topic 注册进 XMLRPC_METHODS，urls.py:45-48 经 @csrf_exempt 的 handle_xmlrpc 暴露；lib/ylinux_xmlrpc.py:39-45 has_auth 仅 authenticate，47-58/60-67/168-185 目标函数内无任何权限或属主判断，Topic.objects.all().delete() 可被任意有效账号触发；注册自助开放，entry_role 属实。分歧仅在定级：任意注册账号一次调用即可清空全站主题，利用成本极低、破坏面大于 ACCESS-001（已评 high 的单帖篡改），medium 明显偏低。（建议严重性：high）

**判定历史。**

- 复核员否决：事实链核实无误：settings.py:164-166/171 将 delete_topic、delete_all_topic、edit_topic 注册进 XMLRPC_METHODS，urls.py:45-48 经 @csrf_exempt 的 handle_xmlrpc 暴露；lib/ylinux_xmlrpc.py:39-45 has_auth 仅 authenticate，47-58/60-67/168-185 目标函数内无任何权限或属主判断，Topic.objects.all().delete() 可被任意有效账号触发；注册自助开放，entry_role 属实。分歧仅在定级：任意注册账号一次调用即可清空全站主题，利用成本极低、破坏面大于 ACCESS-001（已评 high 的单帖篡改），medium 明显偏低。（建议严重性：high）
- 状态 disputed → confirmed

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

`lib/ylinux_xmlrpc.py:47-58`

```
def delete_topic(id, user, passwd):
    '''delete one topic'''
    if not has_auth(user, passwd):
        raise Fault(-1, "Authentication Failure")

    try:
        topic = Topic.objects.get(pk=id)
        topic.posts.all().delete()
        topic.delete()
        return True
```

`lib/ylinux_xmlrpc.py:60-67`

```
def delete_all_topic(user, passwd):
    '''delete all topic'''
    if not has_auth(user, passwd):
        raise Fault(-1, "Authentication Failure")

    try:
        Topic.objects.all().delete()
        return True
```

<a id="finding-xss-001"></a>

### [HIGH] Markdown 渲染不转义 HTML 且模板用 |safe 输出，导致存储型 XSS

- 编号：`XSS-001`
- 类别：`xss`
- CWE：`CWE-79`
- 入口身份：可自助注册的用户
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

帖子和主题正文在保存时经 python-markdown 渲染成 HTML，但对 markup='none' 的帖子（AddPostForm、replayAJAX 都硬编码为 'none'）和所有主题（Topic.save_file）调用 Markdown 时没有启用 safe_mode，用户输入的原始 HTML（如 <script>）会原样进入 body_html；所有展示页又通过 {{ body_html|safe }} 原样输出，形成存储型 XSS。会话 Cookie 未设置 HttpOnly，XSS 可直接窃取会话。

**触发条件。** 注册用户通过 /wiki/topic/<id>/addpost/、/wiki/topic/<id>/replayAJAX/ 提交带原始 HTML 的 body，或通过 /wiki/catalog/<id>/addtopic/、XML-RPC metaWeblog.newPost 提交主题正文；其他用户访问主题页即触发。

**数据流。** 来源：request.POST['body']（app/wiki/views.py:432 replayAJAX，或 AddPostForm body 字段）→ 中间：Post(markup='none', body=post_body)（app/wiki/views.py:435）→ Post.save() 的 markup=='none' 分支 self.body_html = Markdown(...).convert(ylinux_text_filter(self.body)) 无 safe_mode（app/ydata/models.py:260）→ 存储到 body_html；主题路径：AddTopicForm.save→topic.save_file(text)→Markdown(...).convertFile 无 safe_mode（app/ydata/models.py:198-200）→ 危险点：模板 {{ post.body_html|safe }}（app/wiki/utils.py:18、templates/wiki/post.html:12、templates/wiki/topic.html:54、templates/bbs/topic.html:23/30）。入口需登录，注册通过邮件自助开放（account/views.py:64 request_register）。

**影响。** 任何浏览该主题/帖子的访客（含管理员）都会在站点源上执行攻击者脚本：窃取会话 Cookie（set_cookie 未加 HttpOnly）、以受害者身份发帖/删帖、钓鱼、借 admin 会话越权操作。

**修复。** 渲染用户内容时开启 safe_mode='escape'（或升级到新版 markdown 并对输出做白名单清洗）；将 |safe 替换为默认转义输出，仅在确需富文本时使用经过消毒的 HTML；ylinux_text_filter 插入附件名时先 escape；为会话 Cookie 设置 HttpOnly。

**复核员指出的最弱一环。** 最弱一环是 markup='none' 路径是否真的不经过任何 HTML 转义（若 ylinux_text_filter 或 Markdown 默认转义则结论不成立）。

**判定历史。**

- 复核员同意：核对要点：①app/ydata/forms.py:46 与 app/wiki/views.py:435 两处均硬编码 markup='none'；②app/ydata/models.py:258-260 'none' 分支调用 Markdown(extensions=['fenced_code']).convert(...)，无 safe_mode，lib/markdown 为 Python-Markdown 2.x，默认 safe_mode=False，原始 HTML 原样通过；③ylinux_text_filter（models.py:396-430）只做附件/维基引用替换，不转义 HTML；④主题路径 Topic.save_file（models.py:198-200）convertFile 同样无 safe_mode；⑤输出端 app/wiki/utils.py:18、templates/wiki/topic.html:54/59、post.html:12 均 |safe；⑥会话 Cookie（sessions/middleware.py:37-41）确实未带 httponly。入口：replayAJAX 虽无 @login_required 装饰器，但 399-400 行手动检查 is_authenticated，add_post/add_topic 有 @login_required；注册经 request_register 邮件自助开放，entry_role=registered_open 属实。无转义环节，存储型 XSS 成立，high 合理。（最弱一环：最弱一环是 markup='none' 路径是否真的不经过任何 HTML 转义（若 ylinux_text_filter 或 Markdown 默认转义则结论不成立）。）

**证据。**

`app/ydata/models.py:251-260`

```
    def save(self, *args, **kwargs):
        if self.markup == 'bbcode':
            self.body_html = bbmarkup.bbcode(self.body)
        #elif self.markup == 'markdown' and MARKDOWN_AVAILABLE:
        elif self.markup == 'markdown':
            self.body_html = unicode(Markdown(self.body, safe_mode='escape'))
            #self.body_html = markdown(self.body, 'safe')
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

`app/ydata/forms.py:45-46`

```
    def save(self):
        post = Post(topic=self.topic, user=self.user, user_ip=self.ip, markup='none', body=self.cleaned_data['body'])
```

`app/wiki/utils.py:17-18`

```
<div class="post-body">
  <p>{{ post.body_html|safe }}</p>
```

`templates/wiki/topic.html:53-54`

```
  <div class="topic-body content">
    {{ topic.body_html|safe }}
```

`app/wiki/views.py:432-436`

```
        post_body = request.POST.get("body", None)
        if len(post_body) < 2:
            return {'error': u'您的回复太短，至少2个字符！'}
        post = Post(topic = topic, user = request.user, user_ip = ip, markup = 'none', body = post_body, parent = parent_post)
        post.save()
```

<a id="finding-access-003"></a>

### [MEDIUM] 维护端点 update_post_profile 无认证，匿名 GET 即可全表改写帖子数据

- 编号：`ACCESS-003`
- 类别：`access_control`
- CWE：`CWE-862`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

/lab/update_post_profile 是一个无认证、GET 即可触发的全表写维护端点，匿名用户可反复触发全站帖子数据改写。

**触发条件。** 匿名访问 GET /lab/update_post_profile 即触发。

**数据流。** 来源：匿名 GET /lab/update_post_profile（app/ylab/urls.py:8 路由到 ylab.views.update_post_profile）→ 中间：无任何登录/权限检查（app/ylab/views.py:37-46 无装饰器、不读 request.user）→ 危险点：遍历全表 Post 并 p.save()（app/ylab/views.py:39-46），批量改写 touser 与 updated 字段。

**影响。** 任何匿名访问者可通过 GET 请求触发全站帖子的批量更新：重写所有帖子的 updated 时间与 touser 映射，扰乱排序、时间线和“给我的评论”数据，可反复触发造成数据破坏。

**修复。** 删除该测试/维护端点，或移入管理命令（management command）并在视图上增加管理员权限校验与 POST 限制。

**复核员指出的最弱一环。** 最弱一环是入口是否真无认证——若视图或全局中间件有登录要求则 anonymous 不成立。

**判定历史。**

- 复核员同意：核实：app/ylab/urls.py:8 将 ^update_post_profile$ 路由到该视图；app/ylab/views.py:37-48 函数无任何装饰器、不读 req.user、不查方法，GET 即遍历 Post.objects.all() 改写 touser/updated 并 p.save()。匿名可反复触发全表写，影响排序/时间线/提醒数据，属实。属数据完整性破坏但不可逆性低、不直接泄露或执行代码，medium 合理。（最弱一环：最弱一环是入口是否真无认证——若视图或全局中间件有登录要求则 anonymous 不成立。）

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

`app/ylab/urls.py:5-8`

```
urlpatterns = patterns('ylab.views',
    url(r'^time$', 'time', name='time'),
    url(r'^uploadsf$', 'upload_single_file', name='uploadsf'),
    url(r'^update_post_profile$', 'update_post_profile', name='update_post_profile'),
```

<a id="finding-config-001"></a>

### [MEDIUM] DEBUG=True 硬编码且静态目录开启目录索引，泄露目录结构与调试信息

- 编号：`CONFIG-001`
- 类别：`config`
- CWE：`CWE-489`
- 入口身份：无请求入口
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

DEBUG=True 被硬编码进仓库，并且 DEBUG 模式下 /ymedia/ 以 show_indexes=True 提供静态文件服务，导致目录遍历列表与调试信息泄露。

**触发条件。** 任意访问者请求 /ymedia/ 查看目录列表、请求任意媒体文件；触发任意异常查看 DEBUG 错误页。

**数据流。** 配置类问题：settings.py:18 DEBUG = True；urls.py:59-62 在 DEBUG 下挂载 django.views.static.serve 且 show_indexes=True 到 /ymedia/，MEDIA_ROOT（settings.py:74）含附件、主题源文件（ydata/topics/*.src 与 *.html）等。

**影响。** 生产环境若沿用该配置：访问者可通过 /ymedia/ 浏览媒体目录全量清单（show_indexes=True），任意下载附件与主题源码文件；发生异常时 DEBUG 页面回显 traceback 及局部变量（可能包含 SECRET_KEY、数据库配置等敏感信息）。

**修复。** 生产环境强制 DEBUG=False；将静态文件服务交给前端 Web 服务器并关闭 show_indexes；用环境变量区分开发/生产配置，避免把 DEBUG 硬编码进仓库。

**复核员指出的最弱一环。** 最弱一环是配置是否生效——若部署覆盖 DEBUG 或不走该 static serve 挂载则影响不成立。

**判定历史。**

- 复核员同意：核实：settings.py:18 DEBUG=True 硬编码，仓库内未见 local_settings 之类覆盖；urls.py:59-62 在 settings.DEBUG 为真时将 ^ymedia/(?P<path>.*)$ 挂到 django.views.static.serve 且 show_indexes=True，document_root=MEDIA_ROOT（settings.py:74，项目内 ymedia/，含附件与主题 .src/.html）。配置处于生效路径，目录清单可浏览、DEBUG 异常页回显调试信息。medium 合理。（最弱一环：最弱一环是配置是否生效——若部署覆盖 DEBUG 或不走该 static serve 挂载则影响不成立。）

**证据。**

`settings.py:18-19`

```
DEBUG = True
TEMPLATE_DEBUG = DEBUG
```

`urls.py:59-62`

```
if (settings.DEBUG):
    urlpatterns += patterns ('',
        (r'^ymedia/(?P<path>.*)$', 'django.views.static.serve',
         {'document_root': settings.MEDIA_ROOT, 'show_indexes': True}),
```

<a id="finding-config-002"></a>

### [MEDIUM] SECRET_KEY 硬编码进仓库，会话完整性校验可被伪造

- 编号：`CONFIG-002`
- 类别：`config`
- CWE：`CWE-798`
- 入口身份：无请求入口
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

SECRET_KEY 明文硬编码在仓库中，且被用于会话数据 MD5 完整性校验和会话 key 生成，会话防篡改保护可被绕过。

**触发条件。** 任何人读取仓库代码即可获得 SECRET_KEY（配置本身即是触发条件）。

**数据流。** 配置类问题：settings.py:79 硬编码 SECRET_KEY；该值被用作会话数据完整性校验（app/sessions/backends/base.py:89/95、app/sessions/models.py:18/63）与会话 key 生成的盐（app/sessions/backends/base.py:141-143）。

**影响。** SECRET_KEY 随源码公开，任何拿到仓库的人都能为会话数据计算合法校验值，会话防篡改机制形同虚设（一旦能写入会话存储即可伪造管理员会话）；密码重置令牌生成（app/account/tokens.py:54）同样依赖该密钥。

**修复。** 从仓库移除密钥，改为环境变量/密钥管理注入并在各环境使用不同的随机 SECRET_KEY；对已泄露密钥的部署立即轮换。

**复核员指出的最弱一环。** 最弱一环是密钥是否真被安全代码使用——若仅闲置配置则影响有限。

**判定历史。**

- 复核员同意：核实：settings.py:79 SECRET_KEY 明文硬编码；app/sessions/backends/base.py:86-96 encode/decode 用 md5(pickled+SECRET_KEY) 做完整性校验，131-146 会话 key 生成以 SECRET_KEY 为盐，密钥确用于安全功能。仓库公开则防篡改校验可被重算；实际伪造会话还需会话存储写能力（与 DESER-001 前提一致），故 medium 而非更高，定级合理。（最弱一环：最弱一环是密钥是否真被安全代码使用——若仅闲置配置则影响有限。）

**证据。**

`settings.py:78-79`

```
# Make this unique, and don't share it with anybody.
SECRET_KEY = 'c#0cz^i$lyr6*b*xe-t@0tqc_c3dnju=+c1lk^k7(r^7lhz$g@'
```

`app/sessions/backends/base.py:140-143`

```
        while 1:
            session_key = md5_constructor("%s%s%s%s"
                    % (randrange(0, MAX_SESSION_KEY), pid, time.time(),
                       settings.SECRET_KEY)).hexdigest()
```

<a id="finding-crypto-002"></a>

### [MEDIUM] 口令使用弱哈希（单轮 SHA1 + 5 字符盐）存储

- 编号：`CRYPTO-002`
- 类别：`crypto`
- CWE：`CWE-916`
- 入口身份：无请求入口
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

用户口令使用单轮 sha1 + 仅 5 位十六进制随机盐存储，且兼容无盐 md5 旧格式，抗离线破解能力很弱。

**触发条件。** 口令哈希生成发生在用户注册/改密时；数据库内容一旦泄露即可离线破解。

**数据流。** 注册/管理员建号时 user.set_password（app/account/models.py:228-234）生成 'sha1$<5位salt>$<sha1(salt+password)>'；get_hexdigest 支持无盐 md5/sha1（app/account/models.py:62-65），旧格式口令回退为 md5('' + password)（app/account/models.py:243-244）。

**影响。** 数据库泄露后口令哈希可被高速离线破解：单轮 sha1、5 位十六进制盐（仅 20 位）、无迭代/加盐参数，普通字典攻击即可批量还原弱口令。

**修复。** 迁移到强哈希方案（如 Django 现代版的 PBKDF2/Argon2 或 bcrypt），对存量哈希做登录时自动升级；为新哈希使用充足随机盐与高迭代次数。

**复核员指出的最弱一环。** 最弱一环是哈希构造是否如述（单轮、5 字符盐、无迭代）——已逐行确认。

**判定历史。**

- 复核员同意：核实：app/account/models.py:228-234 set_password 用 algo='sha1'、salt 取 get_hexdigest(...random...)[:5]（5 位十六进制≈20 位熵），单轮 sha1(salt+password) 落库；50-66 get_hexdigest 为无迭代 md5/sha1；236-249 旧格式回退无盐 md5。单轮 SHA1+20 位短盐在 GPU 字典攻击下很弱，属实。需库泄露后才能离线破解，medium 合理。（最弱一环：最弱一环是哈希构造是否如述（单轮、5 字符盐、无迭代）——已逐行确认。）

**证据。**

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

`app/account/models.py:62-65`

```
    if algorithm == 'md5':
        return md5_constructor(salt + raw_password).hexdigest()
    elif algorithm == 'sha1':
        return sha_constructor(salt + raw_password).hexdigest()
```

<a id="finding-csrf-001"></a>

### [MEDIUM] 全站缺少 CSRF 防护，状态变更接口可被跨站请求触发

- 编号：`CSRF-001`
- 类别：`csrf`
- CWE：`CWE-352`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

项目未启用任何 CSRF 中间件，且删除/隐藏/回收主题等状态变更接口可通过 GET 触发，存在全站跨站请求伪造风险。

**触发条件。** 攻击者页面嵌入指向 /wiki/topic/<id>/delete/ 等地址的图片/表单/链接，诱导已登录用户访问。

**数据流。** 来源：攻击者构造的跨站页面诱导已登录受害者浏览器发请求 → 中间：MIDDLEWARE_CLASSES 仅含 CommonMiddleware 与自定义 Session/Authentication 中间件，没有 CsrfViewMiddleware（settings.py:98-104），且会话仅靠 Cookie 认证（app/sessions/middleware.py:11-12 读 Cookie 建立 session）→ 危险点：大量状态变更接口无 CSRF 防护且部分可由 GET 触发，如 manage_topic 的 delete/recycled/hidden（app/wiki/urls.py:34-38，模板里是普通 <a href> 链接 templates/wiki/topic.html:44-48）、del_post、editPostAJAX（POST 但无 token 校验）。

**影响。** 攻击者可诱导登录用户触发删除/隐藏/回收主题、删除帖子、篡改任意帖子等状态变更操作；全站不存在 CSRF 防护层。

**修复。** 启用 CsrfViewMiddleware 并对所有模板表单加 {% csrf_token %}；所有状态变更只接受 POST；manage_topic/del_post 等改为 POST 并校验 CSRF token；敏感操作再加二次确认。

**复核员指出的最弱一环。** 最弱一环是状态变更能否 GET 触发——若 manage_topic 限定 POST，<a href> 跨站触发即不成立。

**判定历史。**

- 复核员同意：核实：settings.py:98-104 MIDDLEWARE_CLASSES 仅 CommonMiddleware 与自定义 Session/Authentication 中间件，无 CsrfViewMiddleware，模板表单未见 csrf token；会话靠 Cookie（sessions/middleware.py:11-12）。app/wiki/urls.py:34-38 将 delete/recycled/hidden 等挂到 manage_topic，wiki/views.py:237-268 不限制请求方法，GET 即触发；templates/wiki/topic.html:44-48 为普通 <a href>。manage_topic 的属主校验不防 CSRF（浏览器自动带受害者 Cookie）。del_post、editPostAJAX 同样无 token。全站 CSRF 成立，medium 合理。（最弱一环：最弱一环是状态变更能否 GET 触发——若 manage_topic 限定 POST，<a href> 跨站触发即不成立。）

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

`app/wiki/urls.py:34-38`

```
    url(r'^topic/(?P<id>\d+)/delete/$', 'manage_topic', {'type':'delete'}, name='del_topic'),
    url(r'^topic/(?P<id>\d+)/recycled/$', 'manage_topic', {'type':'recycled'}, name='recycled_topic'),
    url(r'^topic/(?P<id>\d+)/hidden/$', 'manage_topic', {'type':'hidden'}, name='hidden_topic'),
    url(r'^topic/(?P<id>\d+)/disable_recycled/$', 'manage_topic', {'type':'disable_recycled'}, name='disable_recycled_topic'),
    url(r'^topic/(?P<id>\d+)/disable_hidden/$', 'manage_topic', {'type':'disable_hidden'}, name='disable_hidden_topic')
```

`templates/wiki/topic.html:44-48`

```
      {% ifequal user topic.user %}
      <!--[<a href="{% url wiki:del_topic topic.id %}">删除</a>]-->| 
      [<a href="{% url wiki:hidden_topic topic.id %}">隐藏</a>] 
      [<a href="{% url wiki:recycled_topic topic.id %}">移入回收站</a>]
      {% endifequal %}
```

<a id="finding-xss-002"></a>

### [MEDIUM] 附件上传不校验类型，DEBUG 静态服务下可投递同源存储型 XSS

- 编号：`XSS-002`
- 类别：`xss`
- CWE：`CWE-434`
- 入口身份：可自助注册的用户
- 置信度：`medium`
- 状态：`confirmed`
- 复核员：未复核

附件上传不校验扩展名与内容类型，文件原样落入 MEDIA_ROOT；DEBUG 模式下 /ymedia/ 由 django.views.static.serve 按扩展名猜测 Content-Type 提供且无 Content-Disposition，上传的 HTML 可在站点源被受害者浏览器执行，形成经文件上传的同源存储型 XSS。

**触发条件。** 登录后向 /ydata/uploadsf/<topic_id>/ 上传名为 *.html（或 *.svg）且内容含脚本的文件，诱导受害者访问 /ymedia/ydata/attachments/<id>-<uid>-<名字>。

**数据流。** 来源：登录用户上传的文件内容与文件名（app/ydata/views.py:40 f = req.FILES['single_file']，无扩展名/MIME 校验）→ 中间：以 str(id)+'-'+str(user.id)+'-'+f.name 落盘到 MEDIA_ROOT/ydata/attachments/（app/ydata/views.py:78-84、app/ydata/settings.py:65）→ 服务：DEBUG=True（settings.py:18）时 /ymedia/(?P<path>.*) 由 django.views.static.serve 提供，Content-Type 按扩展名猜测且不带 Content-Disposition/X-Content-Type-Options（urls.py:59-62）→ 危险点：受害者访问 /ymedia/ydata/attachments/<id>-<uid>-x.html 时浏览器按 text/html 在站点源渲染攻击者脚本。次要向量：上传响应把 attachment.name 未转义插入 AfterSubmit(...) JS 字符串（app/ydata/views.py:91-95），属影响上传者本人的反射注入。入口 @login_required，注册自助开放。

**影响。** 登录用户可上传含脚本的 .html/.svg 附件，随后诱导任何访客访问 /ymedia/ 下的对应 URL，脚本在站点源执行：窃取会话 Cookie（无 HttpOnly）、冒用受害者身份操作。此链条依赖仓库硬编码的 DEBUG=True 与静态服务挂载，均处于生效配置。

**修复。** 限制附件扩展名与 MIME 白名单；上传内容一律以 application/octet-stream + Content-Disposition: attachment 提供；静态服务对 /ymedia 加 nosniff 或禁止提供 HTML 类文件；生产环境关闭 DEBUG 静态服务；AfterSubmit 响应中的文件名做 JS 字符串转义（或改用 JSON 序列化）。

**证据。**

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

`urls.py:59-62`

```
if (settings.DEBUG):
    urlpatterns += patterns ('',
        (r'^ymedia/(?P<path>.*)$', 'django.views.static.serve',
         {'document_root': settings.MEDIA_ROOT, 'show_indexes': True}),
```

`app/ydata/views.py:91-95`

```
    r = u'<script type="text/javascript">window.parent.AfterSubmit("%s","%s","%s","%s","%s");</script>'\
        % (attachment.id, attachment.name,
           reverse ('ydata:show_attachment', args=[attachment.id]),
           reverse ('ydata:download_attachment', args=[attachment.id]),
           notes)
```

<a id="finding-config-003"></a>

### [LOW] 数据库弱口令明文提交进仓库

- 编号：`CONFIG-003`
- 类别：`config`
- CWE：`CWE-798`
- 入口身份：无请求入口
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

数据库口令 123456 明文提交在 settings.py，启用 MySQL 等网络数据库后即为可远程利用的弱凭据。

**触发条件。** 读取 settings.py 即获得数据库账号口令；部署切换到 MySQL 引擎后凭据生效。

**数据流。** 配置类问题：settings.py:42-53 DATABASES 中明文提交 'PASSWORD': '123456'（切换到 MySQL 引擎时生效，注释示例即 mysql）。

**影响。** 弱口令与配置一并入库：一旦切换到 MySQL 并沿用该密码，任何能连到数据库端口的人（或通过其他漏洞拿到配置的人）可凭 ylinux/123456 直连数据库，读取全部用户密码哈希与数据。

**修复。** 数据库凭据不要写入仓库，使用环境变量/密钥管理，并使用强随机密码；数据库端口限制来源 IP。

**复核员指出的最弱一环。** 最弱一环是该口令当前是否生效——sqlite 引擎下 PASSWORD 完全不参与认证。

**判定历史。**

- 复核员同意：核实：settings.py:42-53 当前 ENGINE 为 sqlite3，USER/PASSWORD 对 sqlite 不生效，弱口令 123456 仅在切换 MySQL 后才有远程利用面。审计员定 low 并注明条件，与"当前配置不生效"的事实相符，定级恰当。（最弱一环：最弱一环是该口令当前是否生效——sqlite 引擎下 PASSWORD 完全不参与认证。）

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

<a id="finding-redirect-001"></a>

### [LOW] 登录/退出/后台登录存在开放重定向

- 编号：`REDIRECT-001`
- 类别：`redirect`
- CWE：`CWE-601`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

登录、退出与后台登录后的重定向目标取自用户可控的 next 参数或 Referer，未做站内校验，存在开放重定向。

**触发条件。** 访问 /account/login/?next=https://attacker.example 登录后被跳转；或访问 /account/logout/?next=... 立即跳转；admin 登录的跳转来自 Referer。

**数据流。** 来源：GET 参数 next（app/account/views.py:44 存入 session、58-60 logout 直接读取）与 HTTP_REFERER（app/admin/views.py:65）→ 危险点：HttpResponseRedirect(request.session.get('login_redirect_url','/'))（app/account/views.py:38）、HttpResponseRedirect(previous_url or '/')（app/account/views.py:60）、HttpResponseRedirect(request.session.get('previous_url','/'))（app/admin/views.py:62），均未校验目标是站内地址。

**影响。** 可用于钓鱼：把登录后/退出后的跳转导向攻击者控制的站点，诱导用户误以为仍在站内输入凭据；admin 登录后的跳转目标同样来自 Referer，不可信。

**修复。** 跳转目标只允许站内相对路径或白名单域名；使用 django.utils.http.is_safe_url（或等价逻辑）校验；Referer 不可作为跳转依据。

**复核员指出的最弱一环。** 最弱一环是跳转前是否有站内校验——若存在域名/相对路径白名单则发现不成立；已确认三处均无。

**判定历史。**

- 复核员同意：核实：app/account/views.py:44 把 GET 参数 next 原样存入 session['login_redirect_url']，38 登录成功后 HttpResponseRedirect 到该值，无 is_safe_url 类校验；55-60 logout 直接用 request.GET.get('next') 跳转；app/admin/views.py:62/65 后台登录跳转目标取自 session['previous_url']，来源是 HTTP_REFERER。三处跳转目标均用户可控，开放重定向成立。用于钓鱼，low 合理。（最弱一环：最弱一环是跳转前是否有站内校验——若存在域名/相对路径白名单则发现不成立；已确认三处均无。）

**证据。**

`app/account/views.py:42-45`

```
    else:
        # 形如 "http://127.0.0.1:8000/account/login?next=/admin/" 的 url 可以得到 next 值
        request.session['login_redirect_url'] = request.GET.get('next')
        form = AuthenticationForm(request)
```

`app/account/views.py:55-60`

```
def logout(request):
    #from django.contrib.auth import logout
    from account import logout
    previous_url = request.GET.get('next')
    logout(request)
    return HttpResponseRedirect(previous_url or '/')
```

## 需要再确认的问题

<a id="finding-deser-001"></a>

### [MEDIUM] 会话数据使用 pickle 反序列化且完整性密钥公开，存在伪造会话风险

- 编号：`DESER-001`
- 类别：`deserialization`
- CWE：`CWE-502`
- 入口身份：无请求入口
- 置信度：`medium`
- 状态：`needs_review`
- 复核员：未复核

自定义会话后端用 cPickle 反序列化会话数据，完整性校验密钥（MD5 + SECRET_KEY）已随仓库公开；若攻击者能写入会话存储，可构造恶意 pickle 导致服务端代码执行。

**触发条件。** 攻击者需先获得会话存储写能力（数据库写能力、文件后端目录写入等）；获得后用公开 SECRET_KEY 计算校验值并写入恶意 pickle 会话。

**数据流。** 会话存储：SessionStore.encode 用 cPickle 序列化 + md5(pickled+SECRET_KEY) 校验（app/sessions/backends/base.py:86-90），decode 先验校验再 pickle.loads（app/sessions/backends/base.py:92-102）；app/sessions/models.py:60-71 是同样逻辑的模型版本。SECRET_KEY 已随仓库公开（CONFIG-002），因此该校验值可被任何攻击者重新计算；只要攻击者能写入会话存储（如数据库写能力、文件后端共用可写目录或其他文件写能力），即可伪造会话数据。会话数据存服务端，远程直接利用受限，需与写入能力组合。

**影响。** 一旦攻击者获得会话存储的写能力，可构造恶意 pickle 对象并在服务端反序列化时执行任意代码；由于防篡改密钥已公开，此防护不会构成障碍。当前会话数据存在服务端，远程直接利用受限，需与写入能力组合。

**修复。** 改用 JSON 序列化并签名的会话（如 Django 现代 SignedCookieSession/JSON session）；绝不使用 pickle 反序列化会话数据；轮换已公开的 SECRET_KEY。

**判定历史。**

- 复核员同意：核实：app/sessions/backends/base.py:86-98 encode 用 pickle.dumps + md5(pickled+SECRET_KEY)，decode 校验后 pickle.loads；settings.py 未设 SESSION_ENGINE，运行时走 Django 默认 db 后端，该年代 contrib 后端同样是 pickle+md5(SECRET_KEY) 模式，且会话 Cookie 只存 key（sessions/middleware.py:11-12, 37-41），数据在服务端库中。故远程直接利用确实需要先获得会话存储写能力（SQLi、或 CONFIG-002 密钥泄露结合其他写入面），审计员已如实标注该前提并评 needs_review/medium，未夸大。加密学上不安全的反序列化设计成立，medium 合理。（最弱一环：最弱一环是可达性：会话数据存服务端，攻击者无法直接控制被 pickle.loads 的字节流，必须先有会话存储写能力。）

**证据。**

`app/sessions/backends/base.py:86-98`

```
    def encode(self, session_dict):
        "Returns the given session dictionary pickled and encoded as a string."
        pickled = pickle.dumps(session_dict, pickle.HIGHEST_PROTOCOL)
        pickled_md5 = md5_constructor(pickled + settings.SECRET_KEY).hexdigest()
        return base64.encodestring(pickled + pickled_md5)

    def decode(self, session_data):
        encoded_data = base64.decodestring(session_data)
        pickled, tamper_check = encoded_data[:-32], encoded_data[-32:]
        if md5_constructor(pickled + settings.SECRET_KEY).hexdigest() != tamper_check:
            raise SuspiciousOperation("User tampered with session cookie.")
        try:
            return pickle.loads(pickled)
```

## 复核员否决、尚未改判的问题

无。

## 已排除的可疑点

<a id="finding-file-001"></a>

### [LOW] 附件上传文件名路径穿越（复核后判定：框架已消毒，不成立）

- 编号：`FILE-001`
- 类别：`file_access`
- CWE：`CWE-22`
- 入口身份：可自助注册的用户
- 置信度：`high`
- 状态：`rejected`
- 复核员：未复核

原判“上传文件名路径穿越”不成立：f.name 经 Django 上传框架的 os.path.basename 消毒后才到达视图，../ 与绝对路径分量已被剥离，无法逃出附件目录；降为 rejected，残余的上传风险改记 XSS-002。

**触发条件。** 无有效触发：multipart filename 中的目录分量在框架层被 basename 剥离。

**数据流。** 曾怀疑的来源：req.FILES['single_file'].name（app/ydata/views.py:40）→ 拼接 local_name 与 open(save_path,'wb+')（app/ydata/views.py:78-84）。复核判定：Django 上传框架在构造 UploadedFile 时对文件名执行 os.path.basename 消毒，视图拿到的 f.name 已不含目录分量，../ 与绝对路径无法到达 open()，路径穿越不可达。

**影响。** 按路径穿越机制不可利用：框架层已对文件名做 basename 消毒。残余风险（上传文件类型不受限、DEBUG 下同源提供 HTML 导致存储型 XSS）已单独记录为 XSS-002。

**修复。** 虽无路径穿越，仍建议：落盘名用 UUID/哈希、限制允许的扩展名与 MIME、写盘前做路径归一化校验以防御将来绕过框架消毒的实现变更。

**异议或降级说明。** 代码事实无误：app/ydata/views.py:78-82 确实把 f.name 拼进 local_name 并 open() 写盘，无自有校验。但 f.name 来自 req.FILES['single_file']，即 Django 上传框架产出的 UploadedFile；自 Django 1.0 起 UploadedFile._set_name 会对文件名做 os.path.basename 消毒（"Just use the basename of the file -- anything else is dangerous"），'../../../settings.py' 到达视图前已变为 'settings.py'，绝对路径同理只剩末段。本项目 lib/ 未捆绑 Django（仅 markdown、django_xmlrpc），代码使用 django.conf.urls.defaults / django.views.generic.simple 等表明运行时为 Django 1.3–1.5，均含该消毒。因此"路径穿越→任意路径写→RCE"的主线不可达；且 local_name 前缀含 id 与 req.user.id，攻击者也无法借文件名构造覆盖他人附件。残余问题（未限制扩展名、附件在 DEBUG 静态服务下同源提供 .html）属另一性质，已用 note_gap 指出。按所述机制 dispute，残余风险最多 low。（建议严重性：low）

**判定历史。**

- 复核员否决：代码事实无误：app/ydata/views.py:78-82 确实把 f.name 拼进 local_name 并 open() 写盘，无自有校验。但 f.name 来自 req.FILES['single_file']，即 Django 上传框架产出的 UploadedFile；自 Django 1.0 起 UploadedFile._set_name 会对文件名做 os.path.basename 消毒（"Just use the basename of the file -- anything else is dangerous"），'../../../settings.py' 到达视图前已变为 'settings.py'，绝对路径同理只剩末段。本项目 lib/ 未捆绑 Django（仅 markdown、django_xmlrpc），代码使用 django.conf.urls.defaults / django.views.generic.simple 等表明运行时为 Django 1.3–1.5，均含该消毒。因此"路径穿越→任意路径写→RCE"的主线不可达；且 local_name 前缀含 id 与 req.user.id，攻击者也无法借文件名构造覆盖他人附件。残余问题（未限制扩展名、附件在 DEBUG 静态服务下同源提供 .html）属另一性质，已用 note_gap 指出。按所述机制 dispute，残余风险最多 low。（建议严重性：low）
- 状态 disputed → rejected

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

## 未完成判断的候选

无。

## 范围

覆盖了 settings.py、根路由与全部 app 的 urls/views（home/account/admin/wiki/ydata/bbs/blog/me/ylab）、自定义 session/account 中间件与后端、表单与模型（account/ydata）、XML-RPC 库（django_xmlrpc、ylinux_xmlrpc）、模板中的 |safe 输出点与上传/下载路径、脚本目录（client）。未覆盖：lib/markdown 子模块（空目录）、静态前端 JS 的具体行为、部署侧配置。

## 局限

静态审计无法证明实际部署环境（Web 服务器、目录权限、进程运行用户）与运行配置（SESSION_ENGINE 未在仓库中设置，实际使用的会话后端无法确定；Django 框架本身不在仓库中，其上传文件名消毒等行为依据其公开源码与版本特征判断）；lib/markdown 为未初始化的子模块，其具体版本行为未验证；未做动态验证，XSS、重置密钥枚举等利用成功率依赖部署细节；生产环境的 HTTPS、反向代理、防火墙等外部防护不在仓库内可见。

## 复核意见

已逐条重读 13 条发现的全部证据窗口（含前后文）。结论：agree 11 条——XSS-001（none/markdown 分支确无 safe_mode、ylinux_text_filter 不转义、模板 |safe、Cookie 无 HttpOnly，均逐行确认）；ACCESS-001（editPostAJAX 确无属主校验，与 del_post 对照明确）；CRYPTO-001（2^20 密钥空间属实，但"离线枚举"措辞不精确，实际需在线逐个验证候选 key，结论不变）；CSRF-001（无 CsrfViewMiddleware 且 manage_topic 等 GET 可触发）；ACCESS-003、CONFIG-001/002/003、CRYPTO-002、REDIRECT-001、DESER-001（前提标注诚实，定级恰当）。dispute 2 条：①FILE-001——f.name 经 Django UploadedFile 的 os.path.basename 消毒（项目运行时为 Django 1.3–1.5，lib 未捆绑 Django），../ 与绝对路径在到达视图前已被剥掉，"路径穿越→任意写→RCE"主线不可达，建议降为 low，其残余问题（无扩展名白名单的附件经 DEBUG 静态服务同源提供）已记为缺口 G1；②ACCESS-002——事实链成立，但任意注册账号即可 delete_all_topic 清空全站，medium 明显偏低，建议升 high。仍存疑：CRYPTO-001 的在线爆破在实际部署中的可行性取决于有无前置限流（代码内未见）；DESER-001 的实际利用依赖会话存储写入面，目前库内未发现直接 SQL 注入入口。

## 复核缺口

- `G1`（已回应）遗漏的同源存储型 XSS 向量：app/ydata/views.py:78-88 上传附件不校验扩展名/Content-Type，文件以原始内容落盘在 MEDIA_ROOT 下；urls.py:59-62 在 DEBUG 下用 django.views.static.serve 直接以 mimetypes 猜测的类型提供 /ymedia/ 内容且不加 Content-Disposition，登录用户上传 .html/.svg 附件后诱导他人访问对应 /ymedia/ydata/attachments/<id>-<uid>-x.html 即在站点源上执行脚本。这与 FILE-001 的路径穿越无关（穿越已被 Django basename 消毒阻断），也与正文 XSS-001 不同，应单独评估。另外 app/ydata/views.py:91-95 上传响应把 attachment.name 未转义插入 <script>AfterSubmit("...") 字符串，文件名含引号时可注入 JS（主要影响上传者本人，次要）。
  - 审计员回应：已重读 settings.py:14-22（DEBUG=True 硬编码）、urls.py:45-64（DEBUG 下 /ymedia/(?P<path>.*) 挂到 django.views.static.serve，show_indexes=True，无附加 Content-Disposition/类型限制）、app/ydata/views.py:30-99（上传逻辑与 AfterSubmit 响应）并用 search_code 交叉定位（urls.py:61-62、ydata/views.py:40/78-84/91、ydata/settings.py:65）。处理结果：①FILE-001 改判 rejected——Django 上传框架在构造 UploadedFile 时对 multipart filename 做 os.path.basename 消毒，f.name 到达视图时已无 ../ 与绝对路径分量，路径穿越→任意写不可达；②新增 XSS-002（confirmed，medium，CWE-434）：上传不校验扩展名/MIME，内容原样写入 MEDIA_ROOT/ydata/attachments/<id>-<uid>-<f.name>（ydata/views.py:78-84、ydata/settings.py:65），DEBUG=True（settings.py:18）时该目录经 /ymedia/ 静态路由（urls.py:59-62）按扩展名猜测的 Content-Type 提供且无 Content-Disposition，登录用户上传 .html 后诱导他人访问对应 URL 即在站点源执行脚本（同源存储型 XSS）；③ydata/views.py:91-95 把 attachment.name 未转义插入 AfterSubmit JS 字符串的反射注入已并入 XSS-002 的 data_flow/修复建议，因其只反射给上传者本人，不单独立项。

## 运行警告

- run interrupted: Error code: 429 - {'error': {'message': 'Your credit balance is running low for account <org-<redacted>>, please recharge immediately to avoid service disruption', 'type': 'exceeded_current_quota_error'}}
