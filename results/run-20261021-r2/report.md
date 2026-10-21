# ylinux_old 应用安全审计报告

- 目标：`https://github.com/gwind/ylinux_old`，commit `8a7316deec88287d020eca21c38dad921b623ffc`
- 模型：审计员 `deepseek-v4-pro`，复核员 `deepseek-v4-pro`
- 时间：2026-10-21T09:28:29+08:00 → 2026-10-21T09:41:06+08:00
- 结论：确认 12 个问题，最高严重性为 high。
- 统计：已确认 12，待再确认 0，已排除 0；引用核对 39 条，未通过 0 条

## 发现总表

| 严重性 | 编号 | 问题 | 入口身份 | 状态 | 复核员 | 位置 |
| --- | --- | --- | --- | --- | --- | --- |
| high | [`ACL-001`](#finding-acl-001) | XML-RPC 写接口只有认证没有授权：任意注册用户可删除/篡改全站主题 | 可自助注册的用户 | confirmed | 同意 | `lib/ylinux_xmlrpc.py:39` |
| high | [`FILE-001`](#finding-file-001) | 附件上传文件名路径穿越，可向 MEDIA_ROOT 任意位置写文件 | 可自助注册的用户 | confirmed | 同意 | `app/ydata/views.py:31` |
| high | [`XSS-001`](#finding-xss-001) | 主题/回复正文 Markdown 渲染未启用 safe_mode，存储型 XSS | 可自助注册的用户 | confirmed | 同意 | `app/ydata/models.py:198` |
| medium | [`ACL-002`](#finding-acl-002) | editPostAJAX 缺少属主校验：任意登录用户可编辑他人帖子 | 可自助注册的用户 | confirmed | 同意 | `app/wiki/views.py:447` |
| medium | [`CONFIG-001`](#finding-config-001) | DEBUG=True 且 /ymedia/ 静态目录带目录列举暴露在生产 | 无请求入口 | confirmed | 同意 | `settings.py:18` |
| medium | [`CONFIG-002`](#finding-config-002) | SECRET_KEY 与数据库口令硬编码提交进仓库 | 无请求入口 | confirmed | 同意 | `settings.py:42` |
| medium | [`CRYPTO-001`](#finding-crypto-001) | 口令使用无迭代 SHA1 + 5 字符弱盐存储 | 无请求入口 | confirmed | 同意 | `app/account/models.py:62` |
| medium | [`CRYPTO-002`](#finding-crypto-002) | 密码重置/激活 key 熵仅 20 位，可在线爆破接管账号 | 匿名 | confirmed | 同意 | `app/account/models.py:361` |
| medium | [`CSRF-001`](#finding-csrf-001) | 全站缺少 CSRF 防护，删除/重启等敏感操作可用 GET 跨站触发 | 可自助注册的用户 | confirmed | 同意 | `settings.py:98` |
| medium | [`XSS-002`](#finding-xss-002) | 注册/密码重置 key 参数反射型 XSS（匿名可达） | 匿名 | confirmed | 同意 | `app/account/views.py:96` |
| low | [`LAB-001`](#finding-lab-001) | lab 调试端点未授权暴露：匿名批量改写帖子与测试上传 | 匿名 | confirmed | 同意 | `app/ylab/urls.py:5` |
| low | [`REDIR-001`](#finding-redir-001) | logout/login 的 next 与 admin Referer 重定向未校验（开放重定向） | 匿名 | confirmed | 同意 | `app/account/views.py:55` |

下面的发现由 Agent 写入，每条引用都回到源码核对过。审计员综述写在复核之前，单条发现的状态以复核后为准。线索处置、读过的文件、阶段记录、工具序列和引用核对见 `appendix.md`，关键决策见 `decisions.md`。

## 审计员综述

这是一个老式 Django（django.conf.urls.defaults 时代）论坛/Wiki/博客系统。整体安全基线很弱：内容渲染（lib/markdown 2.0.3）在主题与回复正文上未启用 safe_mode，模板用 |safe 输出，导致任何注册用户可写存储型 XSS（高危）；附件上传直接用客户端文件名拼路径，可穿越到 MEDIA_ROOT 任意位置写文件（高危）；XML-RPC 写接口（删除全部主题/编辑任意主题）只有账号密码认证、没有授权（高危）。此外还存在无属主校验的帖子编辑越权、全站无 CSRF 中间件且删除/重启等操作 GET 可触发、注册/重置 key 反射 XSS、开放重定向、弱口令哈希（无迭代 SHA1 + 5 字符盐）、激活/重置 key 仅 20 位熵可在线爆破接管账号、硬编码的 SECRET_KEY/DB 口令、DEBUG=True 加目录列举、以及匿名可达的 lab 调试端点。

## 风险概览

最高风险三条：1) 存储型 XSS（XSS-001）+ 附件路径穿越（FILE-001）组合可让自助注册的账号把任意脚本持久注入站点页面并覆盖他人主题文件；2) XML-RPC 未授权写操作（ACL-001）允许任意注册用户一键删除全站主题；3) 密码重置 key 20 位熵（CRYPTO-002）可在线爆破接管任意账号。此外全站无 CSRF 防护（CSRF-001）使管理员会话可被跨站利用触发 /admin/reboot/ 等破坏性操作，SECRET_KEY/DB 口令与 DEBUG=True 的公开使整体纵深防御失效。

## 已确认的问题

<a id="finding-acl-001"></a>

### [HIGH] XML-RPC 写接口只有认证没有授权：任意注册用户可删除/篡改全站主题

- 编号：`ACL-001`
- 类别：`access_control`
- CWE：`CWE-862`
- 入口身份：可自助注册的用户
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

XML-RPC 的 delete_topic/delete_all_topic/edit_topic 只调用 has_auth 校验账号密码，没有任何权限或属主检查，任何注册账号都能删除/篡改全站任意主题。

**触发条件。** 向 /xmlrpc/ POST 调用 metaWeblog.editPost / delete_topic / delete_all_topic，传入自己的用户名密码与目标主题 id。

**数据流。** 来源：XML-RPC 请求参数 id/postid/user/passwd（lib/django_xmlrpc/views.py:87 _marshaled_dispatch 解析请求体）→ 中间：has_auth(user,passwd) 只校验账号密码（lib/ylinux_xmlrpc.py:39-45），不做任何权限/属主判断 → 危险点：delete_topic 直接 Topic.objects.get(pk=id).delete()（:52-56）、delete_all_topic 全表删除（:66）、edit_topic 修改任意主题 name/body（:173-181）。入口身份：任何已注册账号（含攻击者自助注册的账号）。

**影响。** 任何注册用户可通过 XML-RPC 删除任意主题、一键删除全部主题（delete_all_topic）、篡改任意主题的标题与正文（可借正文 XSS 注入脚本），造成全站内容丢失与持久脚本注入。

**修复。** 为写操作增加授权：delete/edit 校验 topic.user == 认证用户或具备对应管理权限；删除 delete_all_topic 或改为仅超级管理员可用；XML-RPC 认证叠加速率限制与权限装饰器（django_xmlrpc.permission_required）。

**复核员指出的最弱一环。** 最站不住的一环是"这些方法真的被暴露且派发层不加授权"。核实：urls.py:45-48 注册 r'^xmlrpc/$' → django_xmlrpc.views.handle_xmlrpc（views.py:73-92，仅 POST 后 _marshaled_dispatch）；lib/django_xmlrpc/dispatcher.py 继承 SimpleXMLRPCDispatcher，无任何权限层；settings.py:164-174 注册了 delete_topic/delete_all_topic/edit_topic；lib/ylinux_xmlrpc.py:39-69、168-185 中三个写方法仅 has_auth（只验用户名/密码），随后对任意 pk 执行 Topic.delete（52-56 行）/ 全表 Topic.objects.all().delete()（66 行）/ 覆盖 name 并 save_file（168-185 行），无属主或权限判断。逐环核实均属实。

**判定历史。**

- 复核员同意：任意注册账号（站点开放自助注册）即可删除任意/全部主题、篡改任意主题标题与正文（edit_topic 经 save_file 复用 XSS-001 的无 safe_mode 渲染链植入脚本）。认证≠授权，CWE-862，high 恰当。（最弱一环：最站不住的一环是"这些方法真的被暴露且派发层不加授权"。核实：urls.py:45-48 注册 r'^xmlrpc/$' → django_xmlrpc.views.handle_xmlrpc（views.py:73-92，仅 POST 后 _marshaled_dispatch）；lib/django_xmlrpc/dispatcher.py 继承 SimpleXMLRPCDispatcher，无任何权限层；settings.py:164-174 注册了 delete_topic/delete_all_topic/edit_topic；lib/ylinux_xmlrpc.py:39-69、168-185 中三个写方法仅 has_auth（只验用户名/密码），随后对任意 pk 执行 Topic.delete（52-56 行）/ 全表 Topic.objects.all().delete()（66 行）/ 覆盖 name 并 save_file（168-185 行），无属主或权限判断。逐环核实均属实。）

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

`lib/ylinux_xmlrpc.py:60-69`

```
def delete_all_topic(user, passwd):
    '''delete all topic'''
    if not has_auth(user, passwd):
        raise Fault(-1, "Authentication Failure")

    try:
        Topic.objects.all().delete()
        return True
```

`lib/ylinux_xmlrpc.py:168-183`

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

`settings.py:164-174`

```
XMLRPC_METHODS = (
    ('ylinux_xmlrpc.delete_topic', 'delete_topic'),
    ('ylinux_xmlrpc.delete_all_topic', 'delete_all_topic'),

    # MetaWebBlog API
    ('ylinux_xmlrpc.new_topic', 'metaWeblog.newPost'),
    ('ylinux_xmlrpc.new_media', 'metaWeblog.newMediaObject'),
    ('ylinux_xmlrpc.edit_topic', 'metaWeblog.editPost'),
    ('ylinux_xmlrpc.get_topic', 'metaWeblog.getPost'),
```

<a id="finding-file-001"></a>

### [HIGH] 附件上传文件名路径穿越，可向 MEDIA_ROOT 任意位置写文件

- 编号：`FILE-001`
- 类别：`file_access`
- CWE：`CWE-22`
- 入口身份：可自助注册的用户
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

附件上传把客户端提供的文件名 f.name 直接拼进保存路径，文件名中的 ../ 可穿越 ATTACHMENT_UPLOAD_TO 目录，向 MEDIA_ROOT 任意位置写入任意内容（登录用户即可）。

**触发条件。** 注册用户 POST multipart 表单到 /ydata/uploadsf/<id>/，文件名字段形如 ../../topics/8.html 或 ../../../../x.html。

**数据流。** 来源：multipart 上传的文件名 f.name（app/ydata/views.py:40 req.FILES['single_file']）→ 中间：local_name = str(id)+'-'+str(req.user.id)+'-'+f.name（:78，文件名未经清洗，可含 ../）→ 危险点：save_path = os.path.join(MEDIA_ROOT, ATTACHMENT_UPLOAD_TO, local_name) 后 open(save_path,'wb+') 写入（:79-82）。入口身份：@login_required，任何自助注册用户。

**影响。** 攻击者可把文件写到 MEDIA_ROOT 下任意位置：覆盖其他用户的附件；把文件名指向 ymedia/ydata/topics/<id>.html 覆盖任意主题的 HTML（植入持久脚本）；或在 /ymedia/ 下放置 .html 文件，由于 DEBUG=True 时 /ymedia/ 由 django.views.static.serve 直接以原 mimetype 提供，形成同源存储型 XSS。

**修复。** 不要使用客户端文件名拼路径：用 os.path.basename 去掉路径成分、白名单校验后缀/字符集，或者用随机文件名保存并把原始名仅作为显示字段；对 MEDIA_ROOT 下文件用 Content-Disposition: attachment 且强制安全 Content-Type。

**复核员指出的最弱一环。** 最站不住的一环是"os.path.join 是否真能被 ../ 穿越"。核实 app/ydata/views.py:31-84：从 req.FILES['single_file'] 取到的 f.name 是客户端 multipart 文件名（Django UploadedFile.name 不做路径清洗），第 78 行直接拼进 local_name，79-81 行与 MEDIA_ROOT/'ydata/attachments' 做 os.path.join 后 open('wb+')，中间没有任何 basename/白名单/字符校验。os.path.join 不规范化路径，'../' 段交由 OS 解析到上级目录（如 f.name='../../topics/8.html' 落到 ymedia/ydata/topics/8.html），穿越成立。

**判定历史。**

- 复核员同意：入口 @login_required（views.py:31-32），任何自助注册用户即可触发；可向 MEDIA_ROOT 任意位置写入任意内容：覆盖主题 HTML（topic 页以 |safe 渲染 body_html）或放置 .html，DEBUG 下 /ymedia/ 由 static.serve 按原 mimetype 提供（urls.py:59-63），形成同源持久 XSS。high 恰当。（最弱一环：最站不住的一环是"os.path.join 是否真能被 ../ 穿越"。核实 app/ydata/views.py:31-84：从 req.FILES['single_file'] 取到的 f.name 是客户端 multipart 文件名（Django UploadedFile.name 不做路径清洗），第 78 行直接拼进 local_name，79-81 行与 MEDIA_ROOT/'ydata/attachments' 做 os.path.join 后 open('wb+')，中间没有任何 basename/白名单/字符校验。os.path.join 不规范化路径，'../' 段交由 OS 解析到上级目录（如 f.name='../../topics/8.html' 落到 ymedia/ydata/topics/8.html），穿越成立。）

**证据。**

`app/ydata/views.py:31-40`

```
@login_required
def upload_single_file(req, id):
    ''' 上传单个附件， 只作异步上传使用
    1. 上传的 form 中文件的 name = 'single_file'
    '''

    if req.method != 'POST':
        return HttpResponse("Just for POST a single file")

    f = req.FILES['single_file'] #req.FILES.values()[0]
```

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

<a id="finding-xss-001"></a>

### [HIGH] 主题/回复正文 Markdown 渲染未启用 safe_mode，存储型 XSS

- 编号：`XSS-001`
- 类别：`xss`
- CWE：`CWE-79`
- 入口身份：可自助注册的用户
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

主题正文（Topic.save_file）和回复正文（Post.save 的 markup='none' 分支）用自带 lib/markdown 2.0.3 转换 HTML 时都没有传入 safe_mode，RawHtmlPostprocessor 在 safeMode 为假时会把用户输入的原始 HTML 原样还原进输出；模板又用 |safe 输出 body_html，任何注册用户都能在正文里放任意 HTML/JavaScript，对浏览 wiki/bbs 主题页的所有访客（含管理员）执行。

**触发条件。** 注册用户 POST 到 /wiki/catalog/<id>/addtopic/、/wiki/topic/<id>/addpost/、/wiki/topic/<id>/replayAJAX/ 或 /wiki/post/<id>/editAJAX/，正文含原始 HTML。

**数据流。** 来源：POST 参数 text/body（app/wiki/views.py add_topic:197、replayAJAX:432、editPostAJAX:456；app/ydata/forms.py AddTopicForm.save:97、AddPostForm.save:46 固定 markup='none'）→ 中间：Topic.save_file / Post.save 用 Markdown 不带 safe_mode 转换（app/ydata/models.py:198-200、:258-260）→ lib/markdown/postprocessors.py:54 在 safeMode 为假时原样还原原始 HTML 写入 body_html → 危险点：templates/wiki/topic.html:54 {{ topic.body_html|safe }}、app/wiki/utils.py:18 {{ post.body_html|safe }}（render_post 用于 wiki/bbs 页面与 ajax_show_posts 的 HttpResponse）。入口身份：任何可自助注册并激活邮箱的用户。

**影响。** 攻击者注册账号后在主题/回复中写入 <script> 等原始 HTML，浏览 /wiki/topic/<id>/、/bbs/topic/<id>/、RSS 及 AJAX 帖子接口的每个访客（含管理员会话）都会被注入脚本，可窃取会话 Cookie、冒充发帖或以管理员身份执行后台操作。

**修复。** 对 Topic 的 convertFile 与 Post 的 markup='none' 转换都启用 safe_mode='escape'（与 Post 的 markdown 分支一致）；对 ylinux_text_filter 拼进 HTML 的附件名/主题名做 html 转义；并优先对渲染层做白名单消毒（如 bleach）。

**复核员指出的最弱一环。** 最站不住的一环是"不带 safe_mode 就必然原样还原用户 HTML"这条因果链。我核实了：lib/markdown/__init__.py:185-212 中 Markdown.__init__ 默认 safe_mode=False；preprocessors.py:56-75 的 HtmlStash.store(html, safe=False) 把原始 HTML 块存进 rawHtmlBlocks；postprocessors.py:43-60 在 "safe or not self.markdown.safeMode" 时把占位符原样替换回 HTML——因果成立。同时确认 ylinux_text_filter（app/ydata/models.py:396-452）只替换 [附件:ID]/[WIKI:ID]/[IMG:ID] 引用，不做任何 HTML 转义，不能充当消毒器。

**判定历史。**

- 复核员同意：来源核实：add_topic 仅 @login_required（wiki/views.py:183-201）、AddPostForm.save 固定 markup='none'（ydata/forms.py:46）、replayAJAX 固定 markup='none'（wiki/views.py:432-436），均为注册用户可控文本；Topic.save_file（models.py:198-200）与 Post.save 的 markup='none' 分支（models.py:258-260）都调用 Markdown() 不带 safe_mode（对照 256 行 markdown 分支确实传了 safe_mode='escape'，说明这是遗漏而非设计）；危险点 templates/wiki/topic.html:54 和 app/wiki/utils.py:18 均 |safe 输出，wiki/bbs/AJAX 页面共用 render_post。存储型 XSS 全链路成立，high 恰当。（最弱一环：最站不住的一环是"不带 safe_mode 就必然原样还原用户 HTML"这条因果链。我核实了：lib/markdown/__init__.py:185-212 中 Markdown.__init__ 默认 safe_mode=False；preprocessors.py:56-75 的 HtmlStash.store(html, safe=False) 把原始 HTML 块存进 rawHtmlBlocks；postprocessors.py:43-60 在 "safe or not self.markdown.safeMode" 时把占位符原样替换回 HTML——因果成立。同时确认 ylinux_text_filter（app/ydata/models.py:396-452）只替换 [附件:ID]/[WIKI:ID]/[IMG:ID] 引用，不做任何 HTML 转义，不能充当消毒器。）

**证据。**

`app/ydata/models.py:198-200`

```
        Markdown(extensions=['fenced_code']).convertFile(input=self.body_path, 
                       output=self.body_html_path, 
                       encoding="utf8", myfilter=ylinux_text_filter)
```

`app/ydata/models.py:258-260`

```
        elif self.markup == 'none':
            #self.body_html = self.body
            self.body_html = Markdown(extensions=['fenced_code']).convert(ylinux_text_filter(self.body))
```

`lib/markdown/postprocessors.py:43-55`

```
    def run(self, text):
        """ Iterate over html stash and restore "safe" html. """
        for i in range(self.markdown.htmlStash.html_counter):
            html, safe  = self.markdown.htmlStash.rawHtmlBlocks[i]
            if self.markdown.safeMode and not safe:
                if str(self.markdown.safeMode).lower() == 'escape':
                    html = self.escape(html)
                elif str(self.markdown.safeMode).lower() == 'remove':
                    html = ''
                else:
                    html = markdown.HTML_REMOVED_TEXT
            if safe or not self.markdown.safeMode:
                text = text.replace("<p>%s</p>" %
```

`templates/wiki/topic.html:53-55`

```
  <div class="topic-body content">
    {{ topic.body_html|safe }}
  </div>
```

`app/wiki/utils.py:17-19`

```
<div class="post-body">
  <p>{{ post.body_html|safe }}</p>
</div>
```

`app/wiki/views.py:432-436`

```
        post_body = request.POST.get("body", None)
        if len(post_body) < 2:
            return {'error': u'您的回复太短，至少2个字符！'}
        post = Post(topic = topic, user = request.user, user_ip = ip, markup = 'none', body = post_body, parent = parent_post)
        post.save()
```

<a id="finding-acl-002"></a>

### [MEDIUM] editPostAJAX 缺少属主校验：任意登录用户可编辑他人帖子

- 编号：`ACL-002`
- 类别：`access_control`
- CWE：`CWE-639`
- 入口身份：可自助注册的用户
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

wiki.editPostAJAX 只用 @login_required 保护，按 postID 取出帖子后不做属主校验即覆盖正文，任何登录用户都能编辑任意用户的帖子（越权编辑）。

**触发条件。** 登录用户 POST 到 /wiki/post/<postID>/editAJAX/，body 为任意内容。

**数据流。** 来源：POST 参数 body 与 URL 参数 postID（app/wiki/views.py:456、:449）→ 中间：post = get_object_or_404(Post, pk=postID)（:451），仅 @login_required、从不比较 post.user 与 request.user（对照同文件 manage_topic:242、del_post:277 都做了属主检查）→ 危险点：post.body = post_body; post.save()（:459-460）覆盖任意帖子的内容。入口身份：任何自助注册用户。

**影响。** 任何注册用户可批量改写他人（含管理员）的任意帖子正文；结合正文 XSS（markup='none' 时渲染不消毒）可在他人帖子中植入持久脚本；也可用于诽谤式篡改内容。

**修复。** 在 editPostAJAX 中校验 post.user == request.user（或授予编辑权限），并限制请求方法为 POST。

**复核员指出的最弱一环。** 最站不住的一环是"是否存在隐藏的属主校验"。核实 app/wiki/views.py:447-467：GET 分支仅返回渲染数据，POST 分支取 body 后直接 post.body=post_body; post.save()，全程只有 @login_required，从未比较 post.user 与 request.user；同文件 manage_topic:242 与 del_post:277 均做了属主检查，证明此处是遗漏而非设计。模板里的"仅属主显示编辑按钮"只是客户端隐藏，不构成服务端授权。

**判定历史。**

- 复核员同意：任意登录用户 POST /wiki/post/<id>/editAJAX/ 即可覆盖任意他人（含管理员）帖子正文，且被改帖子仍沿 markup='none' 渲染链输出，可植入持久脚本。CWE-639，medium 恰当。（最弱一环：最站不住的一环是"是否存在隐藏的属主校验"。核实 app/wiki/views.py:447-467：GET 分支仅返回渲染数据，POST 分支取 body 后直接 post.body=post_body; post.save()，全程只有 @login_required，从未比较 post.user 与 request.user；同文件 manage_topic:242 与 del_post:277 均做了属主检查，证明此处是遗漏而非设计。模板里的"仅属主显示编辑按钮"只是客户端隐藏，不构成服务端授权。）

**证据。**

`app/wiki/views.py:447-452`

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

<a id="finding-config-001"></a>

### [MEDIUM] DEBUG=True 且 /ymedia/ 静态目录带目录列举暴露在生产

- 编号：`CONFIG-001`
- 类别：`config`
- CWE：`CWE-215`
- 入口身份：无请求入口
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

settings.py 硬编码 DEBUG=True；urls.py 在 DEBUG 下用 django.views.static.serve 以 show_indexes=True 暴露整个 MEDIA_ROOT（含附件目录）并可列目录。

**触发条件。** 任何未处理异常页面回显调试信息；直接访问 /ymedia/ydata/attachments/ 等路径浏览目录与文件。

**影响。** 生产环境开启 DEBUG 会向访客回显完整堆栈、设置、局部变量与 SQL，泄露路径/密钥相关信息；同时 urls.py 依据 DEBUG 挂载 /ymedia/ 静态服务并开启目录列举，附件目录、上传文件（含攻击者写入的 HTML）可直接浏览与执行。

**修复。** 生产环境设置 DEBUG=False；静态文件交给 Web 服务器并关闭目录列举；对上传目录强制 Content-Disposition 与安全 Content-Type。

**复核员指出的最弱一环。** 最站不住的一环是"是否真的暴露在生产"。核实 settings.py:18-20 硬编码 DEBUG=True（仓库内无生产覆写），urls.py:59-63 依据 DEBUG 挂载 django.views.static.serve(document_root=MEDIA_ROOT, show_indexes=True)。只要按仓库配置运行（无论是否"生产"），/ymedia/ 即带目录列举、上传文件按原 mimetype 直接提供，未捕获异常还会回显完整调试页（泄露路径、SQL、局部变量）。配置确实生效。

**判定历史。**

- 复核员同意：信息泄露 + 附件目录浏览 + 上传内容同源直出，与 FILE-001 形成叠加；CWE-215，medium 恰当。（最弱一环：最站不住的一环是"是否真的暴露在生产"。核实 settings.py:18-20 硬编码 DEBUG=True（仓库内无生产覆写），urls.py:59-63 依据 DEBUG 挂载 django.views.static.serve(document_root=MEDIA_ROOT, show_indexes=True)。只要按仓库配置运行（无论是否"生产"），/ymedia/ 即带目录列举、上传文件按原 mimetype 直接提供，未捕获异常还会回显完整调试页（泄露路径、SQL、局部变量）。配置确实生效。）

**证据。**

`settings.py:18-20`

```
DEBUG = True
TEMPLATE_DEBUG = DEBUG
DOMAIN = "127.0.0.1:8000"
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

### [MEDIUM] SECRET_KEY 与数据库口令硬编码提交进仓库

- 编号：`CONFIG-002`
- 类别：`config`
- CWE：`CWE-798`
- 入口身份：无请求入口
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

SECRET_KEY 与数据库口令硬编码并提交进代码仓库（公开仓库），任何获得仓库内容的人都知道这些机密。

**触发条件。** 代码仓库公开可读（上游为公开 GitHub 仓库），settings.py 第 46-49 行含 DB 口令、第 79 行含 SECRET_KEY。

**影响。** SECRET_KEY 公开后：密码重置 token 的哈希输入（app/account/tokens.py:54）可由持有者复算，一旦再获得某用户的口令哈希与 last_login 即可伪造重置 token；会话数据的完整性校验（app/sessions/models.py:63）依赖同一密钥。数据库口令入库则让拿到仓库/备份的攻击者直接连接数据库读取全部数据。

**修复。** 从仓库移除真实密钥与口令，改为环境变量/密钥管理系统注入；轮换 SECRET_KEY 与数据库口令；重置 token 改用服务端随机一次性令牌。

**复核员指出的最弱一环。** 最站不住的一环是"DB 口令泄露导致直连数据库"这一半影响。核实 settings.py:42-49：ENGINE 为 django.db.backends.sqlite3，sqlite 不使用 USER/PASSWORD，'123456' 在本地 sqlite 下根本不参与认证——该影响只有在其被注释掉的 mysql 引擎启用时才成立。但 SECRET_KEY（settings.py:79）硬编码入库是实的：app/sessions/models.py 的会话完整性 MD5(pickled+SECRET_KEY)、app/account/tokens.py:54 的重置 token SHA1(SECRET_KEY+...) 均以它为输入，密钥公开使这些机制失去保密前提。

**判定历史。**

- 复核员同意：核心主张（真实机密提交进公开仓库）成立，基于 SECRET_KEY 暴露的影响维持 medium；DB 口令部分对 sqlite 属无效配置，影响仅在切换 mysql 后端时成立，已在 weakest_point 中注明。（最弱一环：最站不住的一环是"DB 口令泄露导致直连数据库"这一半影响。核实 settings.py:42-49：ENGINE 为 django.db.backends.sqlite3，sqlite 不使用 USER/PASSWORD，'123456' 在本地 sqlite 下根本不参与认证——该影响只有在其被注释掉的 mysql 引擎启用时才成立。但 SECRET_KEY（settings.py:79）硬编码入库是实的：app/sessions/models.py 的会话完整性 MD5(pickled+SECRET_KEY)、app/account/tokens.py:54 的重置 token SHA1(SECRET_KEY+...) 均以它为输入，密钥公开使这些机制失去保密前提。）

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

`settings.py:78-79`

```
# Make this unique, and don't share it with anybody.
SECRET_KEY = 'c#0cz^i$lyr6*b*xe-t@0tqc_c3dnju=+c1lk^k7(r^7lhz$g@'
```

<a id="finding-crypto-001"></a>

### [MEDIUM] 口令使用无迭代 SHA1 + 5 字符弱盐存储

- 编号：`CRYPTO-001`
- 类别：`crypto`
- CWE：`CWE-916`
- 入口身份：无请求入口
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

口令存储为单轮 SHA1（旧格式支持无盐 MD5），盐由 random.random() 派生并截取 5 个十六进制字符，无迭代因子，抗离线破解能力很弱；登录接口也没有速率限制。

**触发条件。** 数据库泄露或备份外流时（settings.py 中明文 DB 口令使风险更高），攻击者对 password 字段离线破解。

**影响。** 口令哈希无迭代、盐仅 5 个十六进制字符（20 位熵），单轮 SHA1 极易被 GPU/彩虹表离线破解；一旦数据库泄露（本仓库还同时泄露了 DB 口令），大量账号口令可在短时间内恢复。

**修复。** 迁移到强口令哈希：bcrypt/argon2/PBKDF2（如 Django 的 make_password/check_password），保留旧哈希的升级迁移；登录增加速率限制。

**复核员指出的最弱一环。** 最站不住的一环是严重性是否偏高——它确实以数据库泄露为前提。核实 app/account/models.py:62-66（md5/sha1 单轮、无迭代）、228-234（盐 = get_hexdigest('sha1', str(random.random()), str(random.random()))[:5]，即 5 个十六进制字符 ≈20 位熵）、241-250（兼容无盐 MD5）。单轮 SHA1 + 20 位盐的离线抗破解能力弱是事实，CWE-916 成立；结合本仓库 DB/SECRET_KEY 泄露场景（CONFIG-002），medium 恰当，不算偏高。

**判定历史。**

- 复核员同意：口令存储方案无迭代因子、盐空间仅 16^5，数据库泄露后 GPU/彩虹表可在极短时间内恢复大量弱口令；旧格式无盐 MD5 更弱。登录接口无速率限制（remediation 已提及）。medium 恰当。（最弱一环：最站不住的一环是严重性是否偏高——它确实以数据库泄露为前提。核实 app/account/models.py:62-66（md5/sha1 单轮、无迭代）、228-234（盐 = get_hexdigest('sha1', str(random.random()), str(random.random()))[:5]，即 5 个十六进制字符 ≈20 位熵）、241-250（兼容无盐 MD5）。单轮 SHA1 + 20 位盐的离线抗破解能力弱是事实，CWE-916 成立；结合本仓库 DB/SECRET_KEY 泄露场景（CONFIG-002），medium 恰当，不算偏高。）

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

`app/account/models.py:241-250`

```
        # Backwards-compatibility check. Older passwords won't include the
        # algorithm or salt.
        if '$' not in self.password:
            is_correct = (self.password == get_hexdigest('md5', '', raw_password))
            if is_correct:
                # Convert the password to the new, more secure format.
                self.set_password(raw_password)
                self.save()
            return is_correct
        return check_password(raw_password, self.password)
```

<a id="finding-crypto-002"></a>

### [MEDIUM] 密码重置/激活 key 熵仅 20 位，可在线爆破接管账号

- 编号：`CRYPTO-002`
- 类别：`crypto`
- CWE：`CWE-330`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

注册激活码与密码重置 key 由“5 个十六进制字符的盐 + 邮箱”做 SHA1 得到，熵仅约 20 位，且密码重置接口无速率限制，可在线爆破 key 接管任意账号。

**触发条件。** 对 /account/password/reset/<key>/ 以 16^5 个候选 salt 对受害者邮箱计算 key 并逐个 GET，命中后提交新口令表单。

**数据流。** 来源：账号邮箱 email（攻击者已知的目标邮箱）→ 中间：activation_key = sha1(sha1(random.random())[:5] + email)（app/account/models.py:364-367、:427-430，盐空间仅 16^5≈1M）→ 危险点：/account/password/reset/<key>/ 用该 key 取 Register 并允许直接重设对应用户口令（app/account/views.py:205-219，无速率限制）。入口身份：匿名在线爆破。

**影响。** 知晓受害者邮箱的攻击者可枚举 2^20 个候选 key 逐个请求密码重置接口，命中后直接把受害者账号口令改为自己控制的密码，实现任意账号接管；注册激活 key 同理可被爆破。

**修复。** 激活/重置 key 改用安全随机（os.urandom/SystemRandom）生成至少 128 位熵的 token；重置流程增加限速、失败计数与短有效期；校验时使用常数时间比较。

**复核员指出的最弱一环。** 最站不住的一环是"2^20 在线爆破是否可行、是否有 oracle"。核实 app/account/models.py:361-369、424-430：key = sha1(salt+email)，salt 为 sha1(str(random.random())) 的十六进制前 5 字符，候选空间 16^5≈1,048,576；password_reset_request（views.py:167-198）匿名可为目标邮箱创建/重置 Register 行（email 需已注册为 User）；password_reset（views.py:201-223）对错误 key 返回 403（208 行）、正确 key 返回 200 表单页且提交后 form.save() 改密；无任何速率限制。oracle 与接管链路逐环成立。

**判定历史。**

- 复核员同意：知晓受害者邮箱的攻击者：先触发 password_reset_request（views.py:167-198，匿名）使 Register 行存在/重置，再枚举 1M 个候选 key 打 /account/password/reset/<key>/，正确 key 返回 200 表单页（215 行），提交后 form.save() 直接改密完成接管。需约百万请求、较嘈杂，medium 恰当。（最弱一环：最站不住的一环是"2^20 在线爆破是否可行、是否有 oracle"。核实 app/account/models.py:361-369、424-430：key = sha1(salt+email)，salt 为 sha1(str(random.random())) 的十六进制前 5 字符，候选空间 16^5≈1,048,576；password_reset_request（views.py:167-198）匿名可为目标邮箱创建/重置 Register 行（email 需已注册为 User）；password_reset（views.py:201-223）对错误 key 返回 403（208 行）、正确 key 返回 200 表单页且提交后 form.save() 改密；无任何速率限制。oracle 与接管链路逐环成立。）

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

<a id="finding-csrf-001"></a>

### [MEDIUM] 全站缺少 CSRF 防护，删除/重启等敏感操作可用 GET 跨站触发

- 编号：`CSRF-001`
- 类别：`csrf`
- CWE：`CWE-352`
- 入口身份：可自助注册的用户
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

全站未启用 CSRF 中间件，且删除主题、重启等破坏性操作通过 GET 即可触发：跨站请求可借登录用户（含管理员）会话执行任意状态变更。

**触发条件。** 受害者已登录（普通用户或后台管理员），访问攻击者页面中指向 /wiki/topic/<id>/delete/、/admin/reboot/、/account/login/（登录态固定）等 URL 的跨站请求。

**数据流。** 配置层问题：settings.py MIDDLEWARE_CLASSES 只含 CommonMiddleware、自定义 Session/Auth 中间件，没有 CsrfViewMiddleware（app/sessions、app/account 中间件均无 token 校验）。后果链路：敏感写操作不校验方法与 CSRF token —— admin/urls.py:50 的 /admin/reboot/ 与 wiki/urls.py:34-38 的删除/隐藏主题路由都是 GET 触发的状态变更（admin/views.py reboot:358-365、wiki/views.py manage_topic:237-268 无 request.method 检查），浏览器跨站 <img>/<form> 即可替登录用户执行。

**影响。** 攻击者诱导登录用户访问恶意页面即可：以受害者身份删除/隐藏其主题与帖子、发帖（replayAJAX/add_post）、上传附件；若受害者是有 ydata.delete_catalog 等权限的管理员，还能跨站触发 /admin/reboot/（killall 杀掉进程）、/admin/user/<id>/del、/admin/catalog/<id>/del 等破坏性操作。

**修复。** 启用 django.middleware.csrf.CsrfViewMiddleware 并在所有写表单/视图使用 csrf_token（XML-RPC 入口除外）；所有状态变更视图只接受 POST；不要用 GET 链接执行删除/重启。

**复核员指出的最弱一环。** 最站不住的一环是"自定义 Session/Auth 中间件是否可能暗含 CSRF 校验"。核实 settings.py:98-104：MIDDLEWARE_CLASSES 仅 CommonMiddleware + ylinux.app.sessions.middleware.SessionMiddleware + ylinux.app.account.middleware.AuthenticationMiddleware，无 CsrfViewMiddleware；通读两个自定义中间件（app/sessions/middleware.py:8-42、app/account/middleware.py:15-21），只有会话存取与 LazyUser 注入，无 token/Origin/Referer 校验——全站确实无 CSRF 防护。

**判定历史。**

- 复核员同意：危险链路核实：wiki/urls.py:34-38 删除/隐藏/回收站路由不限制方法，manage_topic（wiki/views.py:237-268）无 request.method 检查（属主检查在 CSRF 场景下不构成防御，受害者恰是属主）；admin/urls.py:50 /admin/reboot/ → admin/views.py:358-365，permission_required（account/decorators.py:34-39 仅查 has_perm）后 GET 即执行 killall。跨站 <img>/<form> 可借登录用户（含管理员）会话执行状态变更。medium 恰当。（最弱一环：最站不住的一环是"自定义 Session/Auth 中间件是否可能暗含 CSRF 校验"。核实 settings.py:98-104：MIDDLEWARE_CLASSES 仅 CommonMiddleware + ylinux.app.sessions.middleware.SessionMiddleware + ylinux.app.account.middleware.AuthenticationMiddleware，无 CsrfViewMiddleware；通读两个自定义中间件（app/sessions/middleware.py:8-42、app/account/middleware.py:15-21），只有会话存取与 LazyUser 注入，无 token/Origin/Referer 校验——全站确实无 CSRF 防护。）

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

`app/wiki/views.py:237-243`

```
@login_required
def manage_topic (request, id, type=None):

    topic = get_object_or_404 (Topic, pk=id)

    if topic.user != request.user:
        return HttpResponseForbidden('<h1>您没有这个权限！</h1>')
```

`app/admin/views.py:358-365`

```
@permission_required('ydata.delete_catalog')
def reboot(request):

    import os
    user=os.popen('whoami').read().strip()
    os.system('killall -u %s' % user)

    return HttpResponseRedirect(reverse('home:index'))
```

<a id="finding-xss-002"></a>

### [MEDIUM] 注册/密码重置 key 参数反射型 XSS（匿名可达）

- 编号：`XSS-002`
- 类别：`xss`
- CWE：`CWE-79`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

注册与密码重置视图把 URL 中的 key 参数未转义地拼进 HttpResponseForbidden 的 HTML，形成匿名可触发的反射型 XSS。

**触发条件。** GET /account/register/%3Cscript%3Ealert(1)%3C/script%3E/ 或 /account/password/reset/<payload>/，key 不存在即触发回显。

**数据流。** 来源：URL 路径参数 key（app/account/urls.py:8、:13 的 (?P<key>.+)）→ 中间：Register.objects.get(activation_key=key) 失败后直接把 key 用 % 拼进 HTML → 危险点：app/account/views.py:102 与 :208 的 HttpResponseForbidden(u'<h1>错误的 Key ： %s </h1>' % key)，无任何转义且响应当作 HTML 返回。入口身份：匿名。

**影响。** 攻击者把编码后的 HTML/JS 放入 key 段，构造 /account/register/<payload>/ 或 /account/password/reset/<payload>/ 链接发给受害者，脚本在站点源内执行，可窃取 Cookie（含会话）或钓鱼。

**修复。** 错误提示不要回显原始 key；确需回显时用模板自动转义（escape）输出，并把 key 限制为 [0-9a-f]{40}。

**复核员指出的最弱一环。** 最站不住的一环是"URL 路径里的 payload 能否原样进入 HTML 响应"。核实 app/account/urls.py:8、13 的正则 (?P<key>.+)/$：.+ 贪婪匹配可含斜杠（仅要求以 / 结尾），所以 <script>alert(document.cookie)</script> 这类带 / 的 payload 也能成为 key；Django 对 PATH_INFO 做百分号解码，%3C 等还原为 <；app/account/views.py:96-102、202-208 在 Register 查无时用 % 把 key 原样拼进 HttpResponseForbidden 的 HTML（Django 1.x 默认 Content-Type text/html），无任何转义。反射链路完整。

**判定历史。**

- 复核员同意：两个入口（/account/register/<key>/ 与 /account/password/reset/<key>/）均匿名可达、模式相同；只需用一个不存在的 key 触发回显。反射型 XSS，medium 恰当。（最弱一环：最站不住的一环是"URL 路径里的 payload 能否原样进入 HTML 响应"。核实 app/account/urls.py:8、13 的正则 (?P<key>.+)/$：.+ 贪婪匹配可含斜杠（仅要求以 / 结尾），所以 <script>alert(document.cookie)</script> 这类带 / 的 payload 也能成为 key；Django 对 PATH_INFO 做百分号解码，%3C 等还原为 <；app/account/views.py:96-102、202-208 在 Register 查无时用 % 把 key 原样拼进 HttpResponseForbidden 的 HTML（Django 1.x 默认 Content-Type text/html），无任何转义。反射链路完整。）

**证据。**

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

`app/account/urls.py:8-13`

```
    url(r'^register/(?P<key>.+)/$', 'register', name='complete_register'),
    url(r'^login/$', 'login', name='login'),
    url(r'^logout/$', 'logout', name='logout'),
    url(r'^(?P<id>\d+)/$', 'user', name='show_user'),
    url(r'^password/reset/$', 'password_reset_request', name='password_reset_request'),
    url(r'^password/reset/(?P<key>.+)/$', 'password_reset', name='password_reset')
```

<a id="finding-lab-001"></a>

### [LOW] lab 调试端点未授权暴露：匿名批量改写帖子与测试上传

- 编号：`LAB-001`
- 类别：`access_control`
- CWE：`CWE-306`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

/lab/ 下的调试端点 update_post_profile 与 uploadsf 未做任何认证即暴露：前者匿名批量改写全站帖子字段并保存，后者为匿名测试上传并把文件名反射进脚本。

**触发条件。** 匿名 GET /lab/update_post_profile 即全量改写帖子；匿名 POST /lab/uploadsf 上传文件并得到含文件名的脚本响应。

**数据流。** 来源：匿名 HTTP 请求 → 路由 app/ylab/urls.py:7-8 直接映射到视图，无任何装饰器/会话校验 → 危险点：app/ylab/views.py update_post_profile（:37-48）遍历并改写所有 Post 的 touser/updated 后 p.save()；upload_single_file（:24-34）接受未认证上传并把客户端文件名未转义拼进 <script> 响应。入口身份：匿名。

**影响。** 匿名攻击者可反复调用 /lab/update_post_profile 重写全站帖子的更新时间/收件人字段并触发重渲染（含每帖一次数据库写），造成内容数据被批量篡改与资源消耗；/lab/uploadsf 为无认证的调试上传与文件名反射（自 XSS 向量）。

**修复。** 删除或禁止生产路由暴露 lab 调试端点；如确需保留，加登录与权限校验、限制方法、并转义回显的文件名。

**复核员指出的最弱一环。** 最站不住的一环是"文件名反射 XSS"的利用面。核实 app/ylab/views.py:24-34：响应只返回给提交请求者本人（响应进入自己的父帧），属自 XSS 而非对第三方受害者的反射/存储 XSS，且 uploadsf 并不落盘；update_post_profile（37-48 行）为匿名 GET 即触发的全表遍历改写（touser/updated 字段 + 每条 p.save()），影响真实但限于这两个字段。因此 low 是恰当定级，而非 medium 以上。

**判定历史。**

- 复核员同意：路由核实：urls.py:31 挂载 /lab/ → app/ylab/urls.py:5-8 无任何装饰器/会话校验，匿名可达。批量数据改写 + 无认证调试上传 + 文件名自反射，low 恰当。（最弱一环：最站不住的一环是"文件名反射 XSS"的利用面。核实 app/ylab/views.py:24-34：响应只返回给提交请求者本人（响应进入自己的父帧），属自 XSS 而非对第三方受害者的反射/存储 XSS，且 uploadsf 并不落盘；update_post_profile（37-48 行）为匿名 GET 即触发的全表遍历改写（touser/updated 字段 + 每条 p.save()），影响真实但限于这两个字段。因此 low 是恰当定级，而非 medium 以上。）

**证据。**

`app/ylab/urls.py:5-8`

```
urlpatterns = patterns('ylab.views',
    url(r'^time$', 'time', name='time'),
    url(r'^uploadsf$', 'upload_single_file', name='uploadsf'),
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

`app/ylab/views.py:24-34`

```
def upload_single_file(req):
    ''' 仅仅处理上传的文件中的第一个 '''

    if req.method != 'POST':
        return HttpResponse("Just for POST test!")

    url = '/ydata/attachement/3'
    attachment = req.FILES.values()[0]
    innerHTML = u'<span><a href="%s">%s</a>， %s， <a href="%s/delete">删除</a></span>' % (url, attachment.name, attachment.size, url)
    r = u'<script type="text/javascript">window.parent.AfterSubmit(%s);</script>' % innerHTML
    return HttpResponse(r)
```

<a id="finding-redir-001"></a>

### [LOW] logout/login 的 next 与 admin Referer 重定向未校验（开放重定向）

- 编号：`REDIR-001`
- 类别：`redirect`
- CWE：`CWE-601`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

logout/login 对 next 参数、admin 登录对 Referer 不做校验即作为重定向目标，存在开放重定向。

**触发条件。** 访问 /account/logout/?next=https://evil.example/ 或带 ?next= 的登录链接；管理员登录页面携带攻击者控制的 Referer。

**数据流。** 来源：GET 参数 next（app/account/views.py:58、:44）→ 危险点：logout 直接 HttpResponseRedirect(previous_url or '/')（:60）；login 把 next 存入会话后登录成功再跳转（:38）。admin.login 同样把 HTTP_REFERER 存入会话（app/admin/views.py:64-66）用于登录后跳转（:62）。入口身份：匿名（logout 跳转）；login 跳转需完成一次登录但 next 由攻击者提供。

**影响。** 攻击者构造 /account/logout/?next=https://evil.example/ 等链接，可把站点用户重定向到钓鱼/恶意页面；用于结合登录流程的钓鱼（受害者以为重新登录，把凭据输入攻击者站点）。

**修复。** 跳转目标只允许站内相对路径或白名单域名：使用 django.utils.http.is_safe_url 校验，拒绝绝对 URL。

**复核员指出的最弱一环。** 最站不住的一环是 login 分支"受害者必须完成登录才会跳转"。核实 app/account/views.py:42-44 把 GET 参数 next 存入会话、38 行登录成功后 HttpResponseRedirect(request.session.get('login_redirect_url','/'))；logout（55-60 行）直接 HttpResponseRedirect(request.GET.get('next') or '/')，匿名即可触发；admin login（admin/views.py:62-66）把 HTTP_REFERER 存入会话用于登录后跳转（浏览器对顶层导航会带 Referer）。三条路径均无 is_safe_url/白名单校验。

**判定历史。**

- 复核员同意：开放重定向成立：logout 分支完全匿名直接跳转，login/Referer 分支用于钓鱼链（诱导重新登录）。影响属辅助性钓鱼，low 恰当。（最弱一环：最站不住的一环是 login 分支"受害者必须完成登录才会跳转"。核实 app/account/views.py:42-44 把 GET 参数 next 存入会话、38 行登录成功后 HttpResponseRedirect(request.session.get('login_redirect_url','/'))；logout（55-60 行）直接 HttpResponseRedirect(request.GET.get('next') or '/')，匿名即可触发；admin login（admin/views.py:62-66）把 HTTP_REFERER 存入会话用于登录后跳转（浏览器对顶层导航会带 Referer）。三条路径均无 is_safe_url/白名单校验。）

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

`app/account/views.py:36-45`

```
                    if request.session.test_cookie_worked():
                        request.session.delete_test_cookie()
                        return HttpResponseRedirect(request.session.get('login_redirect_url','/') or '/')
                else:
                    return HttpResponseForbidden(u'用户未被激活，请联系管理员： ylinux.admin@gmail.com')

    else:
        # 形如 "http://127.0.0.1:8000/account/login?next=/admin/" 的 url 可以得到 next 值
        request.session['login_redirect_url'] = request.GET.get('next')
        form = AuthenticationForm(request)
```

`app/admin/views.py:62-66`

```
                return HttpResponseRedirect(request.session.get('previous_url','/'))

    else:
        request.session['previous_url'] = request.META.get('HTTP_REFERER', '/')
        form = AuthenticationForm(request)
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

已覆盖：根 settings/urls、全部 app（account/admin/home/bbs/blog/me/ydata/ylab/wiki/sessions/syndication）的 urls/views/forms/models、自定义会话与认证中间件/后端、lib/markdown 渲染链路、lib/django_xmlrpc 与 lib/ylinux_xmlrpc、全部模板中 |safe 输出点。未覆盖：scripts/ 部署脚本细节、静态资源与前端第三方库、生产 Web 服务器配置。

## 局限

本报告为静态审计结论：无法确认生产部署是否覆盖了 DEBUG/SESSION_ENGINE 等设置（settings.py 未定义 SESSION_ENGINE，可能回落到未安装的 django.contrib.sessions 后端，运行时会话行为未能静态确认）；markdown/HTML 具体解析行为按仓库内 lib/markdown 2.0.3 源码判断；20 位熵爆破与 CSRF 的实际成功率依赖部署网络、速率限制与受害者行为；未对 scripts/ 下部署脚本与第三方代码（如 jquery、syntaxhighlighter）做深入审计。

## 复核意见

复核方式：对 12 条 confirmed 发现逐一重开证据位置并外扩上下文，另追查了 lib/markdown 的 safe_mode 默认值、HtmlStash/RawHtmlPostprocessor 的还原逻辑、ylinux_text_filter 实现、XML-RPC 派发层、自定义会话/认证中间件、account.decorators 的 permission_required、root urls 的 ylab/xmlrpc 挂载与 /ymedia/ static 配置。结论：12 条全部同意，无 dispute。仍需保留的怀疑点：(1) CONFIG-002 中 DB 口令 '123456' 对 sqlite3 引擎不生效，该条影响主要靠 SECRET_KEY 支撑；(2) LAB-001 与 ydata 上传回显的文件名反射均为自 XSS，仅影响提交者本人；(3) XSS-002 依赖旧版 Django HttpResponse 默认 text/html 与 PATH_INFO 解码，两者在该版本下成立。抽查 leads 的 benign 判定（SQL 参数绑定、固定命令、服务端 pickle 会话）未见站不住之处；未发现需 note_gap 的遗漏高危项。

## 复核缺口

无。
