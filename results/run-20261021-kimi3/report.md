# ylinux_old 应用安全审计报告

- 目标：`https://github.com/gwind/ylinux_old`，commit `8a7316deec88287d020eca21c38dad921b623ffc`
- 模型：审计员 `deepseek-v4-pro`，复核员 `kimi-k3`
- 时间：2026-10-21T10:55:11+08:00 → 2026-10-21T11:18:21+08:00
- 结论：确认 14 个问题，最高严重性为 high。
- 统计：已确认 14，待再确认 1，已排除 0；引用核对 38 条，未通过 0 条

> 这次运行中途中断（原因见文末“运行警告”），复核没有做完，标“未复核”的条目只经过审计员判断。

## 发现总表

| 严重性 | 编号 | 问题 | 入口身份 | 状态 | 复核员 | 位置 |
| --- | --- | --- | --- | --- | --- | --- |
| high | [`ACCESS-002`](#finding-access-002) | XML-RPC 仅认证无授权：任意注册用户可删除全站主题、修改任意主题、绕过目录组权限 | 可自助注册的用户 | confirmed | 未复核 | `lib/ylinux_xmlrpc.py:39` |
| high | [`XSS-001`](#finding-xss-001) | 主题正文存储型 XSS：Markdown 渲染未启用 safe_mode，原始 HTML 原样输出并经 \|safe 渲染 | 可自助注册的用户 | confirmed | 同意 | `app/ydata/models.py:190` |
| high | [`XSS-002`](#finding-xss-002) | 回复正文存储型 XSS：markup='none' 的帖子用无 safe_mode 的 Markdown 渲染并经 \|safe 输出 | 可自助注册的用户 | confirmed | 同意 | `app/wiki/views.py:432` |
| high | [`FILE-001`](#finding-file-001) | 附件上传路径穿越写文件并允许匿名访问上传的 HTML/JS | 可自助注册的用户 | disputed | 否决 | `app/ydata/views.py:78` |
| medium | [`ACCESS-001`](#finding-access-001) | editPostAJAX 缺少帖子属主校验：任意登录用户可修改任意帖子 | 可自助注册的用户 | confirmed | 同意 | `app/wiki/views.py:447` |
| medium | [`CONFIG-001`](#finding-config-001) | DEBUG=True 提交进仓库并暴露媒体目录列表 | 无请求入口 | confirmed | 未复核 | `settings.py:18` |
| medium | [`CONFIG-002`](#finding-config-002) | SECRET_KEY 硬编码并提交进公开仓库 | 无请求入口 | confirmed | 未复核 | `settings.py:79` |
| medium | [`CRYPTO-001`](#finding-crypto-001) | 弱口令哈希：单轮 SHA1+5字符随机盐，可低成本离线爆破 | 无请求入口 | confirmed | 未复核 | `app/account/models.py:62` |
| medium | [`CRYPTO-002`](#finding-crypto-002) | 密码重置/激活令牌熵仅 20bit 且不过期：可枚举重置链接接管账户 | 匿名 | confirmed | 未复核 | `app/account/models.py:361` |
| medium | [`CSRF-001`](#finding-csrf-001) | 全站未启用 CSRF 中间件，所有 Cookie 会话写操作可被跨站伪造 | 无请求入口 | confirmed | 同意 | `settings.py:98` |
| medium | [`REDIRECT-001`](#finding-redirect-001) | 登录/登出/管理员登录基于 next 与 Referer 的开放重定向 | 匿名 | confirmed | 未复核 | `app/account/views.py:42` |
| medium | [`XSS-003`](#finding-xss-003) | 注册/密码重置 key 未转义反射进 403 页面导致反射型 XSS | 匿名 | confirmed | 同意 | `app/account/views.py:96` |
| medium | [`XSS-005`](#finding-xss-005) | 附件文件名未转义拼入正文 HTML 造成属性注入型存储 XSS | 可自助注册的用户 | confirmed | 同意 | `app/ydata/models.py:407` |
| medium | [`SESSION-001`](#finding-session-001) | 会话存储使用 pickle 反序列化 + MD5 校验，签名密钥已提交进仓库 | 无请求入口 | needs_review | 未复核 | `app/sessions/backends/base.py:86` |
| medium | [`XSS-004`](#finding-xss-004) | ylab 上传端点把文件名未转义拼入响应导致匿名反射型 XSS | 匿名 | disputed | 否决 | `app/ylab/views.py:24` |
| low | [`ACCESS-003`](#finding-access-003) | ylab update_post_profile 匿名批量改写全站帖子数据 | 匿名 | confirmed | 同意 | `app/ylab/views.py:37` |
| low | [`CONFIG-003`](#finding-config-003) | 数据库口令 123456 明文提交进仓库 | 无请求入口 | confirmed | 未复核 | `settings.py:42` |

下面的发现由 Agent 写入，每条引用都回到源码核对过。审计员综述写在复核之前，单条发现的状态以复核后为准。线索处置、读过的文件、阶段记录、工具序列和引用核对见 `appendix.md`，关键决策见 `decisions.md`。

## 审计员综述

该仓库是老式 Django（约 1.2/1.3 时代）社区网站 YLinux.org 的完整源码。总体安全状况较差：内容渲染管线（python-markdown 默认 safe_mode=False + 模板 |safe）形成多处存储型 XSS；附件上传存在路径穿越且上传的 HTML/JS 可被匿名访问；XML-RPC 接口只认证不授权，任何自助注册用户可删除全站主题；站点完全没有启用 CSRF 中间件；SECRET_KEY、弱数据库口令、DEBUG=True 均明文提交进仓库；口令哈希为单轮 SHA1+短盐，激活/重置令牌熵仅 20bit 且不过期。共确认 17 项问题（3 项 high XSS、1 项 high 文件上传、1 项 high 授权缺失，其余 medium/low 及 1 项 needs_review 的会话反序列化组合风险）。

## 风险概览

最高风险依次为：1) 存储型 XSS（XSS-001/XSS-002，注册用户发帖即可对所有浏览者执行脚本，老版本会话 Cookie 默认无 HttpOnly 放大为会话劫持/管理员接管）；2) XML-RPC 授权缺失（ACCESS-002，任何注册用户可删除全站主题/篡改任意主题/绕过目录组限制）；3) 上传路径穿越与任意文件托管（FILE-001，可覆盖媒体目录文件并向匿名用户提供可执行 HTML）；4) 会话数据 pickle 反序列化 + 已公开的 MD5 签名密钥（SESSION-001/CONFIG-002，配合任何 DB 写入原语即为 RCE）；5) 全站无 CSRF 防护、开放重定向、弱口令哈希与弱重置令牌等配置/加密弱点。

## 已确认的问题

<a id="finding-access-002"></a>

### [HIGH] XML-RPC 仅认证无授权：任意注册用户可删除全站主题、修改任意主题、绕过目录组权限

- 编号：`ACCESS-002`
- 类别：`access_control`
- CWE：`CWE-862`
- 入口身份：可自助注册的用户
- 置信度：`high`
- 状态：`confirmed`
- 复核员：未复核

XML-RPC 接口（/xmlrpc/）对 delete_topic、delete_all_topic、edit_topic、new_topic 只校验用户名密码、不做任何属主或权限校验：任何注册用户都能删除全部主题、修改任意主题、绕过 Catalog 的 has_access 组限制发帖。

**触发条件。** 以任意注册账号调用 XML-RPC 方法 ylinux_xmlrpc.delete_all_topic / delete_topic / metaWeblog.editPost / metaWeblog.newPost。

**数据流。** 来源：XML-RPC 请求参数（/xmlrpc/ 路由，lib/django_xmlrpc/views.py:74-87 分发）→ lib/ylinux_xmlrpc.py 的 has_auth(user, passwd) 只做认证（:39-45），delete_topic/delete_all_topic/edit_topic/new_topic 在认证通过后不再做任何属主或权限校验 → :66 Topic.objects.all().delete() 全站删除、:174-176 改任意主题名、:199-205 可向任意 catalog（包括组限制目录）发帖。注册开放（account.request_register 匿名可达），任何自助注册用户都拥有合法凭证。

**影响。** 任何自助注册的用户即可：删除全站所有主题（级联删除回复，不可恢复）、修改/篡改任意主题标题与正文（结合 XSS-001 注入脚本）、向仅限特定用户组访问的目录发帖，构成全站内容完整性破坏。

**修复。** 在 XML-RPC 方法里增加授权：删除/编辑校验主题属主或管理权限；new_topic 调用 catalog.has_access 检查；对 delete_all_topic 要求 superuser；限制 XML-RPC 为 HTTPS 并加速率限制。

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

`lib/ylinux_xmlrpc.py:168-176`

```
def edit_topic(postid, user, passwd, struct, publish):
    '''Edit one topic'''
    if not has_auth(user, passwd):
        raise Fault(-1, "Authentication Failure")

    try:
        topic = Topic.objects.get(pk=postid)
        if struct.has_key('title'):
            topic.name = st(struct['title'], 'utf-8')
```

<a id="finding-xss-001"></a>

### [HIGH] 主题正文存储型 XSS：Markdown 渲染未启用 safe_mode，原始 HTML 原样输出并经 |safe 渲染

- 编号：`XSS-001`
- 类别：`xss`
- CWE：`CWE-79`
- 入口身份：可自助注册的用户
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

Topic.save_file 用 Markdown(extensions=['fenced_code']).convertFile 渲染正文时没有传 safe_mode，而本仓库自带的 python-markdown 默认 safe_mode=False，攻击者在主题正文里写的 <script> 等原始 HTML 会被原样写进 .html 文件；wiki/topic.html 和 bbs/topic.html 又用 {{ topic.body_html|safe }} 输出，形成存储型 XSS。任何注册用户发帖即可向所有匿名浏览者投放脚本。

**触发条件。** 登录用户在 /wiki/catalog/<id>/addtopic/ 提交的 text 字段（AddTopicForm），或 XML-RPC metaWeblog.newPost / editPost 的 description 字段，最终进入 Topic.save_file。

**数据流。** 来源：AddTopicForm.text（POST，登录用户，app/ydata/forms.py:97-98）或 XML-RPC struct['description']（lib/ylinux_xmlrpc.py:181/211）→ 中间：topic.save_file(text) → app/ydata/models.py:198-200 Markdown(...).convertFile(...)（无 safe_mode，lib/markdown/__init__.py:188 默认 safe_mode=False）把原始 HTML 写入 body_html_path → 危险点：templates/wiki/topic.html:54 与 templates/bbs/topic.html:23 的 {{ topic.body_html|safe }} 原样输出。发帖需登录（registered_open），浏览受害者页面无需登录。

**影响。** 任何能创建/编辑主题的用户（注册开放，任何人可自助注册）可注入任意 JS，对所有浏览该主题的匿名用户执行：窃取会话 Cookie（老版本 Django 会话 Cookie 默认不带 HttpOnly）、以受害者身份执行发帖/删帖/上传等操作，可对管理员账户实现接管。

**修复。** 渲染用户内容时启用 safe_mode='escape'（与 Post 的 markdown 分支一致），或改用专门的安全 HTML 白名单库（如 bleach）过滤后输出；模板中去掉 |safe，改用可信任的 HTML 字段并对其做白名单过滤；升级 markdown 库。

**复核员指出的最弱一环。** 最弱一环是"注册开放（registered_open）"这一攻击者前提是否属实，以及 ylinux_text_filter 是否在 Markdown 之前做了转义。核实结果：account.views.request_register（views.py:63-93）只有 @render_to，无登录要求，匿名即可申请注册链接，注册开放成立；ylinux_text_filter（models.py:396-452）只做 [a:]/[w:]/[i:] 引用替换，不做任何 HTML 转义；lib/markdown/__init__.py:188 确认 safe_mode 默认 False，models.py:198-200 convertFile 未传 safe_mode，原始 HTML 原样写入 body_html_path；wiki/topic.html:54 与 bbs/topic.html:23 均 |safe 输出。add_topic 视图（views.py:183-208）@login_required + catalog.has_access 校验存在但任何注册用户都能通过。

**判定历史。**

- 复核员同意：完整核对来源（AddTopicForm.text，forms.py:97-98 → topic.save_file）、中间环节（无 safe_mode、无转义）与危险点（两处模板 |safe），链路每一环都在代码中得到证实。自定义会话中间件 set_cookie 未传 httponly（sessions/middleware.py:37-41），会话 Cookie 可被 JS 读取，影响评估成立。存储型 XSS、开放注册攻击者、匿名受害者，high 合理。（最弱一环：最弱一环是"注册开放（registered_open）"这一攻击者前提是否属实，以及 ylinux_text_filter 是否在 Markdown 之前做了转义。核实结果：account.views.request_register（views.py:63-93）只有 @render_to，无登录要求，匿名即可申请注册链接，注册开放成立；ylinux_text_filter（models.py:396-452）只做 [a:]/[w:]/[i:] 引用替换，不做任何 HTML 转义；lib/markdown/__init__.py:188 确认 safe_mode 默认 False，models.py:198-200 convertFile 未传 safe_mode，原始 HTML 原样写入 body_html_path；wiki/topic.html:54 与 bbs/topic.html:23 均 |safe 输出。add_topic 视图（views.py:183-208）@login_required + catalog.has_access 校验存在但任何注册用户都能通过。）

**证据。**

`app/ydata/models.py:190-200`

```
    def save_file(self, text):
        dirname = os.path.dirname(self.body_path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)	
        f = file(self.body_path, 'w')
        f.write(text)
        f.close()

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

`templates/wiki/topic.html:54-54`

```
    {{ topic.body_html|safe }}
```

`templates/bbs/topic.html:23-23`

```
    {{ topic.body_html|safe }}
```

<a id="finding-xss-002"></a>

### [HIGH] 回复正文存储型 XSS：markup='none' 的帖子用无 safe_mode 的 Markdown 渲染并经 |safe 输出

- 编号：`XSS-002`
- 类别：`xss`
- CWE：`CWE-79`
- 入口身份：可自助注册的用户
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

发表回复的主要路径（wiki.views.replayAJAX、AddPostForm.save）把帖子保存为 markup='none'，Post.save() 对该分支用 Markdown(...).convert(ylinux_text_filter(self.body)) 渲染，未启用 safe_mode，正文中的原始 HTML 原样进入 body_html；随后在 wiki/utils.py 的 POST_MAIN、templates/wiki/post.html、editPostAJAX.html、replayAJAX.html 及 bbs/topic.html 中以 |safe 输出，形成存储型 XSS。

**触发条件。** POST /wiki/topic/<id>/replayAJAX/ 或 /wiki/post/<id>/replayAJAX/ 的 body 参数，以及 /wiki/topic/<id>/addpost/ 的 body 字段（登录用户）。

**数据流。** 来源：request.POST.get("body")（app/wiki/views.py:432）→ Post(topic=..., markup='none', body=post_body)（:435）→ Post.save() 的 markup=='none' 分支 app/ydata/models.py:260 Markdown(extensions=['fenced_code']).convert(ylinux_text_filter(self.body))（无 safe_mode，原始 HTML 通过）→ 存储进 Post.body_html → 危险点：app/wiki/utils.py:18 的 {{ post.body_html|safe }}（经 render_post/HTTP 响应输出）、templates/wiki/post.html:12、templates/wiki/editPostAJAX.html:19、templates/wiki/replayAJAX.html:16、templates/bbs/topic.html:30。发帖需登录（registered_open），受害者浏览无需登录。

**影响。** 任何注册用户在任意可回复主题里发帖即可注入 JS，对匿名浏览者执行：窃取会话、冒充受害者操作、对管理员会话的接管。所有主题页、帖子页、论坛页都是触发面。

**修复。** 对 markup='none'（以及所有用户输入渲染路径）启用 safe_mode='escape' 或白名单 HTML 过滤；在模板侧对不可信 HTML 一律转义，仅在经过白名单过滤后用 |safe。

**复核员指出的最弱一环。** 最弱一环是 markup='none' 分支是否真的不转义、以及 urlize() 是否可能充当过滤。核实：models.py:258-260 对 markup='none' 用无 safe_mode 的 Markdown.convert 渲染，原始 HTML 直接通过；:264 的 urlize 只做 URL 自动链接，不转义 HTML；replayAJAX 虽注释掉了 @login_required（views.py:394），但 :399 有手动 is_authenticated() 检查，攻击者仍需登录（registered_open 成立，注册匿名开放）；add_post（:132-161）与 AddPostForm.save（forms.py:46）同样落 markup='none'。输出点 wiki/utils.py:18、bbs/topic.html:30、wiki/post.html 等均 |safe。

**判定历史。**

- 复核员同意：来源（request.POST["body"]）、渲染路径（无 safe_mode 的 Markdown + 无转义的 ylinux_text_filter）、存储字段（Post.body_html）与多个 |safe 输出点逐一核对无误，链条完整。影响与 XSS-001 同类，high 合理。（最弱一环：最弱一环是 markup='none' 分支是否真的不转义、以及 urlize() 是否可能充当过滤。核实：models.py:258-260 对 markup='none' 用无 safe_mode 的 Markdown.convert 渲染，原始 HTML 直接通过；:264 的 urlize 只做 URL 自动链接，不转义 HTML；replayAJAX 虽注释掉了 @login_required（views.py:394），但 :399 有手动 is_authenticated() 检查，攻击者仍需登录（registered_open 成立，注册匿名开放）；add_post（:132-161）与 AddPostForm.save（forms.py:46）同样落 markup='none'。输出点 wiki/utils.py:18、bbs/topic.html:30、wiki/post.html 等均 |safe。）

**证据。**

`app/wiki/views.py:432-435`

```
        post_body = request.POST.get("body", None)
        if len(post_body) < 2:
            return {'error': u'您的回复太短，至少2个字符！'}
        post = Post(topic = topic, user = request.user, user_ip = ip, markup = 'none', body = post_body, parent = parent_post)
```

`app/ydata/models.py:258-260`

```
        elif self.markup == 'none':
            #self.body_html = self.body
            self.body_html = Markdown(extensions=['fenced_code']).convert(ylinux_text_filter(self.body))
```

`app/wiki/utils.py:18-18`

```
  <p>{{ post.body_html|safe }}</p>
```

`templates/bbs/topic.html:30-30`

```
    {{ p.body_html|safe }}
```

<a id="finding-access-001"></a>

### [MEDIUM] editPostAJAX 缺少帖子属主校验：任意登录用户可修改任意帖子

- 编号：`ACCESS-001`
- 类别：`access_control`
- CWE：`CWE-639`
- 入口身份：可自助注册的用户
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

editPostAJAX 只要求登录、不校验帖子归属，任何登录用户都能修改任意帖子的内容，属于水平越权（同文件 edit_topic/del_post 均有属主校验，此处遗漏）。

**触发条件。** 登录用户 POST /wiki/post/<任意postID>/editAJAX/，body 参数为要写入的内容。

**数据流。** 来源：URL 参数 postID → app/wiki/views.py:451 get_object_or_404(Post, pk=postID) → 视图只有 @login_required，没有任何 post.user == request.user 之类的属主校验（对比同文件 del_post:277、edit_topic:217 都有校验）→ :456-460 直接把 request.POST.get('body') 写进 post.body 并 save()。任何登录用户可修改任意帖子。

**影响。** 任意注册用户可篡改全站任何人的帖子内容（水平越权），结合 XSS-002 的渲染路径还能往他人帖子里注入脚本，造成大规模内容污染与凭证窃取。

**修复。** 在 editPostAJAX 中校验 post.user == request.user（或权限），与 edit_topic/del_post 保持一致；同时校验请求方法。

**复核员指出的最弱一环。** 最弱一环是"没有任何属主校验"是否为真。核实 views.py:447-467 全函数：仅 @login_required + get_object_or_404，随后直接把 request.POST['body'] 写入 post.body 并 save()，确实无 post.user == request.user 或权限检查；对照同文件 del_post:277、edit_topic:217 都有 if post/topic.user != request.user: return HttpResponseForbidden，遗漏属实。wiki/urls.py:54 路由存在，注册开放，任何登录用户可达。

**判定历史。**

- 复核员同意：对照同文件 edit_topic:217、manage_topic:242、del_post:277 均有属主校验，唯独 editPostAJAX 缺失，属水平越权，结论与代码一致。结合 XSS-002 渲染链路可放大影响，但单独立即影响是篡改任意帖子内容，medium 合理（也可议 high，维持 medium 不算错）。（最弱一环：最弱一环是"没有任何属主校验"是否为真。核实 views.py:447-467 全函数：仅 @login_required + get_object_or_404，随后直接把 request.POST['body'] 写入 post.body 并 save()，确实无 post.user == request.user 或权限检查；对照同文件 del_post:277、edit_topic:217 都有 if post/topic.user != request.user: return HttpResponseForbidden，遗漏属实。wiki/urls.py:54 路由存在，注册开放，任何登录用户可达。）

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

<a id="finding-config-001"></a>

### [MEDIUM] DEBUG=True 提交进仓库并暴露媒体目录列表

- 编号：`CONFIG-001`
- 类别：`config`
- CWE：`CWE-489`
- 入口身份：无请求入口
- 置信度：`high`
- 状态：`confirmed`
- 复核员：未复核

settings.py 把 DEBUG 固定为 True 并提交进仓库；urls.py 在 DEBUG 下用 django.views.static.serve 以 show_indexes=True 暴露 MEDIA_ROOT 目录列表，生产部署若沿用将泄漏调试回溯与媒体目录结构。

**触发条件。** 配置项本身生效即触发：DEBUG=True 时任何未捕获异常返回调试页；/ymedia/ 任何路径可浏览目录。

**影响。** 生产环境若沿用此配置：任何异常都会向攻击者回显完整回溯（含 SECRET_KEY、数据库名、源码路径等敏感信息）；/ymedia/ 提供带目录列表的静态服务，可枚举媒体目录下所有上传文件。

**修复。** 生产环境设置 DEBUG=False 并配置 500/404 模板；不要用 static.serve 提供媒体目录，由前端 Web 服务器以受限配置提供并关闭目录索引。

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

### [MEDIUM] SECRET_KEY 硬编码并提交进公开仓库

- 编号：`CONFIG-002`
- 类别：`config`
- CWE：`CWE-798`
- 入口身份：无请求入口
- 置信度：`high`
- 状态：`confirmed`
- 复核员：未复核

Django SECRET_KEY 以明文硬编码在提交进公开仓库的 settings.py 中，且被会话签名（app/sessions/backends/base.py）等机制直接使用，密钥等同公开。

**触发条件。** 任何人可读 settings.py:79 获取密钥；它被 app/sessions/backends/base.py:89/95、app/sessions/models.py:18/63 用作会话数据签名。

**影响。** 任何能读到仓库的人（含所有曾访问过源码的人）都持有会话签名密钥，可用于伪造会话数据签名（配合 SESSION-001 的 DB 写入即 RCE）、伪造令牌类数据，并削弱所有依赖该密钥的完整性保护。

**修复。** 从版本库删除硬编码密钥，改为环境变量/独立部署配置文件提供；历史提交中的密钥视为已泄露，立即轮换。

**证据。**

`settings.py:79-79`

```
SECRET_KEY = 'c#0cz^i$lyr6*b*xe-t@0tqc_c3dnju=+c1lk^k7(r^7lhz$g@'
```

<a id="finding-crypto-001"></a>

### [MEDIUM] 弱口令哈希：单轮 SHA1+5字符随机盐，可低成本离线爆破

- 编号：`CRYPTO-001`
- 类别：`crypto`
- CWE：`CWE-916`
- 入口身份：无请求入口
- 置信度：`high`
- 状态：`confirmed`
- 复核员：未复核

用户口令使用单轮 SHA1（或 MD5/crypt）哈希存储，盐为 random.random() 派生的 5 字符短盐，无任何迭代成本，等于明文口令库的弱保护。

**触发条件。** 用户注册/改密/管理员建用户时经 User.set_password 生成哈希；攻击面是口令数据库泄露后的离线爆破。

**影响。** 口令哈希为单轮 SHA1(salt+password)、盐只有 5 个十六进制字符（20bit）且源自可预测的 random.random()，数据库一旦泄露，攻击者可用 GPU 以极低成本批量恢复绝大多数口令并复用。

**修复。** 改用带高成本因子的算法（bcrypt/scrypt/argon2 或至少 PBKDF2 数十万次迭代）；盐用 secrets/os.urandom 生成且长度≥16 字节；迁移到 Django 标准口令哈希器。

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

<a id="finding-crypto-002"></a>

### [MEDIUM] 密码重置/激活令牌熵仅 20bit 且不过期：可枚举重置链接接管账户

- 编号：`CRYPTO-002`
- 类别：`crypto`
- CWE：`CWE-640`
- 入口身份：匿名
- 置信度：`medium`
- 状态：`confirmed`
- 复核员：未复核

注册激活与密码重置共用 Register.activation_key，其生成仅依赖 5 个十六进制字符（20bit）的 random.random() 派生盐加 email，密钥空间小且无过期/失效机制，密码重置链接可被枚举或暴力猜解。

**触发条件。** 匿名调用 POST /account/password/reset/ 为目标邮箱生成重置 key，然后遍历 /account/password/reset/<key>/ 枚举；注册激活 key 同样受影响。

**影响。** 密码重置链接的密钥空间只有 2^20（约 100 万），且重置/注册端点无速率限制、密钥无过期时间、重置成功后也不失效；攻击者为受害者邮箱申请重置后，可在可接受时间内枚举出正确 key 并为受害者设置新密码，实现账户接管。

**修复。** 激活/重置令牌改用 secrets.token_urlsafe(32) 或带 SECRET_KEY 的 HMAC（含时间戳与过期时间），并加入速率限制、设置有效期、重置成功后删除 Register 记录。

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

### [MEDIUM] 全站未启用 CSRF 中间件，所有 Cookie 会话写操作可被跨站伪造

- 编号：`CSRF-001`
- 类别：`csrf`
- CWE：`CWE-352`
- 入口身份：无请求入口
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

MIDDLEWARE_CLASSES 中没有启用任何 CSRF 中间件（本项目对应老版 Django，CSRF 需显式配置），所有依赖 Cookie 会话的写操作端点（登录、发帖、编辑、删除、管理员管理操作）都没有 CSRF 防护。

**触发条件。** 全局中间件配置问题：settings.py 的 MIDDLEWARE_CLASSES 缺少 CSRF 中间件，因此所有写操作视图默认不校验 Origin/Referer/token。

**影响。** 攻击者可构造跨站页面让已登录用户的浏览器自动向登录、发帖、编辑帖子、删除主题、管理员用户/权限/目录管理等写操作端点发请求，借受害者的会话执行任意状态变更；管理员相关端点被 CSRF 即等同于权限提升。

**修复。** 启用 Django 的 CsrfViewMiddleware（或 csrf_protect 装饰器），并在所有写操作表单/模板加入 {% csrf_token %}；对 XML-RPC 保持独立（认证凭证在请求体内）。

**复核员指出的最弱一环。** 最弱一环是"该版本 Django 需要显式启用 CSRF 中间件、而配置里确实没有"。核实 settings.py:98-104：MIDDLEWARE_CLASSES 只有 CommonMiddleware + 自定义 Session/Authentication 中间件，无 CsrfViewMiddleware；搜索全仓库也无 csrf_protect 装饰器（仅 django_xmlrpc/views.py 有 csrf_exempt，方向相反）；该代码指向 Django 1.3–1.5 时代，CSRF 确实默认不启用。会话认证依赖 Cookie（sessions/middleware.py:37-41 set_cookie 无 httponly/无 samesite），写操作端点众多（wiki/ydata/admin）。

**判定历史。**

- 复核员同意：全站无 CSRF 防护与代码事实一致；所有依赖会话 Cookie 的写操作（发帖、编辑、删除、后台管理）均可被跨站伪造，且注册开放。考虑到需要受害者已登录/有权限这一前提，medium 可接受（评 high 也有道理，但 medium 不算错）。（最弱一环：最弱一环是"该版本 Django 需要显式启用 CSRF 中间件、而配置里确实没有"。核实 settings.py:98-104：MIDDLEWARE_CLASSES 只有 CommonMiddleware + 自定义 Session/Authentication 中间件，无 CsrfViewMiddleware；搜索全仓库也无 csrf_protect 装饰器（仅 django_xmlrpc/views.py 有 csrf_exempt，方向相反）；该代码指向 Django 1.3–1.5 时代，CSRF 确实默认不启用。会话认证依赖 Cookie（sessions/middleware.py:37-41 set_cookie 无 httponly/无 samesite），写操作端点众多（wiki/ydata/admin）。）

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

<a id="finding-redirect-001"></a>

### [MEDIUM] 登录/登出/管理员登录基于 next 与 Referer 的开放重定向

- 编号：`REDIRECT-001`
- 类别：`redirect`
- CWE：`CWE-601`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：未复核

登录/登出/管理员登录的重定向目标直接取自 GET 的 next 参数或 HTTP_REFERER，无任何白名单校验，形成开放重定向。

**触发条件。** 访问 /account/login/?next=http://evil.com/ 后登录，或 /account/logout/?next=http://evil.com/；管理员登录页的 Referer 由攻击者可控页面设置。

**数据流。** 来源：GET 参数 next（app/account/views.py:44 存入 session['login_redirect_url']、:58 直接取用）与 HTTP Referer（app/admin/views.py:65 存入 session['previous_url']）→ 危险点：登录成功后 HttpResponseRedirect(session.get('login_redirect_url')...)（app/account/views.py:38）、logout 的 HttpResponseRedirect(previous_url or '/')（:60）、admin 登录成功 HttpResponseRedirect(session.get('previous_url','/'))（app/admin/views.py:62）。全程无 URL 白名单/域校验。login/logout 匿名可达。

**影响。** 攻击者可构造 ?next=https://evil 的登录/登出链接诱导受害者点击，登录成功后浏览器被带到钓鱼页面，用于凭据/会话钓鱼；管理员登录页还信任 HTTP_REFERER，存在同样的跳转利用。

**修复。** 对重定向目标做校验：只允许站内相对路径（is_safe_url）或以白名单域名开头；不使用 HTTP_REFERER 作为跳转目标。

**证据。**

`app/account/views.py:42-44`

```
    else:
        # 形如 "http://127.0.0.1:8000/account/login?next=/admin/" 的 url 可以得到 next 值
        request.session['login_redirect_url'] = request.GET.get('next')
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

`app/admin/views.py:62-65`

```
                return HttpResponseRedirect(request.session.get('previous_url','/'))

    else:
        request.session['previous_url'] = request.META.get('HTTP_REFERER', '/')
```

<a id="finding-xss-003"></a>

### [MEDIUM] 注册/密码重置 key 未转义反射进 403 页面导致反射型 XSS

- 编号：`XSS-003`
- 类别：`xss`
- CWE：`CWE-79`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

注册激活（/account/register/<key>/）和密码重置（/account/password/reset/<key>/）视图在 key 不存在时把 URL 中的 key 原样拼进 HttpResponseForbidden 返回的 HTML，没有任何转义，形成匿名可达的反射型 XSS。

**触发条件。** 访问 /account/register/<payload>/ 或 /account/password/reset/<payload>/，payload 为不存在的激活 key（任意字符串，含 HTML）。

**数据流。** 来源：URL 路径参数 key（urls：r'^register/(?P<key>.+)/$'、r'^password/reset/(?P<key>.+)/$'）→ Register.objects.get(activation_key=key) 抛 DoesNotExist → 危险点：app/account/views.py:102 与 :208 把 key 未转义地拼进 HttpResponseForbidden 的 HTML 直接返回（默认 text/html）。匿名可达。

**影响。** 攻击者构造带 HTML/JS 的注册或重置 URL（无需斜杠即可注入，如 <img src=x onerror=...>），诱导受害者点击后在站点源上执行脚本，可用于窃取会话或钓鱼。

**修复。** 将 key 视为不可信数据，返回前用 escape() 转义，或改为固定的错误文案不拼接输入。

**复核员指出的最弱一环。** 最弱一环是 URL 正则是否允许注入 HTML 元字符。核实 account/urls.py:8 与 :13：两个路由均为 (?P<key>.+)，对字符无任何限制，<、>、"、空格之外的注入字符都可进入 key；views.py:102 与 :208 在 DoesNotExist 分支把 key 用 % 直接拼进 HttpResponseForbidden 的 HTML 字符串返回，无 escape；HttpResponse 默认 text/html。匿名可达，两个端点均无需登录。

**判定历史。**

- 复核员同意：反射型 XSS 链路（URL 参数 → 未转义拼接 → text/html 响应）完整成立，匿名可触发。medium 与"需诱导点击的反射型 XSS"相符，不过高。（最弱一环：最弱一环是 URL 正则是否允许注入 HTML 元字符。核实 account/urls.py:8 与 :13：两个路由均为 (?P<key>.+)，对字符无任何限制，<、>、"、空格之外的注入字符都可进入 key；views.py:102 与 :208 在 DoesNotExist 分支把 key 用 % 直接拼进 HttpResponseForbidden 的 HTML 字符串返回，无 escape；HttpResponse 默认 text/html。匿名可达，两个端点均无需登录。）

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

`app/account/views.py:205-208`

```
    try:
        register = Register.objects.get(activation_key=key)
    except Register.DoesNotExist:
        return HttpResponseForbidden(u'<h1>错误的 Key ： %s </h1>' % key)
```

<a id="finding-xss-005"></a>

### [MEDIUM] 附件文件名未转义拼入正文 HTML 造成属性注入型存储 XSS

- 编号：`XSS-005`
- 类别：`xss`
- CWE：`CWE-79`
- 入口身份：可自助注册的用户
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

ydata 的附件/图片引用替换（ylinux_text_filter）把上传时用户可控的附件文件名不转义地拼进生成的 <a>/<img> HTML，这些 HTML 又随正文经过无 safe_mode 的 Markdown 渲染并 |safe 输出，攻击者可在文件名里注入事件处理器造成存储型 XSS。

**触发条件。** 登录用户上传文件名为 HTML 标签/属性的附件，然后在主题或回复正文中引用 [a:附件ID] 或 [i:附件ID]。

**数据流。** 来源：上传文件名（ydata.views.upload_single_file 的 req.FILES['single_file'].name）→ 存入 Attachment.name → 发帖正文中的 [a:ID]/[i:ID] 引用被 ylinux_text_filter 替换：app/ydata/models.py:408 把 a.name 原样拼进 <a href=...> 的标签体、:444 把 img.name 原样拼进 <img alt="..."> 属性 → 该 HTML 随正文进入 Markdown 渲染（topic 与 markup='none' 的 post 均无 safe_mode，见 XSS-001/XSS-002）→ body_html 经 |safe 输出。攻击者为登录用户（上传与发帖），受害者匿名浏览。

**影响。** 登录用户上传一个文件名含 HTML 的附件（如 <img src=x onerror=...>.txt）并在帖子中引用 [a:ID]，即可把脚本注入帖子正文，对所有浏览者执行，构成存储型 XSS。

**修复。** 在 ylinux_text_filter 里对 a.name/img.name 做 HTML 属性与标签体转义（escape）；上传时用安全的随机文件名代替用户文件名显示；正文渲染启用 safe_mode。

**复核员指出的最弱一环。** 最弱一环是上传文件名能否真的携带 HTML 元字符到达拼接点。核实：ydata/views.py:78/86 的 f.name 经 Django UploadedFile basename 清洗后仍保留引号/尖括号（basename 只切路径），Attachment.name 原样入库；ylinux_text_filter（models.py:396-452）对 [a:ID]/[i:ID] 的替换把 a.name 直接插进 <a> 标签体、img.name 插进 <img alt="..."> 属性（:408、:444），无任何转义；该 HTML 随正文经无 safe_mode 的 Markdown 渲染并 |safe 输出（见 XSS-001/002 证据）。文件名形如 x"><script>... 即可闭合 alt 属性注入。

**判定历史。**

- 复核员同意：来源（上传文件名，登录用户可控）、拼接点（models.py:408/444 无转义）、渲染链路（无 safe_mode Markdown + 模板 |safe，与 XSS-001/002 相同）逐环核实成立，构成登录用户投放、匿名受害的存储型 XSS。medium 可接受（相对 XSS-001/002 多一步上传动作，不再上调）。（最弱一环：最弱一环是上传文件名能否真的携带 HTML 元字符到达拼接点。核实：ydata/views.py:78/86 的 f.name 经 Django UploadedFile basename 清洗后仍保留引号/尖括号（basename 只切路径），Attachment.name 原样入库；ylinux_text_filter（models.py:396-452）对 [a:ID]/[i:ID] 的替换把 a.name 直接插进 <a> 标签体、img.name 插进 <img alt="..."> 属性（:408、:444），无任何转义；该 HTML 随正文经无 safe_mode 的 Markdown 渲染并 |safe 输出（见 XSS-001/002 证据）。文件名形如 x"><script>... 即可闭合 alt 属性注入。）

**证据。**

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

<a id="finding-access-003"></a>

### [LOW] ylab update_post_profile 匿名批量改写全站帖子数据

- 编号：`ACCESS-003`
- 类别：`access_control`
- CWE：`CWE-306`
- 入口身份：匿名
- 置信度：`high`
- 状态：`confirmed`
- 复核员：同意

/lab/update_post_profile 是一个无鉴权、无方法限制的批量写库端点，任何匿名请求都会触发对全部 Post 记录的修改。

**触发条件。** 直接访问 GET /lab/update_post_profile。

**数据流。** 来源：无任何输入即可触发（GET/POST 均可，app/ylab/views.py:37-48 没有方法检查也没有登录/权限装饰器，urls.py:8 直接暴露 /lab/update_post_profile）→ 对全表 Post 逐条修改 touser/updated 并 p.save() 写库。匿名可达。

**影响。** 任何匿名用户（甚至只是 GET 请求/图片链接）都能触发全站帖子的批量改写，破坏帖子时间线（updated 被重置为 created）等数据完整性。

**修复。** 删除该调试端点，或加 @login_required/@permission_required 与 POST 方法检查。

**复核员指出的最弱一环。** 最弱一环是"无鉴权无方法限制"是否属实。核实 ylab/views.py:37-48 函数体：无任何装饰器（对照同文件 import 了 login_required/permission_required 却未用），无 req.method 检查，GET 即触发对 Post 全表逐条 p.save()；ylab/urls.py:8 直接暴露该路由。影响仅为 touser/updated 字段被批量改写（updated 重置为 created），不改正文，属于数据完整性骚扰。

**判定历史。**

- 复核员同意：无鉴权、无方法限制的全表写端点，证据与代码完全一致。影响是把所有帖子的 touser/updated 重置（数据完整性骚扰，非毁灭性），low 合理。（最弱一环：最弱一环是"无鉴权无方法限制"是否属实。核实 ylab/views.py:37-48 函数体：无任何装饰器（对照同文件 import 了 login_required/permission_required 却未用），无 req.method 检查，GET 即触发对 Post 全表逐条 p.save()；ylab/urls.py:8 直接暴露该路由。影响仅为 touser/updated 字段被批量改写（updated 重置为 created），不改正文，属于数据完整性骚扰。）

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

`app/ylab/urls.py:8-8`

```
    url(r'^update_post_profile$', 'update_post_profile', name='update_post_profile'),
```

<a id="finding-config-003"></a>

### [LOW] 数据库口令 123456 明文提交进仓库

- 编号：`CONFIG-003`
- 类别：`config`
- CWE：`CWE-798`
- 入口身份：无请求入口
- 置信度：`high`
- 状态：`confirmed`
- 复核员：未复核

settings.py 把数据库口令 '123456' 明文提交进仓库（当前 ENGINE 为 sqlite3 时该口令不生效，但文件中保留了 mysql 引擎切换与同一口令，属已提交的弱凭据）。

**触发条件。** 部署方把 ENGINE 切换为注释中的 mysql 或复用该口令时即生效；凭据本身已随仓库公开。

**影响。** 若部署切换到注释中的 MySQL 引擎（或生产配置沿用同一口令），数据库凭据即为弱口令 123456，可被直接猜解登录数据库。

**修复。** 删除仓库中的数据库口令，改用环境变量/密钥管理；使用强随机口令并限制数据库访问源。

**证据。**

`settings.py:42-52`

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
```

## 需要再确认的问题

<a id="finding-session-001"></a>

### [MEDIUM] 会话存储使用 pickle 反序列化 + MD5 校验，签名密钥已提交进仓库

- 编号：`SESSION-001`
- 类别：`deserialization`
- CWE：`CWE-502`
- 入口身份：无请求入口
- 置信度：`medium`
- 状态：`needs_review`
- 复核员：未复核

自定义会话后端（ylinux.app.sessions）用 pickle 反序列化会话数据，完整性校验是 MD5(pickle+SECRET_KEY)，而 SECRET_KEY 硬编码在提交进仓库的 settings.py 中。该反序列化点本身不直接接收 HTTP 输入（DB 会话只有 key 在 Cookie 里），但密钥公开加上任何 DB 写入原语即可伪造会话载荷并触发 pickle RCE，属于高危潜伏组合。

**触发条件。** 触发条件：攻击者需先获得向 ylinux_session 表（或文件会话目录）写入的能力；SECRET_KEY 公开（CONFIG-002）使签名可离线伪造，随后请求携带该 session key 即触发 pickle.loads。

**影响。** 会话数据用 cPickle 反序列化，防篡改只靠 md5(数据+SECRET_KEY)，而 SECRET_KEY 明文提交在公开仓库里。一旦攻击者获得任何向会话表/会话文件写入的能力（数据库泄露、其他注入、共享主机文件写等），即可构造恶意 pickle 实现服务器端远程代码执行；密钥公开也使签名可被任意伪造。

**修复。** 换成仅存 key 的签名 Cookie 会话或 JSON 序列化；签名改用 HMAC-SHA256 与 os.urandom 生成的新密钥；轮换并外部化 SECRET_KEY，绝不入库进版本库。

**证据。**

`app/sessions/backends/base.py:86-102`

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
        # Unpickling can cause a variety of exceptions. If something happens,
        # just return an empty dictionary (an empty session).
        except:
            return {}
```

`settings.py:79-79`

```
SECRET_KEY = 'c#0cz^i$lyr6*b*xe-t@0tqc_c3dnju=+c1lk^k7(r^7lhz$g@'
```

## 复核员否决、尚未改判的问题

<a id="finding-file-001"></a>

### [HIGH] 附件上传路径穿越写文件并允许匿名访问上传的 HTML/JS

- 编号：`FILE-001`
- 类别：`file_access`
- CWE：`CWE-434`
- 入口身份：可自助注册的用户
- 置信度：`high`
- 状态：`disputed`
- 复核员：否决

ydata.views.upload_single_file 用攻击者可控的上传文件名直接拼接存储路径写盘，存在路径穿越（可写任意目录/覆盖文件）；同时下载接口按扩展名回显 Content-Type，使上传的 HTML/JS 以可执行类型被匿名访问；XML-RPC new_media 亦允许任意认证用户无限制地写任意扩展名文件到媒体目录。

**触发条件。** 登录用户 POST /ydata/uploadsf/<id>/，multipart 文件名形如 ../../topics/5.html 或 evil.html；XML-RPC 调用 metaWeblog.newMediaObject。

**数据流。** 来源：req.FILES['single_file'].name（multipart 文件名，完全由浏览器控制）→ app/ydata/views.py:78 拼进 local_name → :79-81 os.path.join(MEDIA_ROOT, ATTACHMENT_UPLOAD_TO, local_name) → :82 open(save_path,'wb+') 写盘，无 basename 清洗也无扩展名限制 → 路径穿越可覆盖 MEDIA_ROOT 下任意文件（如 ydata/topics/<id>.html 主题渲染结果）。下载端 :129-132 用 mimetypes.guess_type 按文件扩展名返回 Content-Type，上传的 .html 会以 text/html 提供给匿名用户（/ydata/attachment/<id>/download/ 无鉴权）。XML-RPC new_media 同样允许任意认证用户把任意扩展名文件写入 MEDIA_ROOT/img（lib/ylinux_xmlrpc.py:119-124，无大小与类型限制）。

**影响。** 登录用户可用 ../../ 穿越目录覆盖站点媒体目录下任意可写文件（例如重写主题渲染的 .html 文件植入脚本、覆盖其他附件）；上传的 .html/.js 等文件可被匿名用户从下载接口或 /ymedia/ 直接访问，成为站点源上的持久脚本托管；XML-RPC 新媒体的无限大小写入还可耗尽磁盘。

**修复。** 用白名单方式生成存储文件名（如 sha1 摘要或随机名，扩展名白名单）；对 f.name 先 os.path.basename 再校验；下载接口强制 application/octet-stream 或 Content-Disposition: attachment 并设置 nosniff；对 XML-RPC 上传增加大小与类型限制并复用同一存储逻辑。

**复核员指出的最弱一环。** 最弱一环是"路径穿越"声明：f.name 直接拼 local_name 看似可注入 ../，但 req.FILES 返回 Django UploadedFile，其 _set_name 自 Django 1.0 起就用 os.path.basename 清洗文件名（本仓库未内置 Django，但代码特征 hashcompat/urls.defaults/patterns 指向 1.3–1.5，均含该清洗），f.name 不可能含路径分隔符，"../../ 覆盖任意文件（如重写主题 .html）"不可达。次弱点：下载接口并非"按扩展名回显即可内联执行"——ydata/views.py:148 明确设置 Content-Disposition: attachment，浏览器会强制下载而非渲染 text/html，该回显路径基本被抵消。仍然成立的部分：上传无扩展名/类型白名单（:78-86）、附件匿名可下载、在随仓库发布的 DEBUG=True 配置下 /ymedia/ 由 django.views.static.serve 提供（urls.py:59-63）且不设 disposition，上传的 .html 可经 /ymedia/ydata/attachments/... 内联执行；XML-RPC new_media 任意认证用户可无限大小写任意扩展名文件到 MEDIA_ROOT/img（磁盘耗尽 + 同源内容托管）。

**异议或降级说明。** 下载接口无鉴权、按扩展名猜 Content-Type 属实（ydata/views.py:117-135）；XML-RPC new_media 无类型/大小限制写盘属实（ylinux_xmlrpc.py:105-127，已做 basename）；两条"Django 1.x 不清洗文件名"与"下载接口可内联执行"的核心机制均与代码/框架事实不符，需审计员修正 data_flow 与标题后重新定级。（建议严重性：medium）

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

`app/ydata/views.py:125-132`

```
    f = open(a.get_absolute_path())
    response = HttpResponse(f.read())
    f.close()

    type, encoding = mimetypes.guess_type(a.get_absolute_path())
    if type is None:
        type = 'application/octet-stream'
    response['Content-Type'] = type
```

`lib/ylinux_xmlrpc.py:119-124`

```
    if file_type == 'img':
        dated_path = datetime.now().strftime('%Y_%m_%d_') + os.path.basename(file_name)
        relative_path = os.path.join(file_type, dated_path)
        target_path = os.path.join(settings.MEDIA_ROOT, relative_path)
        target_url = '%s/%s' % (settings.MEDIA_URL, relative_path)
        open(target_path, 'w').write(file_data)
```

<a id="finding-xss-004"></a>

### [MEDIUM] ylab 上传端点把文件名未转义拼入响应导致匿名反射型 XSS

- 编号：`XSS-004`
- 类别：`xss`
- CWE：`CWE-79`
- 入口身份：匿名
- 置信度：`high`
- 状态：`disputed`
- 复核员：否决

ylab.views.upload_single_file 把用户上传的文件名未经任何转义地拼进 JS 回调字符串和 HTML 片段并返回，/lab/uploadsf 路由没有任何登录或鉴权要求，形成匿名可达的反射型 XSS。

**触发条件。** POST /lab/uploadsf 上传一个文件名含引号与 </script> 的 multipart 文件。

**数据流。** 来源：multipart 上传的文件名 attachment.name（浏览器可控，Django 1.x 不清洗 UploadedFile.name）→ app/ylab/views.py:32 拼入 innerHTML，再在 :33 拼进 window.parent.AfterSubmit(%s) 的 JS 字符串 → HttpResponse 直接以 text/html 返回。该路由 /lab/uploadsf 无任何鉴权与登录要求，匿名可达。

**影响。** 匿名攻击者即可构造恶意文件名的 multipart 请求触发反射型 XSS（无鉴权、无 CSRF），可用于向受害者投递脚本。

**修复。** 删除该实验性端点或对文件名做 JS/HTML 转义后再输出；不要用字符串拼接生成 JS。

**复核员指出的最弱一环。** 最弱一环是"可用于向受害者投递脚本"这一反射型 XSS 的可投递性。代码事实成立：ylab/views.py:31-33 把 attachment.name 未转义拼进 innerHTML 与 <script> 响应并以 text/html 返回，ylab/urls.py:7 无任何鉴权，Django 的 UploadedFile basename 清洗不会去掉引号与尖括号。但要让受害者浏览器触发，必须使受害者发出文件名受攻击者控制的 multipart POST 并把响应当作文档渲染：跨站表单无法设置 file input 的文件名（浏览器禁止），XHR/fetch 的响应不会被渲染为文档，故不存在把恶意文件名送进受害者浏览器并执行脚本的现实路径——实际上只是上传者对自己的 self-XSS。

**异议或降级说明。** 未鉴权、未转义拼接属实，但"匿名反射型 XSS 可投递给受害者"不成立，现实利用仅为 self-XSS（且 Windows 文件名不允许 <>" 等字符，社工受害者改名上传也不现实）。作为匿名反射型 XSS 评 medium 明显偏高，建议降为 low（危险代码模式/self-XSS）。另注：ydata/views.py:91-95 存在同款 AfterSubmit 回显（需登录），已用 note_gap 提示。（建议严重性：low）

**证据。**

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

## 已排除的可疑点

无。

## 未完成判断的候选

无。

## 范围

覆盖：settings.py、根 urls.py、全部 app 的 urls/views/forms/models（account、admin、bbs、blog、home、me、sessions、wiki、ydata、ylab、syndication）、lib/django_xmlrpc、lib/ylinux_xmlrpc.py、lib/markdown 渲染器关键部分、全部模板中的 |safe 危险点、scripts 部署文件。未深入：doc 目录、各 app 的 tests.py、前端 JS、生产部署配置（ylinux.ysettings 未提交，SESSION_ENGINE 等运行时值无法在本仓库确认）。

## 局限

静态审计无法验证运行时行为：1) SESSION_ENGINE 未在本仓库定义，实际会话后端（DB/文件）取决于未提交的部署配置，SESSION-001 的可达性因此标为 needs_review；2) 生产环境是否沿用 DEBUG=True、/ymedia/ 静态路由和 sqlite 引擎无法确认；3) 邮件发送依赖部署环境 SMTP，注册是否实际开放取决于站点策略（代码层面注册流程匿名可达）；4) 未对 markdown 库的 safe_mode 绕过细节做版本级验证，但已确认默认 safe_mode=False 时原始 HTML 直接通过。

## 复核意见

（复核员没有留下说明。）

## 复核缺口

无。

## 运行警告

- run interrupted: Error code: 429 - {'error': {'message': 'Your credit balance is running low for account <org-<redacted>>, please recharge immediately to avoid service disruption', 'type': 'exceeded_current_quota_error'}}
