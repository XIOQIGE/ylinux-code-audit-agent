# ylinux_old 应用安全审计报告

- 目标：`https://github.com/gwind/ylinux_old`，commit `8a7316deec88287d020eca21c38dad921b623ffc`
- 模型：审计员 `deepseek-v4-pro`，复核员 `deepseek-v4-pro`
- 时间：2026-10-21T09:28:29+08:00 → 2026-10-21T09:43:08+08:00
- 结论：确认 15 个问题，最高严重性为 high。
- 统计：已确认 15，待再确认 0，已排除 0；引用核对 39 条，未通过 0 条

## 发现总表

| 严重性 | 编号 | 问题 | 入口身份 | 状态 | 复核员 | 位置 |
| --- | --- | --- | --- | --- | --- | --- |
| high | [`ACCESS-001`](#finding-access-001) | XML-RPC 删除/编辑主题接口缺少所有权与权限校验 | 可自助注册的用户 | confirmed | 同意 | `lib/ylinux_xmlrpc.py:39` |
| high | [`FILE-001`](#finding-file-001) | ydata 附件上传文件名未校验导致路径穿越任意文件写入 | 可自助注册的用户 | confirmed | 同意 | `app/ydata/views.py:37` |
| high | [`XSS-001`](#finding-xss-001) | wiki 主题与回复正文存在存储型 XSS（Markdown 未启用 safe_mode，body_html 以 \|safe 渲染） | 可自助注册的用户 | confirmed | 同意 | `app/wiki/views.py:432` |
| medium | [`ACCESS-002`](#finding-access-002) | editPostAJAX 越权编辑他人帖子（水平越权） | 可自助注册的用户 | confirmed | 同意 | `app/wiki/views.py:447` |
| medium | [`ACCESS-003`](#finding-access-003) | 受限目录的读取路径未做组权限校验（读侧越权） | 匿名 | confirmed | 同意 | `app/ydata/models.py:91` |
| medium | [`CONFIG-001`](#finding-config-001) | DEBUG=True 生产配置泄露堆栈、设置与媒体目录 | 无请求入口 | confirmed | 同意 | `settings.py:18` |
| medium | [`CONFIG-002`](#finding-config-002) | SECRET_KEY 硬编码入仓库致会话完整性校验可被伪造 | 无请求入口 | confirmed | 同意 | `settings.py:78` |
| medium | [`CRYPTO-001`](#finding-crypto-001) | 用户口令使用单轮 SHA1 + 弱盐存储 | 无请求入口 | confirmed | 同意 | `app/account/models.py:50` |
| medium | [`CRYPTO-002`](#finding-crypto-002) | 密码重置令牌熵过低且无过期/防爆破机制 | 匿名 | confirmed | 同意 | `app/account/models.py:424` |
| medium | [`CSRF-001`](#finding-csrf-001) | 全站缺少 CSRF 防护且状态变更端点可被 GET 触发 | 匿名 | confirmed | 同意 | `settings.py:98` |
| medium | [`XSS-002`](#finding-xss-002) | account.views.register / password_reset 激活 key 未转义反射型 XSS | 匿名 | confirmed | 同意 | `app/account/urls.py:8` |
| low | [`CONFIG-003`](#finding-config-003) | 数据库口令硬编码提交仓库（当前 sqlite 未生效） | 无请求入口 | confirmed | 同意 | `settings.py:42` |
| low | [`FILE-002`](#finding-file-002) | 附件下载缺少鉴权与目录权限校验 | 匿名 | confirmed | 同意 | `app/ydata/views.py:117` |
| low | [`MISC-001`](#finding-misc-001) | ylab update_post_profile 匿名批量改写帖子数据 | 匿名 | confirmed | 同意 | `app/ylab/views.py:37` |
| low | [`REDIR-001`](#finding-redir-001) | logout 与管理登录存在开放重定向 | 匿名 | confirmed | 同意 | `app/account/views.py:55` |

下面的发现由 Agent 写入，每条引用都回到源码核对过。审计员综述写在复核之前，单条发现的状态以复核后为准。线索处置、读过的文件、阶段记录、工具序列和引用核对见 `appendix.md`，关键决策见 `decisions.md`。

## 审计员综述

ylinux_old（commit 8a7316d）是基于老式 Django 1.x 的自研社区/维基系统，自实现了账户、会话、权限和 XML-RPC 模块。整体安全状况较差：全站未启用 CSRF 中间件；wiki 正文用未启用 safe_mode 的 Markdown 生成 HTML 并以 |safe 输出，形成注册用户即可投放的存储型 XSS；附件上传文件名未校验导致路径穿越任意文件写入；XML-RPC 的删除/编辑主题接口只验登录不验所有权，任意注册用户可清空全站主题；Catalog 组权限只在写路径生效，所有读取路径匿名可读；密码以单轮 SHA1 存储、密码重置令牌熵仅 20 位；DEBUG=True 与 SECRET_KEY、数据库口令被直接提交进仓库。共确认 15 项问题，其中高危 4 项（存储型 XSS、上传路径穿越、XML-RPC 越权删除、DEBUG 泄露组合）。

## 风险概览

最高风险依次为：1) 注册用户可注入存储型 XSS，配合未设 HttpOnly 的会话 Cookie 可实现账户接管（含管理员）；2) 附件上传文件名路径穿越可向任意可写路径写文件，有升级为代码执行的可能；3) XML-RPC delete_all_topic/delete_topic/edit_topic 无权限与所有权校验，注册用户可清空全站内容；4) Catalog.groups 组权限对读取路径完全不生效，匿名访客可读取受限目录的主题、回复与附件；5) 全站无 CSRF 防护且删除类操作多为 GET，可跨站触发；6) DEBUG=True 使匿名攻击者可通过制造异常获取 SECRET_KEY 等敏感信息，SECRET_KEY 公开又使会话完整性校验可伪造。

## 已确认的问题

<a id="finding-access-001"></a>

### [HIGH] XML-RPC 删除/编辑主题接口缺少所有权与权限校验

- 编号：`ACCESS-001`
- 类别：`access_control`
- CWE：`CWE-862`
- 入口身份：可自助注册的用户
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

XML-RPC 的 delete_topic / delete_all_topic / edit_topic 只校验用户名口令，不校验主题所有权或任何权限，任何注册用户都可删除全部主题或篡改他人主题。

**触发条件。** 注册用户以自身账号口令向 /xmlrpc/ 调用 delete_topic(id,...)、delete_all_topic(...) 或 metaWeblog.editPost(postid,...)，无需任何额外权限。

**数据流。** 来源：XML-RPC 方法参数 id/user/passwd（经 /xmlrpc/ 由 lib/django_xmlrpc/views.py:87 的 _marshaled_dispatch 解析请求体）→ 中间：lib/ylinux_xmlrpc.py:39-45 has_auth 只调用 authenticate 验证用户名口令，不检查所有权或权限 → 危险点：delete_topic（:47-58）任意用户删除任意 Topic，delete_all_topic（:60-69）删除全部 Topic，edit_topic（:168-183）改写任意 Topic 的 name/正文。这些方法已通过 settings.py:164-175 注册为公开 XMLRPC_METHODS。入口身份：注册用户（注册开放），凭自身用户名口令即可调用。

**影响。** 任意注册用户可用自己的账号口令调用 delete_all_topic 清空全站主题（连带帖子）、删除/篡改任何人的主题正文与标题，造成全站数据破坏与内容伪造。

**修复。** 删除 delete_all_topic 或仅限管理员；对 delete_topic/edit_topic 增加所有权校验（topic.user == 认证用户）或要求相应权限；为 XML-RPC 方法统一加权限装饰器并记录操作审计。

**复核员指出的最弱一环。** 最弱的一环是"has_auth 只认证身份、方法对所有权/权限零校验"。我核对了 lib/ylinux_xmlrpc.py:39-45（has_auth 仅 authenticate(username,password)），:47-58 delete_topic（凭自身口令即可删任意 Topic 及其帖子，无 topic.user 校验）、:60-69 delete_all_topic（Topic.objects.all().delete() 无任何权限）、:168-185 edit_topic（改写任意 Topic 的 name 与正文，无归属校验）；settings.py:164-175 已注册这些方法，lib/django_xmlrpc/views.py:81-87 的 _marshaled_dispatch 处理 /xmlrpc/ POST（urls.py:45-48）。注册开放（account/views.py:63-91 request_register 无门槛）。

**判定历史。**

- 复核员同意：来源、认证逻辑、危险点、注册表均与代码一致。任意注册用户可凭自己口令清空全站主题或篡改他人主题，破坏性大，high 合理。new_media（:105-125）虽做了 os.path.basename，不影响本条的删除/编辑越权结论。（最弱一环：最弱的一环是"has_auth 只认证身份、方法对所有权/权限零校验"。我核对了 lib/ylinux_xmlrpc.py:39-45（has_auth 仅 authenticate(username,password)），:47-58 delete_topic（凭自身口令即可删任意 Topic 及其帖子，无 topic.user 校验）、:60-69 delete_all_topic（Topic.objects.all().delete() 无任何权限）、:168-185 edit_topic（改写任意 Topic 的 name 与正文，无归属校验）；settings.py:164-175 已注册这些方法，lib/django_xmlrpc/views.py:81-87 的 _marshaled_dispatch 处理 /xmlrpc/ POST（urls.py:45-48）。注册开放（account/views.py:63-91 request_register 无门槛）。）

**证据。**

`lib/ylinux_xmlrpc.py:39-58`

```
def has_auth(user, passwd):

    user = authenticate(username=user, password=passwd)
    if user is not None:
        return True
    else:
        return False

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
    except:
        raise Fault(-1, "delete all topics failed")
```

`settings.py:164-175`

```
XMLRPC_METHODS = (
    ('ylinux_xmlrpc.delete_topic', 'delete_topic'),
    ('ylinux_xmlrpc.delete_all_topic', 'delete_all_topic'),

    # MetaWebBlog API
    ('ylinux_xmlrpc.new_topic', 'metaWeblog.newPost'),
    ('ylinux_xmlrpc.new_media', 'metaWeblog.newMediaObject'),
    ('ylinux_xmlrpc.edit_topic', 'metaWeblog.editPost'),
    ('ylinux_xmlrpc.get_topic', 'metaWeblog.getPost'),
    ('ylinux_xmlrpc.get_categories', 'metaWeblog.getCategories'),
    ('ylinux_xmlrpc.get_recent_topics', 'metaWeblog.getRecentPosts'),
```

<a id="finding-file-001"></a>

### [HIGH] ydata 附件上传文件名未校验导致路径穿越任意文件写入

- 编号：`FILE-001`
- 类别：`file_access`
- CWE：`CWE-22`
- 入口身份：可自助注册的用户
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

附件上传端点把用户控制的原始文件名直接拼进保存路径，未做任何路径规范化，注册用户可通过文件名中的 ../ 实现路径穿越的任意文件写入。

**触发条件。** 注册用户向 /ydata/uploadsf/<topic_id>/ 以 multipart 上传名为 ../../<目标路径> 的文件（POST 参数 single_file）。

**数据流。** 来源：上传文件原始文件名 f.name（app/ydata/views.py:40 取自 req.FILES['single_file']，multipart filename 由攻击者控制）→ 中间：:78 直接拼入 local_name = str(id)+'-'+str(req.user.id)+'-'+f.name → 危险点：:79-82 os.path.join(MEDIA_ROOT, ATTACHMENT_UPLOAD_TO, local_name) 后 open(save_path,'wb+') 写入，未做 basename/黑名单校验，文件名中的 ../ 可穿越出上传目录（MEDIA_ROOT=PROJECT_ROOT/ymedia/，见 settings.py:74）。入口身份：注册用户（@login_required，注册开放）。

**影响。** 攻击者上传文件名含 ../ 序列的文件即可在 Web 进程权限允许的任意目录写入任意内容（覆盖站点脚本/配置文件、投放 .py/.html 载荷等），在共享主机或权限宽松的部署下可直接导致代码执行或站点篡改。

**修复。** 使用 os.path.basename(f.name)（并对非 ASCII 做规范化）、拒绝含路径分隔符/../ 的文件名，或改用服务端生成的随机文件名并在数据库中保留展示名；同时对写入做扩展名/类型白名单。

**复核员指出的最弱一环。** 最弱的一环是"f.name 是否真能保留 ../ 穿越序列进入 os.path.join"。我核对了 app/ydata/views.py:31-90：upload_single_file 有 @login_required；f.name 取自 req.FILES['single_file'] 后未经 os.path.basename 或任何黑名单，直接进入 local_name = str(id)+'-'+str(req.user.id)+'-'+f.name（:78），再 os.path.join(MEDIA_ROOT, 'ydata/attachments', local_name) 后 open(save_path,'wb+')（:79-82）；ATTACHMENT_UPLOAD_TO='ydata/attachments'（ydata/settings.py:65），MEDIA_ROOT=PROJECT_ROOT+'/ymedia/'（settings.py:74）。该年代 Django 的 multipart 解析只在 IE UA 下剥路径，攻击者自构造的 multipart filename 可完整保留 ../，穿越成立。

**判定历史。**

- 复核员同意：来源（multipart 文件名，攻击者可控且未被规范化）、危险点（open(save_path,'wb+') 前无 basename/校验）、入口身份（注册开放 + @login_required）均已核实。任意文件写入，结合 /ymedia/ 静态服务可投放 .html 载荷，high 合理。（最弱一环：最弱的一环是"f.name 是否真能保留 ../ 穿越序列进入 os.path.join"。我核对了 app/ydata/views.py:31-90：upload_single_file 有 @login_required；f.name 取自 req.FILES['single_file'] 后未经 os.path.basename 或任何黑名单，直接进入 local_name = str(id)+'-'+str(req.user.id)+'-'+f.name（:78），再 os.path.join(MEDIA_ROOT, 'ydata/attachments', local_name) 后 open(save_path,'wb+')（:79-82）；ATTACHMENT_UPLOAD_TO='ydata/attachments'（ydata/settings.py:65），MEDIA_ROOT=PROJECT_ROOT+'/ymedia/'（settings.py:74）。该年代 Django 的 multipart 解析只在 IE UA 下剥路径，攻击者自构造的 multipart filename 可完整保留 ../，穿越成立。）

**证据。**

`app/ydata/views.py:37-44`

```
    if req.method != 'POST':
        return HttpResponse("Just for POST a single file")

    f = req.FILES['single_file'] #req.FILES.values()[0]
    if f.size > ydata_settings.ATTACHMENT_SIZE_LIMIT:
        notes = u'文件太大： %s (限制大小： %s)' % (f.size, ydata_settings.ATTACHMENT_SIZE_LIMIT)
        r = u'<script type="text/javascript">window.parent.UploadError("%s");</script>' % notes
        return HttpResponse(r)
```

`app/ydata/views.py:78-86`

```
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

<a id="finding-xss-001"></a>

### [HIGH] wiki 主题与回复正文存在存储型 XSS（Markdown 未启用 safe_mode，body_html 以 |safe 渲染）

- 编号：`XSS-001`
- 类别：`xss`
- CWE：`CWE-79`
- 入口身份：可自助注册的用户
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

用户提交的主题正文和回复正文在保存时由 vendored Python-Markdown 2.0.3 以默认 safe_mode=False 转换成 HTML（未做任何 HTML 转义），随后在多个模板中以 |safe 直接输出，任何已注册用户都可以发布包含 <script> 的内容，对所有浏览者造成存储型 XSS。

**触发条件。** 已注册用户通过 /wiki/topic/<id>/replayAJAX/（POST body）、/wiki/topic/<id>/addpost/、/wiki/catalog/<id>/addtopic/、/wiki/topic/<id>/edit/ 或 XML-RPC metaWeblog.newPost/editPost 提交正文；任意访客浏览 /wiki/topic/<id>/、/bbs/topic/<id>/、/wiki/post/<id>/ 等页面时执行。

**数据流。** 来源：POST 参数 body（app/wiki/views.py:432 取 request.POST["body"]，经 replayAJAX 以 markup='none' 构造 Post 并 save() 于 :435-436；主题正文经 app/ydata/forms.py:98/127 调用 Topic.save_file）→ 中间：Post.save()/Topic.save_file 在 app/ydata/models.py:258-260（markup='none'）与 :198-200（Topic.save_file）调用 Markdown(...).convert/convertFile，其 vendored 实现 lib/markdown/__init__.py:188 默认 safe_mode=False，不转义原始 HTML，ylinux_text_filter（app/ydata/models.py:396-452）也只做替换不做转义 → 存储：Post.body_html/Topic.body_html 落库/落盘 → 危险点：app/wiki/utils.py:18（POST_MAIN 模板 `{{ post.body_html|safe }}`）、templates/wiki/topic.html:54/59、templates/bbs/topic.html:23/30、templates/wiki/post.html:12、templates/wiki/replayAJAX.html:16、templates/wiki/editPostAJAX.html:19。入口身份：注册即可（app/account/views.py:63-91 request_register 对任意邮箱开放申请）。

**影响。** 任意注册用户可植入持久化脚本；浏览者（含管理员）在 ylinux.org 源下执行攻击者脚本，可窃取会话 Cookie（会话 Cookie 未设置 HttpOnly，见 app/sessions/middleware.py 的 set_cookie 调用）导致账户接管、盗取权限，或进行钓鱼。

**修复。** 生成 body_html 时使用 safe_mode='escape'/'replace'（并对 ylinux_text_filter 插入的附件/主题名做 escape），或改用白名单 HTML 清洗（如 bleach）；模板中移除 |safe，改为对可信输出显式 mark_safe；为会话 Cookie 设置 HttpOnly。

**复核员指出的最弱一环。** 最弱的一环是"Markdown safe_mode=False 真的不转义原始 HTML、且中途没有其他清洗"。我核对了 lib/markdown/__init__.py:185-189（safe_mode 默认 False）、postprocessors.py:43-59（RawHtmlPostprocessor 在 not self.markdown.safeMode 时把 stash 里的原始 HTML 原样还原）、app/ydata/models.py:258-260（markup='none' 走 Markdown(extensions=['fenced_code']).convert(ylinux_text_filter(body))）以及 396-452 的 ylinux_text_filter（只做 [A:ID]/[W:ID]/[IMG:ID] 替换，注入的 HTML 也不转义，且替换出的 a.name 原样拼接）。保存后 urlize/smiles 均不剥离标签。渲染侧 7 处 |safe 全部命中 body_html（templates 全库 grep 结果与证据一致，无其他未覆盖 sink）。

**判定历史。**

- 复核员同意：核实了来源（app/wiki/views.py:432-436 replayAJAX 以 markup='none' 保存，app/ydata/forms.py:87-99/118-127 Add/EditTopicForm 调用 Topic.save_file）、中间（models.py:258-260 与 198-200 均以默认 safe_mode=False 的 vendored Python-Markdown 转换，ylinux_text_filter 不转义）、危险点（app/wiki/utils.py:18 及 templates/wiki/topic.html:54/59、bbs/topic.html:23/30、wiki/post.html:12、replayAJAX.html:16、editPostAJAX.html:19 全部 |safe 渲染）。Post.save 的 markdown 分支虽用了 safe_mode='escape'，但 'none' 分支与主题正文路径不受此保护，注册用户默认路径即可触发。存储型 XSS，high 合理。（最弱一环：最弱的一环是"Markdown safe_mode=False 真的不转义原始 HTML、且中途没有其他清洗"。我核对了 lib/markdown/__init__.py:185-189（safe_mode 默认 False）、postprocessors.py:43-59（RawHtmlPostprocessor 在 not self.markdown.safeMode 时把 stash 里的原始 HTML 原样还原）、app/ydata/models.py:258-260（markup='none' 走 Markdown(extensions=['fenced_code']).convert(ylinux_text_filter(body))）以及 396-452 的 ylinux_text_filter（只做 [A:ID]/[W:ID]/[IMG:ID] 替换，注入的 HTML 也不转义，且替换出的 a.name 原样拼接）。保存后 urlize/smiles 均不剥离标签。渲染侧 7 处 |safe 全部命中 body_html（templates 全库 grep 结果与证据一致，无其他未覆盖 sink）。）

**证据。**

`app/wiki/views.py:432-436`

```
        post_body = request.POST.get("body", None)
        if len(post_body) < 2:
            return {'error': u'您的回复太短，至少2个字符！'}
        post = Post(topic = topic, user = request.user, user_ip = ip, markup = 'none', body = post_body, parent = parent_post)
        post.save()
```

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

`lib/markdown/__init__.py:185-189`

```
    def __init__(self,
                 extensions=[],
                 extension_configs={},
                 safe_mode = False, 
                 output_format=DEFAULT_OUTPUT_FORMAT):
```

`app/wiki/utils.py:17-19`

```
<div class="post-body">
  <p>{{ post.body_html|safe }}</p>
</div>
```

`templates/wiki/topic.html:53-54`

```
  <div class="topic-body content">
    {{ topic.body_html|safe }}
```

`templates/bbs/topic.html:22-23`

```
    <h2>标题： {{ topic.name }}</h2>
    {{ topic.body_html|safe }}
```

<a id="finding-access-002"></a>

### [MEDIUM] editPostAJAX 越权编辑他人帖子（水平越权）

- 编号：`ACCESS-002`
- 类别：`access_control`
- CWE：`CWE-862`
- 入口身份：可自助注册的用户
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

editPostAJAX 视图缺少帖子归属校验，任何登录用户都能修改任意帖子的正文。

**触发条件。** 注册用户向 /wiki/post/<任意postID>/editAJAX/ 提交 POST body 即可覆盖该帖子内容，被改帖子无需属于攻击者。

**数据流。** 来源：URL 参数 postID 与 POST 参数 body（app/wiki/urls.py:54 路由到 editPostAJAX）→ 中间：app/wiki/views.py:451 直接 get_object_or_404(Post, pk=postID)，未做 post.user == request.user 之类的归属校验（对比同文件 edit_topic 在 :215-218 有归属校验）→ 危险点：:456-460 将 body 写入任意帖子并 save()。入口身份：注册用户（@login_required，注册开放）。

**影响。** 任意注册用户可改写任何人的帖子正文，破坏内容完整性；结合 XSS-001 的渲染链路，还能把恶意脚本注入他人帖子，扩大存储型 XSS 的散布面。

**修复。** 在编辑前校验 post.user == request.user（或具备相应权限），否则返回 403；同时只允许 POST 方法执行写操作。

**复核员指出的最弱一环。** 最弱的一环是"是否真的缺少归属校验"。我核对了 app/wiki/views.py:447-467：editPostAJAX 有 @login_required，但取 post 后直接判断方法并 post.body = post_body; post.save()，全程没有 post.user == request.user 或 topic 归属校验；对比同文件 edit_topic（:217-218）与 del_post（:277-278）都有归属校验，说明此处是遗漏而非设计。路由 app/wiki/urls.py:54 确认 /post/<postID>/editAJAX/ 暴露。

**判定历史。**

- 复核员同意：水平越权成立：任意登录用户可改写任意帖子正文（仅 GET 分支返回表单，其余方法都执行写操作）。与 XSS-001 的渲染链路结合可把存储型 XSS 植入他人帖子。medium 恰当。（最弱一环：最弱的一环是"是否真的缺少归属校验"。我核对了 app/wiki/views.py:447-467：editPostAJAX 有 @login_required，但取 post 后直接判断方法并 post.body = post_body; post.save()，全程没有 post.user == request.user 或 topic 归属校验；对比同文件 edit_topic（:217-218）与 del_post（:277-278）都有归属校验，说明此处是遗漏而非设计。路由 app/wiki/urls.py:54 确认 /post/<postID>/editAJAX/ 暴露。）

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

<a id="finding-access-003"></a>

### [MEDIUM] 受限目录的读取路径未做组权限校验（读侧越权）

- 编号：`ACCESS-003`
- 类别：`access_control`
- CWE：`CWE-862`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

Catalog.groups 的组访问控制（has_access）只在写路径上被校验，所有读取路径（wiki/bbs 的主题、目录、帖子及附件下载）都不调用它，匿名访客可直接读取受限目录的全部内容。

**触发条件。** 匿名 GET /wiki/topic/<id>/、/wiki/catalog/<id>/、/wiki/topic/<id>/ajax_show_posts/、/bbs/topic/<id>/ 或 /ydata/attachment/<id>/download/ 即可读取属于指定了 groups 的 Catalog 下的内容，无需登录或加入组。

**数据流。** 来源：URL 参数 id/topicID/postID，匿名可达（wiki 的 topic/catalog/post/ajax_show_posts、bbs 的 topic/catalog、ydata 的 attachment download 均无登录装饰器）→ 中间：Catalog.groups 组限制只在写路径被校验（find_references 确认 has_access 仅出现于 app/wiki/views.py:141、:172、:192、:423 四个写操作），所有读视图都不调用 catalog.has_access → 危险点：app/wiki/views.py:81-103 topic、:51-79 catalog、:119-128 post、:368-388 ajax_show_posts（匿名渲染全部回复 body_html），app/bbs/views.py:30-56 catalog/topic，以及 app/ydata/views.py:117-127 download_attachment 直接返回受限目录内容。入口身份：匿名（无需登录即可读取任何目录的主题、回复与附件）。

**影响。** Catalog.groups 设计的“仅组内用户可访问”在读取侧完全不生效：任何匿名访客只要知道（或枚举）主题/帖子/附件 id，就能读取受限目录下的主题正文、全部回复和附件内容，访问控制模型对读操作形同虚设。

**修复。** 在 wiki/bbs 的所有读视图（topic、catalog、post、ajax_show_posts、Feeds 等）与附件下载/展示入口统一调用 catalog.has_access(request.user) 做读取鉴权，无权限返回 403/404；并将该校验下沉到模型层或中间件，避免遗漏新入口。

**复核员指出的最弱一环。** 最弱的一环是"读侧真的从未调用 has_access、也没有中间件/装饰器兜底"。我做了全库正则搜索，has_access 的调用点只有 4 处且全部在写路径（app/wiki/views.py:141/172/192/423）；逐一读窗口核实读视图：wiki topic（81-103）、catalog（51-79）、post（119-128）只有 @render_to，ajax_show_posts（368-388）连装饰器都没有，bbs catalog/topic（app/bbs/views.py:30-56）与 download_attachment（app/ydata/views.py:117-127）同样无任何权限判断；app/account/middleware.py:15-21 的 AuthenticationMiddleware 仅填充 request.user，不做目录级控制；wiki/utils.py:23-36 的 render_post 只渲染模板不检查权限。该环节经核实站得住。

**判定历史。**

- 复核员同意：来源（URL 路径参数 id/topicID/postID，匿名可达）、中间（Catalog.groups 的组限制只写在模型 has_access 中且仅被 4 个写操作调用）、危险点（全部读视图与附件下载直接返回受限目录内容）均与代码一致：has_access 定义于 app/ydata/models.py:91-101，调用点经全库搜索确认只有 app/wiki/views.py:141/172/192/423 四个写路径；wiki topic/catalog/post/ajax_show_posts、bbs catalog/topic、ydata download_attachment 均无登录装饰器也无 has_access 调用，中间件层也无兜底。匿名读取组受限目录内容的事实成立，越权读取是真实缺陷。medium 定级合理：属于访问控制模型在读取侧整体失效，但因目录内容敏感度依赖部署中是否实际配置 groups，不抬到 high。（最弱一环：最弱的一环是"读侧真的从未调用 has_access、也没有中间件/装饰器兜底"。我做了全库正则搜索，has_access 的调用点只有 4 处且全部在写路径（app/wiki/views.py:141/172/192/423）；逐一读窗口核实读视图：wiki topic（81-103）、catalog（51-79）、post（119-128）只有 @render_to，ajax_show_posts（368-388）连装饰器都没有，bbs catalog/topic（app/bbs/views.py:30-56）与 download_attachment（app/ydata/views.py:117-127）同样无任何权限判断；app/account/middleware.py:15-21 的 AuthenticationMiddleware 仅填充 request.user，不做目录级控制；wiki/utils.py:23-36 的 render_post 只渲染模板不检查权限。该环节经核实站得住。）

**证据。**

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

`app/wiki/views.py:81-96`

```
@render_to('wiki/topic.html')
def topic(request, id):

    try:
        topic = Topic.objects.get(pk=id)
    except Topic.DoesNotExist:
        url = reverse ('wiki:topic_not_exist', args=[id])
        return HttpResponseRedirect(url)

    parents = get_parents (Catalog, topic.catalog.id)
    edit_topic_perm = request.user.has_perm ('ydata.edit_topic')

    posts = Post.objects.filter(topic=id, parent=None).order_by('created')
    POST_HTML = ''
    for p in posts:
        POST_HTML += render_post(request.user, p)
```

`app/wiki/views.py:368-388`

```
def ajax_show_posts(request, topicID=None, postID=None):

    if topicID:
        posts = Post.objects.filter(topic=topicID, parent=None).order_by('created')
        #posts = Post.objects.filter(topic=topicID).order_by('created')
    elif postID:
        posts = [get_object_or_404(Post,pk=postID),]
    else:
        return HttpResponse(u'显示 posts 出错')

    HTML = ''
#    HTML = '''
#<script type="text/javascript">
#  $(document).ready(function () {
#    $(".post-item").draggable();
#  })
#</script>
#'''
    for p in posts:
        HTML += render_post(request.user, p)
    return HttpResponse(HTML)
```

<a id="finding-config-001"></a>

### [MEDIUM] DEBUG=True 生产配置泄露堆栈、设置与媒体目录

- 编号：`CONFIG-001`
- 类别：`config`
- CWE：`CWE-215`
- 入口身份：无请求入口
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

DEBUG=True 与 TEMPLATE_DEBUG=True 被直接提交进代码并在生产生效，同时以 show_indexes=True 开放媒体目录浏览，导致敏感信息（含 SECRET_KEY）对外泄露。

**触发条件。** 配置问题本身生效即可：例如匿名访问 /ydata/attachment/<id>/download/ 在缺少 User-Agent 请求头时触发 KeyError（app/ydata/views.py:138），即返回含 settings 转储的技术 500 页面。

**影响。** 生产环境开启 DEBUG 时，任何未捕获异常都会向匿名访问者返回带完整回溯、局部变量、settings 全部内容（包括 SECRET_KEY、数据库配置）和 SQL 语句的技术 500 页面；同时 /ymedia/ 由 Django 静态服务开放目录列表（show_indexes: True），泄露媒体文件清单与内容。

**修复。** 部署环境将 DEBUG/TEMPLATE_DEBUG 设为 False，配置 500/404 模板，静态文件交由 Web 服务器处理并禁止目录列表。

**复核员指出的最弱一环。** 最弱的一环是"DEBUG=True 是否真实生效并开放媒体目录"。我核对了 settings.py:18-19（DEBUG=True、TEMPLATE_DEBUG=DEBUG）与 urls.py:59-63（settings.DEBUG 为真时注册 /ymedia/ 的 django.views.static.serve，show_indexes=True）；触发例证成立：app/ydata/views.py:138 无条件读取 request.META['HTTP_USER_AGENT']，缺 UA 头时抛 KeyError，DEBUG 下返回含 settings 转储（含 SECRET_KEY）的技术 500 页面。

**判定历史。**

- 复核员同意：DEBUG/TEMPLATE_DEBUG 提交在代码中、目录列表开启、可匿名触发信息泄露。medium 恰当（真实风险取决于部署是否覆盖该配置，仓库默认即开启）。（最弱一环：最弱的一环是"DEBUG=True 是否真实生效并开放媒体目录"。我核对了 settings.py:18-19（DEBUG=True、TEMPLATE_DEBUG=DEBUG）与 urls.py:59-63（settings.DEBUG 为真时注册 /ymedia/ 的 django.views.static.serve，show_indexes=True）；触发例证成立：app/ydata/views.py:138 无条件读取 request.META['HTTP_USER_AGENT']，缺 UA 头时抛 KeyError，DEBUG 下返回含 settings 转储（含 SECRET_KEY）的技术 500 页面。）

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

### [MEDIUM] SECRET_KEY 硬编码入仓库致会话完整性校验可被伪造

- 编号：`CONFIG-002`
- 类别：`config`
- CWE：`CWE-798`
- 入口身份：无请求入口
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

SECRET_KEY 硬编码提交在公开仓库中，而它是会话 pickle 数据 MD5 防篡改校验的唯一密钥；密钥公开使校验可被绕过，结合 pickle 反序列化存在会话伪造与代码执行风险。

**触发条件。** 配置/代码层问题：会话数据以 pickle + md5(pickled+SECRET_KEY) 存放（app/sessions/models.py:13-19、backends/base.py:86-98），SECRET_KEY 公开后任何可写会话存储的攻击者都能伪造任意会话内容（例如管理员会话）。

**影响。** SECRET_KEY 随代码公开后，会话数据的 MD5 完整性校验（pickled+SECRET_KEY）形同虚设：任何能修改会话存储（数据库行或文件）的攻击者都可以构造合法的 pickle 会话数据（例如把自己的会话写成 _auth_user_id=<管理员id>），pickle.loads 在反序列化伪造数据时还可能触发任意代码执行；DEBUG 页面又会直接打印该密钥。

**修复。** 生成新的 SECRET_KEY 并从环境变量注入（不提交仓库）；轮换密钥使旧会话失效；会话反序列化考虑改用 JSON 序列化并继续保留签名校验（使用独立的、不公开的签名密钥）。

**复核员指出的最弱一环。** 最弱的一环是"公开的 SECRET_KEY 是否足以让会话完整性校验失效，以及 RCE 措辞是否越界"。我核对了 settings.py:79（SECRET_KEY 明文提交）、app/sessions/models.py:13-19 与 backends/base.py:86-98（encode=base64(pickled+md5(pickled+SECRET_KEY))，decode 校验后 pickle.loads）。密钥公开后校验确可被伪造；但 pickle.loads 的代码执行要求攻击者同时能写会话存储（DB 行或会话文件），finding 的 impact 段落明确写了"任何能修改会话存储的攻击者"这一前提，没有夸大；DEBUG 页面（CONFIG-001）还会把密钥直接打印给匿名者。

**判定历史。**

- 复核员同意：密钥硬编码公开 + md5 防篡改校验 + pickle 反序列化三要素均核实。因伪造会话还需会话存储写权限（非纯远程），medium 定级合适。（最弱一环：最弱的一环是"公开的 SECRET_KEY 是否足以让会话完整性校验失效，以及 RCE 措辞是否越界"。我核对了 settings.py:79（SECRET_KEY 明文提交）、app/sessions/models.py:13-19 与 backends/base.py:86-98（encode=base64(pickled+md5(pickled+SECRET_KEY))，decode 校验后 pickle.loads）。密钥公开后校验确可被伪造；但 pickle.loads 的代码执行要求攻击者同时能写会话存储（DB 行或会话文件），finding 的 impact 段落明确写了"任何能修改会话存储的攻击者"这一前提，没有夸大；DEBUG 页面（CONFIG-001）还会把密钥直接打印给匿名者。）

**证据。**

`settings.py:78-79`

```
# Make this unique, and don't share it with anybody.
SECRET_KEY = 'c#0cz^i$lyr6*b*xe-t@0tqc_c3dnju=+c1lk^k7(r^7lhz$g@'
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

`app/sessions/backends/base.py:92-98`

```
    def decode(self, session_data):
        encoded_data = base64.decodestring(session_data)
        pickled, tamper_check = encoded_data[:-32], encoded_data[-32:]
        if md5_constructor(pickled + settings.SECRET_KEY).hexdigest() != tamper_check:
            raise SuspiciousOperation("User tampered with session cookie.")
        try:
            return pickle.loads(pickled)
```

<a id="finding-crypto-001"></a>

### [MEDIUM] 用户口令使用单轮 SHA1 + 弱盐存储

- 编号：`CRYPTO-001`
- 类别：`crypto`
- CWE：`CWE-916`
- 入口身份：无请求入口
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

用户口令以单轮 SHA1（盐仅 5 个 hex 字符）存储，无迭代与加盐强度可言，属于可快速离线爆破的弱口令哈希。

**触发条件。** 所有用户注册、密码重置、管理员建号路径均通过 User.set_password（app/account/models.py:228-234）生成该弱哈希，无需特定请求入口即可被离线攻击。

**影响。** 一旦数据库泄露，攻击者可用 GPU 以极高速度离线爆破口令（单轮 SHA1、仅 5 字符盐、无任何迭代/内存成本），进而接管账号并尝试撞库。

**修复。** 迁移到强口令哈希（PBKDF2-HMAC-SHA256、bcrypt 或 argon2），设置合理的迭代次数，并对存量哈希做登录时重哈希迁移。

**复核员指出的最弱一环。** 最弱的一环是"口令确实以单轮 SHA1+5 字符盐存储且在校验路径上真实使用"。我核对了 app/account/models.py:50-66（get_hexdigest：sha1(salt+raw_password) 单轮）、:228-234（set_password：algo='sha1'，salt = get_hexdigest(...)[:5] 即 5 个 hex 字符，生成 '%s$%s$%s'）、:70-76（check_password 按同一算法比较）；Register.create_activate_user 与表单注册/管理员建号均走该 set_password。盐熵 20 位、无迭代、无内存成本，离线爆破速度极高。

**判定历史。**

- 复核员同意：弱口令哈希事实成立（CWE-916），medium 合理：需要先取得数据库内容才能离线爆破，故不按 high。（最弱一环：最弱的一环是"口令确实以单轮 SHA1+5 字符盐存储且在校验路径上真实使用"。我核对了 app/account/models.py:50-66（get_hexdigest：sha1(salt+raw_password) 单轮）、:228-234（set_password：algo='sha1'，salt = get_hexdigest(...)[:5] 即 5 个 hex 字符，生成 '%s$%s$%s'）、:70-76（check_password 按同一算法比较）；Register.create_activate_user 与表单注册/管理员建号均走该 set_password。盐熵 20 位、无迭代、无内存成本，离线爆破速度极高。）

**证据。**

`app/account/models.py:50-66`

```
def get_hexdigest(algorithm, salt, raw_password):
    """根据 algorithm,salt,raw_password 参数返回加密后的密码字符串。
    支持 'md5', 'sha1' 和 'crypt' 三种加密算法。
    """
    raw_password, salt = smart_str(raw_password), smart_str(salt)
    if algorithm == 'crypt':
        try:
            import crypt
        except ImportError:
            raise ValueError('当前环境不支持 "crypt" 加密算法！')
        return crypt.crypt(raw_password, salt)

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

<a id="finding-crypto-002"></a>

### [MEDIUM] 密码重置令牌熵过低且无过期/防爆破机制

- 编号：`CRYPTO-002`
- 类别：`crypto`
- CWE：`CWE-330`
- 入口身份：匿名
- 置信度：`medium`
- 状态：`confirmed`
- 复核员：同意

密码重置使用的 activation_key 仅含 20 位熵（5 字符 hex 盐），且校验时无过期、无次数限制、用后不失效，可被暴力枚举实现账户接管。

**触发条件。** 匿名攻击者先用目标邮箱调用 /account/password/reset/ 创建/刷新 Register 记录，再枚举 /account/password/reset/<key>/，命中后提交新口令。

**数据流。** 来源：匿名 POST /account/password/reset/ 提交邮箱 → 中间：app/account/views.py:182-191 用 Register.reset_activation_key() 生成 key=sha1(salt+email)，其中 salt 只有 5 个 hex 字符（app/account/models.py:427），密钥空间仅 2^20；key 通过邮件发给用户 → 危险点：app/account/views.py:202-213 password_reset 仅按 key 查 Register 即允许设置新密码，不检查时间戳/过期、不限制尝试次数、成功后也不使 key 失效。攻击者无须收邮件，枚举 2^20 个 key 即可以目标用户身份设置新口令。入口身份：匿名。

**影响。** 攻击者针对已知邮箱的用户申请重置后，离线/在线枚举约 100 万个候选 key（响应 403/200 可区分，且无速率限制），可无需访问邮箱即重置该用户口令，实现账户接管。

**修复。** 改用高熵随机令牌（secrets/os.urandom，至少 128 位），设置短有效期并在校验时检查时间戳，成功后立即作废令牌，并对重置端点做频率限制与失败计数。

**复核员指出的最弱一环。** 最弱的一环是"2^20 枚举是否现实、key 是否真的无过期/无失效"。我核对了 app/account/models.py:424-430（reset_activation_key：salt=sha1(random.random())[:5] 即 5 hex 字符，activation_key=sha1(salt+email)，密钥空间 2^20），app/account/views.py:167-196（匿名可对任意邮箱触发重置/刷新 Register 记录）与 :202-223（password_reset 仅按 key 查库，不检查 updated 时间戳、不限制尝试次数、成功后不删除/重置 key，SetPasswordForm.save 直接 set_password 并保存，见 forms.py:145-170）。注意 salt 来自 random.random()（Mersenne Twister，非 CSPRNG），攻击者若估中随机种子可进一步缩小候选集；即便纯在线枚举，403/200 可区分且无速率限制。

**判定历史。**

- 复核员同意：令牌熵 20 位、无过期、无失败计数、用后不失效，与证据一致；combined with weak randomness 使暴力枚举更可行。置信度 medium、严重性 medium 的标注诚实合理。（最弱一环：最弱的一环是"2^20 枚举是否现实、key 是否真的无过期/无失效"。我核对了 app/account/models.py:424-430（reset_activation_key：salt=sha1(random.random())[:5] 即 5 hex 字符，activation_key=sha1(salt+email)，密钥空间 2^20），app/account/views.py:167-196（匿名可对任意邮箱触发重置/刷新 Register 记录）与 :202-223（password_reset 仅按 key 查库，不检查 updated 时间戳、不限制尝试次数、成功后不删除/重置 key，SetPasswordForm.save 直接 set_password 并保存，见 forms.py:145-170）。注意 salt 来自 random.random()（Mersenne Twister，非 CSPRNG），攻击者若估中随机种子可进一步缩小候选集；即便纯在线枚举，403/200 可区分且无速率限制。）

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

`app/account/views.py:201-223`

```
@render_to('account/password_reset.html')
def password_reset (request, key=None):
    """ 重置用户密码 """

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

        return {'PASSWORD_RESET_DONE':True,}

    return {'NEW_REQUEST':True, 'form':form}
```

<a id="finding-csrf-001"></a>

### [MEDIUM] 全站缺少 CSRF 防护且状态变更端点可被 GET 触发

- 编号：`CSRF-001`
- 类别：`csrf`
- CWE：`CWE-352`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

项目未启用任何 CSRF 中间件，模板也没有 csrf_token；同时大量删除/修改操作可通过 GET 触发（如 del_post、manage_topic、admin del_*、logout），跨站请求可在已登录用户会话下执行这些操作。

**触发条件。** 攻击者让已登录用户访问携带 <img src="http://<站点>/wiki/post/<id>/delete/"> 或跨站自动提交表单的页面；由于无 CSRF 校验，浏览器以受害者会话 Cookie 执行删除等操作。

**数据流。** 来源：浏览器自动携带的会话 Cookie（app/sessions/middleware.py:11 从 Cookie 取 session_key，认证凭 _auth_user_id 存于会话）→ 中间：settings.py:98-104 MIDDLEWARE_CLASSES 未包含 CsrfViewMiddleware，全站无 CSRF 校验；模板中亦无 csrf_token（仓库内无 csrfmiddlewaretoken 命中）→ 危险点：大量状态变更端点对方法不设限，如 app/wiki/views.py:271-283 del_post、:237-268 manage_topic 可用 GET 触发删除，app/admin/views.py:252-257 del_user 等同理；登录/登出（account/views.py:24-60）亦可被跨站触发。入口身份：攻击者匿名构造跨站请求，受害者需已登录（普通用户或管理员）。

**影响。** 攻击者可在第三方页面放置图片/表单，诱使已登录用户（含管理员）的浏览器跨站发起删除主题/帖子、删除用户/目录/权限、发布内容、登出等操作；会话 Cookie 未设 HttpOnly/SameSite，攻击面进一步扩大。

**修复。** 启用 CsrfViewMiddleware 并让所有 POST 表单携带 csrf_token；所有状态变更端点只接受 POST（或 PUT/DELETE）并做 CSRF 校验；登出改为 POST；为会话 Cookie 设置 HttpOnly 与 SameSite。

**复核员指出的最弱一环。** 最弱的一环是"全站确实没有任何 CSRF 防护且存在 GET 可触发的状态变更"。我核对了 settings.py:98-104（MIDDLEWARE_CLASSES 仅 CommonMiddleware + 自定义 Session/Authentication 中间件，无 CsrfViewMiddleware），全仓库 grep csrf_token/csrfmiddlewaretoken/CsrfViewMiddleware 为 0 命中；app/wiki/views.py:271-283 del_post、:237-268 manage_topic、app/admin/views.py:252-257 del_user 均未限制请求方法（GET 即可触发写操作），account/views.py:55-60 logout 也是 GET。会话 Cookie 在 app/sessions/middleware.py:37-41 设置时确实没有 httponly/samesite 参数。

**判定历史。**

- 复核员同意：无 CSRF 中间件、模板无 token、多个写端点 GET 可触发，跨站请求可借受害者会话执行删除/登出等操作。定级 medium 恰当（部分端点有归属校验或权限校验，限制了影响面）。（最弱一环：最弱的一环是"全站确实没有任何 CSRF 防护且存在 GET 可触发的状态变更"。我核对了 settings.py:98-104（MIDDLEWARE_CLASSES 仅 CommonMiddleware + 自定义 Session/Authentication 中间件，无 CsrfViewMiddleware），全仓库 grep csrf_token/csrfmiddlewaretoken/CsrfViewMiddleware 为 0 命中；app/wiki/views.py:271-283 del_post、:237-268 manage_topic、app/admin/views.py:252-257 del_user 均未限制请求方法（GET 即可触发写操作），account/views.py:55-60 logout 也是 GET。会话 Cookie 在 app/sessions/middleware.py:37-41 设置时确实没有 httponly/samesite 参数。）

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

`app/wiki/views.py:271-283`

```
@login_required
def del_post (request, id):

    post = get_object_or_404 (Post, pk=id)
    t_id = post.topic.id

    if post.user != request.user:
        return HttpResponseForbidden('<h1>您没有这个权限！</h1>')

    post.delete()

    url = reverse ('wiki:show_topic', args=[t_id])
    return HttpResponseRedirect(url)
```

`app/sessions/middleware.py:36-41`

```
                request.session.save()
                response.set_cookie(settings.SESSION_COOKIE_NAME,
                        request.session.session_key, max_age=max_age,
                        expires=expires, domain=settings.SESSION_COOKIE_DOMAIN,
                        path=settings.SESSION_COOKIE_PATH,
                        secure=settings.SESSION_COOKIE_SECURE or None)
```

<a id="finding-xss-002"></a>

### [MEDIUM] account.views.register / password_reset 激活 key 未转义反射型 XSS

- 编号：`XSS-002`
- 类别：`xss`
- CWE：`CWE-79`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

注册激活与密码重置两个视图在激活 key 不存在时，把 URL 中的 key 原样拼进 HTML 响应返回，形成匿名可触发的反射型 XSS。

**触发条件。** 匿名 GET /account/register/<payload>/ 或 /account/password/reset/<payload>/，其中 payload 为不含斜杠的 HTML 标签（如 <img src=x onerror=...>，路径参数经 URL 解码后原样进入响应）。

**数据流。** 来源：URL 路径参数 key（app/account/urls.py:8 `(?P<key>.+)/`）→ 中间：app/account/views.py:100 用 key 查询 Register 失败落入 except → 危险点：:102 将 key 直接以字符串格式化拼入 HTML 返回，无任何转义（password_reset 在 :205-208 同样处理）。入口身份：匿名（无需登录即可 GET 这两个地址）。

**影响。** 攻击者诱导受害者点击形如 /account/register/<img src=x onerror=...>/ 的链接即可在受害者浏览器（ylinux 源）执行脚本，可窃取会话 Cookie、伪装登录页面钓鱼。403 响应体仍会被浏览器渲染，因此状态码不构成防护。

**修复。** 不要将 URL 参数直接拼入 HTML 响应；改用模板渲染或对 key 做 HTML 转义（escape），或直接返回不含用户输入的通用错误文案。

**复核员指出的最弱一环。** 最弱的一环是"路径参数能否携带 < > 等字符并原样出现在 HTML 响应里"。我核对了 app/account/urls.py:8 的 `(?P<key>.+)/$`（.+ 不限制字符集，Django 1.x 对解码后的路径做正则匹配），app/account/views.py:96-102 与 202-208 两个视图在 Register.DoesNotExist 时用 `u'<h1>错误的 Key ： %s </h1>' % key` 直接字符串格式化进 HttpResponseForbidden，无任何 escape；HttpResponseForbidden 默认 Content-Type 为 text/html，403 状态码不阻止浏览器渲染。两个端点均无登录装饰器，匿名可达。

**判定历史。**

- 复核员同意：来源（URL path 参数 key，urls.py:8/13 两个路由）、危险点（account/views.py:102 与 :208 未转义回显）、入口身份（匿名）均与代码一致。payload 无需含斜杠即可注入完整标签（如 <img src=x onerror=...>），属于可实际触发的反射型 XSS。medium 定级恰当。（最弱一环：最弱的一环是"路径参数能否携带 < > 等字符并原样出现在 HTML 响应里"。我核对了 app/account/urls.py:8 的 `(?P<key>.+)/$`（.+ 不限制字符集，Django 1.x 对解码后的路径做正则匹配），app/account/views.py:96-102 与 202-208 两个视图在 Register.DoesNotExist 时用 `u'<h1>错误的 Key ： %s </h1>' % key` 直接字符串格式化进 HttpResponseForbidden，无任何 escape；HttpResponseForbidden 默认 Content-Type 为 text/html，403 状态码不阻止浏览器渲染。两个端点均无登录装饰器，匿名可达。）

**证据。**

`app/account/urls.py:8-8`

```
    url(r'^register/(?P<key>.+)/$', 'register', name='complete_register'),
```

`app/account/views.py:99-102`

```
    try:
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

<a id="finding-config-003"></a>

### [LOW] 数据库口令硬编码提交仓库（当前 sqlite 未生效）

- 编号：`CONFIG-003`
- 类别：`config`
- CWE：`CWE-798`
- 入口身份：无请求入口
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

数据库口令（123456）硬编码提交在 settings.py 中；当前生效 ENGINE 为 sqlite3 故暂不使用，但作为 MySQL 凭据模板被提交进仓库。

**触发条件。** 配置层问题：任何人获取仓库源码即拿到 'ylinux'/'123456' 数据库凭据；若部署时启用被注释的 mysql ENGINE 则该凭据直接生效。

**影响。** 弱口令 123456 与用户名随代码公开；当前 ENGINE 为 sqlite3 时该口令不生效，但注释中的 mysql ENGINE 表明这是生产数据库凭据模板，一旦切换数据库引擎或该文件被部署即成为可直接使用的数据库凭据。

**修复。** 从代码中移除数据库口令，改用环境变量/独立配置文件提供，并更换为强口令。

**复核员指出的最弱一环。** 最弱的一环是"该凭据当前是否生效"。我核对了 settings.py:42-53：生效 ENGINE 为 sqlite3（NAME='ylinux'，HOST/PORT 为空），USER='ylinux'、PASSWORD='123456' 对 sqlite 不起作用，mysql ENGINE 被注释。finding 自己也如实标注"当前 sqlite 未生效"，没有把它当高危。

**判定历史。**

- 复核员同意：弱口令数据库凭据模板随代码公开，当前不生效、切换 ENGINE 即生效。作为配置卫生问题记 low 是恰当的，不构成 dispute。（最弱一环：最弱的一环是"该凭据当前是否生效"。我核对了 settings.py:42-53：生效 ENGINE 为 sqlite3（NAME='ylinux'，HOST/PORT 为空），USER='ylinux'、PASSWORD='123456' 对 sqlite 不起作用，mysql ENGINE 被注释。finding 自己也如实标注"当前 sqlite 未生效"，没有把它当高危。）

**证据。**

`settings.py:42-53`

```
DATABASES = {
    'default': {
        # 可选数据库: postgresql_psycopg2 postgresql mysql sqlite3 oracle
        #'ENGINE': 'django.db.backends.mysql',
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'ylinux',
        'USER': 'ylinux',
        'PASSWORD': '123456',
        'HOST': '',
        'PORT': '',
        }
    }
```

<a id="finding-file-002"></a>

### [LOW] 附件下载缺少鉴权与目录权限校验

- 编号：`FILE-002`
- 类别：`access_control`
- CWE：`CWE-862`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

附件下载端点无任何鉴权与目录访问校验，任何匿名用户可按 id 枚举下载任意附件。

**触发条件。** 匿名 GET /ydata/attachment/<自增id>/download/ 即可下载附件（附件 id 为自增整数）。

**数据流。** 来源：URL 参数 id（app/ydata/urls.py:9 `^attachment/(?P<id>\d+)/download/$`）→ 中间：app/ydata/views.py:117-125 get_object_or_404(Attachment,pk=id) 后直接 open(a.get_absolute_path()) 读取文件并返回，无任何登录校验，也不检查附件所属 Topic/Catalog 的 has_access（对比 wiki 视图用 catalog.has_access 控制访问，如 app/wiki/views.py:141）→ 危险点：:126 将文件内容作为 HttpResponse 返回。入口身份：匿名（id 为自增整数，可顺序枚举）。

**影响。** 匿名攻击者按自增 id 顺序枚举即可下载所有附件，包括挂在受限目录（Catalog.groups 控制的 has_access）下的私有附件，造成越权信息泄露。

**修复。** 下载前校验 request.user 对附件所属 Topic 的 Catalog 具有 has_access 权限（或要求登录），并对下载做审计。

**复核员指出的最弱一环。** 最弱的一环是"下载端点确实无鉴权"。我核对了 app/ydata/views.py:117-127：download_attachment 无 @login_required、无权限装饰器，直接 get_object_or_404(Attachment,pk=id) 后 open 读文件并返回；路由 app/ydata/urls.py:9 为 ^attachment/(?P<id>\d+)/download/$，id 自增可枚举。需要指出 impact 里"受限目录下的私有附件"表述偏乐观：wiki/bbs 的读取视图（如 app/wiki/views.py:81-103 topic、:51-79 catalog、:368-388 ajax_show_posts）同样不调用 catalog.has_access，所谓"私有"只限制写不限制读；但这削弱的是私有性论证，不改变"下载端点缺鉴权"这一事实本身。

**判定历史。**

- 复核员同意：匿名可枚举下载任意附件的事实成立，low 定级恰当（受影响的"隐私"边界本身较弱）。（最弱一环：最弱的一环是"下载端点确实无鉴权"。我核对了 app/ydata/views.py:117-127：download_attachment 无 @login_required、无权限装饰器，直接 get_object_or_404(Attachment,pk=id) 后 open 读文件并返回；路由 app/ydata/urls.py:9 为 ^attachment/(?P<id>\d+)/download/$，id 自增可枚举。需要指出 impact 里"受限目录下的私有附件"表述偏乐观：wiki/bbs 的读取视图（如 app/wiki/views.py:81-103 topic、:51-79 catalog、:368-388 ajax_show_posts）同样不调用 catalog.has_access，所谓"私有"只限制写不限制读；但这削弱的是私有性论证，不改变"下载端点缺鉴权"这一事实本身。）

**证据。**

`app/ydata/views.py:117-127`

```
def download_attachment(request, id):

    a = get_object_or_404(Attachment,pk=id)

    a.dtimes += 1
    a.save()

    print a.get_absolute_path()
    f = open(a.get_absolute_path())
    response = HttpResponse(f.read())
    f.close()
```

`app/ydata/urls.py:9-9`

```
    url(r'^attachment/(?P<id>\d+)/download/$', 'download_attachment', name='download_attachment'),
```

<a id="finding-misc-001"></a>

### [LOW] ylab update_post_profile 匿名批量改写帖子数据

- 编号：`MISC-001`
- 类别：`access_control`
- CWE：`CWE-862`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

ylab 的 update_post_profile 是无鉴权的调试端点，匿名 GET 即可批量改写全站 Post 的 touser/updated 字段。

**触发条件。** 匿名 GET /lab/update_post_profile 即触发全表遍历写库，无需任何参数或身份。

**数据流。** 来源：无任何请求参数，仅 GET /lab/update_post_profile（app/ylab/urls.py:8）→ 中间：app/ylab/views.py:37-48 无登录校验、无方法校验，直接遍历全部 Post 改写 touser 与 updated 字段并 save() → 危险点：:39-46 对全站帖子执行批量写库。入口身份：匿名。

**影响。** 任何匿名访问者（含爬虫）反复请求该地址即可持续改写全站帖子的收件人和时间戳字段（updated 被重置为 created），扰乱帖子排序与“回复我”关系，构成数据完整性破坏与低成本 DoS。

**修复。** 删除该调试端点或将其移出生产路由；若需保留则加登录与权限校验、仅允许 POST、并限定处理范围。

**复核员指出的最弱一环。** 最弱的一环是"端点是否真的匿名可达且全表写库"。我核对了 app/ylab/views.py:37-48（update_post_profile 无装饰器、无方法校验，遍历 Post.objects.all() 改写 touser/updated 并逐条 save()）与 app/ylab/urls.py:5-8（映射到 ^update_post_profile$，根部 urls.py:31 以 ^lab/ 挂载）。GET 即触发，匿名成立。

**判定历史。**

- 复核员同意：匿名批量改写全站帖子的数据完整性/低成本 DoS 问题成立。low 定级合理（篡改的是辅助字段 touser/updated，不涉及内容本身）。（最弱一环：最弱的一环是"端点是否真的匿名可达且全表写库"。我核对了 app/ylab/views.py:37-48（update_post_profile 无装饰器、无方法校验，遍历 Post.objects.all() 改写 touser/updated 并逐条 save()）与 app/ylab/urls.py:5-8（映射到 ^update_post_profile$，根部 urls.py:31 以 ^lab/ 挂载）。GET 即触发，匿名成立。）

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

<a id="finding-redir-001"></a>

### [LOW] logout 与管理登录存在开放重定向

- 编号：`REDIR-001`
- 类别：`redirect`
- CWE：`CWE-601`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

logout 视图将 next 参数、管理员登录将 HTTP_REFERER 直接作为重定向目标，未做站内校验，存在开放重定向。

**触发条件。** 匿名访问 /account/logout/?next=https://evil.example/；或攻击者页面链接到 /admin/login/，管理员登录成功后被重定向回该页面。

**数据流。** 来源：GET 参数 next（account.views.logout）与 HTTP_REFERER 请求头（admin.views.login）→ 危险点：app/account/views.py:58-60 将 request.GET.get('next') 直接传给 HttpResponseRedirect；app/admin/views.py:62-65 将 session 中的 previous_url（来源为 :65 的 HTTP_REFERER）直接重定向。两者都不校验目标是否为站内地址。入口身份：匿名（logout 无需登录；admin/login 的重定向发生在管理员登录成功后）。

**影响。** 攻击者构造 /account/logout/?next=http://evil.example 的链接（例如嵌入邮件或论坛）使受害者被重定向到钓鱼站；管理员登录后的 referer 重定向同样可被控制，用于钓鱼或掩盖攻击来源。

**修复。** 重定向前校验目标为站内相对路径（如要求以 / 开头且不含 //），或使用白名单/固定的重定向地址；管理员登录改为固定跳转 /admin/。

**复核员指出的最弱一环。** 最弱的一环是"next/HTTP_REFERER 是否真的未经校验进入重定向"。我核对了 app/account/views.py:55-60（logout 将 request.GET.get('next') 直接传给 HttpResponseRedirect，无站内校验）与 app/admin/views.py:48-66（管理员登录成功后将 session['previous_url']——来源为 HTTP_REFERER——直接重定向）；login 视图（account/views.py:44/38）的 next→session 跳转同类但未被 finding 单独列明，不影响结论。

**判定历史。**

- 复核员同意：两处均未校验目标是否为站内地址，开放重定向成立（logout 匿名可触发、admin 登录场景需管理员交互）。low 定级符合惯例。（最弱一环：最弱的一环是"next/HTTP_REFERER 是否真的未经校验进入重定向"。我核对了 app/account/views.py:55-60（logout 将 request.GET.get('next') 直接传给 HttpResponseRedirect，无站内校验）与 app/admin/views.py:48-66（管理员登录成功后将 session['previous_url']——来源为 HTTP_REFERER——直接重定向）；login 视图（account/views.py:44/38）的 next→session 跳转同类但未被 finding 单独列明，不影响结论。）

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

`app/admin/views.py:62-66`

```
                return HttpResponseRedirect(request.session.get('previous_url','/'))

    else:
        request.session['previous_url'] = request.META.get('HTTP_REFERER', '/')
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

覆盖仓库全部应用代码：settings.py、urls.py、app/ 下 account/admin/home/ydata/wiki/blog/bbs/ylab/me/syndication/sessions 的 urls/views/forms/models/middleware/decorators、lib/ 下 django_xmlrpc 与 ylinux_xmlrpc、vendored lib/markdown 核心（safe_mode 行为），以及关键模板（|safe 渲染点）。未逐一阅读 tests.py 与 scripts 下的部署辅助脚本（除 .htaccess 与 ylinux-client.py），静态资源目录未审计。

## 局限

本审计仅基于静态代码阅读，未实际部署运行；无法验证生产环境是否启用了被注释的 mysql ENGINE、是否设置了 SESSION_ENGINE 覆盖、Web 进程文件系统写权限等部署细节。Django 具体版本仓库中未随附，部分结论（如 403 页渲染、表单错误回显、会话 Cookie 默认属性）基于该时代 Django（约 1.2-1.4）的通常行为推断。攻击利用的成功率（如重置令牌在线枚举、弱哈希离线爆破、路径穿越可达目录）取决于部署环境与数据量。

## 复核意见

本轮唯一待复核的 ACCESS-003（读侧越权）已逐条核实：has_access 全库搜索确认仅 4 个写路径调用（app/wiki/views.py:141/172/192/423），wiki topic/catalog/post/ajax_show_posts、bbs catalog/topic、ydata download_attachment 全部读视图无登录装饰器也无 has_access 调用，中间件（app/account/middleware.py:15-21）只填充 request.user 不做目录控制，wiki/utils.py render_post 也不做权限判断。同意 medium 定级。其余条目上一轮已 agree，本轮抽查了部分关联证据（app/wiki/views.py:156-200、400-447 的写路径 has_access 校验仍在，未推翻已有结论）。我仍保留的一点怀疑：XSS-001/ACCESS-003 的实际影响面依赖部署中是否真有配置了 groups 的目录、以及 Markdown 输出的原始 HTML 是否在其它模板层被二次过滤，但当前代码证据不支持推翻结论。

## 复核缺口

- `G1`（已回应）Catalog 组权限（Catalog.groups + has_access，app/ydata/models.py:91-101）只在写路径上被强制（app/wiki/views.py:141 add_post、:172/:192 add_topic、:423 replayAJAX），所有读取路径都没有调用 has_access：wiki 的 topic（:81-103）、post（:119-128）、catalog（:51-79）、ajax_show_posts（:368-388，匿名渲染全部回复的 body_html）、bbs 的 topic/catalog（app/bbs/views.py:30-56）以及 ydata 的附件下载（app/ydata/views.py:117-127）。结果是"组内可见"的受限目录内容（主题、回复、附件）可以被任何匿名访客直接读取/下载，访问控制模型形同虚设——审计员在 FILE-002 中甚至错误地假设受限目录附件是"私有"的。建议审计员评估该读侧越权并单独成条（预期 medium）。
  - 审计员回应：已核实并单独成条：find_references 确认 has_access 仅被 4 个写路径调用（app/wiki/views.py:141/172/192/423），所有读路径（wiki topic/catalog/post/ajax_show_posts、bbs catalog/topic、ydata download_attachment）均不校验组权限且匿名可达。新增 ACCESS-003（读侧越权，medium，anonymous），证据引用 app/ydata/models.py:91-101、app/wiki/views.py:81-96 与 368-388。
