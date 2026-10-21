# ylinux_old 审计分析报告

审计对象是 [gwind/ylinux_old](https://github.com/gwind/ylinux_old)，commit `8a7316deec88287d020eca21c38dad921b623ffc`，一个 2010–2011 年写的 Django 1.2 / Python 2 社区站点（论坛 + Wiki + 附件 + XML-RPC 发帖接口）。

我用当前版本的 Agent 跑了 5 次：3 次同配置重复（r1–r3）、1 次复核员换成 Kimi、1 次是加 `list_endpoints` 之前的版本。下面把 5 次的发现合并，每条都回到源码看过，再对照 `eval/ground_truth.json` 统计 Agent 找到了几次。单次运行的完整报告在 `results/<运行>/report.md`。

## 结论

按仓库里的配置上线的话，这个站点有几处几乎没有门槛的问题：

- 注册一个账号，就能在帖子里写入会被全站访客执行的脚本（存储型 XSS）。
- 拿任意账号的用户名密码调 XML-RPC 的 `delete_all_topic`，可以删掉全部主题。
- 重置口令的 key 只有 20 bit 随机量，知道对方邮箱就能枚举出重置链接，接管账号。
- 全站没有 CSRF 防护，后台的删除操作还接受 GET。

这 4 类问题 5 次运行都找到了。Agent 一直没找到的，是重置流程里要把两段代码连起来看才能发现的两个逻辑漏洞，还有一些 low 级的信息泄露类问题。

## 高危问题

### 存储型 XSS：帖子正文不过滤直接输出

所有发帖路径都把 `markup` 写死成 `'none'`：

```python
# app/ydata/forms.py:46
post = Post(topic=self.topic, user=self.user, user_ip=self.ip, markup='none', body=self.cleaned_data['body'])
```

`markup='none'` 这条分支调用 Markdown 时没有传 `safe_mode`，原始 HTML 会原样保留。带 `safe_mode='escape'` 的那条分支走不到：

```python
# app/ydata/models.py:255-260
elif self.markup == 'markdown':
    self.body_html = unicode(Markdown(self.body, safe_mode='escape'))
elif self.markup == 'none':
    self.body_html = Markdown(extensions=['fenced_code']).convert(ylinux_text_filter(self.body))
```

主题正文（`models.py:196-198`）也一样，模板最后用 `|safe` 输出（`templates/wiki/topic.html:54`、`:59`）。注册是开放的，所以任何访客注册后都能写入。会话 cookie 没有设 HttpOnly，XSS 可以直接拿到会话。

### XML-RPC 只认证、不鉴权

```python
# lib/ylinux_xmlrpc.py:39-45
def has_auth(user, passwd):
    user = authenticate(username=user, password=passwd)
    if user is not None:
        return True
```

`delete_topic`、`delete_all_topic`、`edit_topic` 都只调了 `has_auth`，没有检查权限，也没有检查对象归属。`delete_all_topic` 里就是一句 `Topic.objects.all().delete()`（`:66`）。另外，认证后端（`app/account/backends.py:19-25`）只校验口令，不看 `is_active`，被管理员禁用的账号照样能调这些接口。

### 激活和重置 key 只有 20 bit

```python
# app/account/models.py:364-367
salt = sha_constructor(str(random.random())).hexdigest()[:5]
activation_key = sha_constructor(salt+email).hexdigest()
```

key 是 `sha1(5 位十六进制 + 邮箱)`。邮箱是已知的，所以总共只有 16^5 ≈ 105 万种可能，重新生成 key 的 `reset_activation_key`（`:427-430`）也是同样的写法。重置接口没有频率限制，key 也不会过期（见后面的漏报部分），在线枚举是可行的。

### 编辑任意人的帖子

```python
# app/wiki/views.py:445-460
@login_required
def editPostAJAX(request, postID):
    post = get_object_or_404(Post, pk = postID)
    ...
    post.body = post_body
    post.save()
```

只要登录就能改任何人的回帖，没有判断 `post.user == request.user`。

### 没有 CSRF 防护

`settings.py:98-104` 的中间件列表里没有 `CsrfViewMiddleware`。后台删除操作用的是 GET，删完按 Referer 跳回去（`app/admin/views.py:130-134`），诱导已登录的管理员打开一个嵌了 `<img>` 的页面就能触发。

## 全部问题和 Agent 的命中次数

“命中”指 5 次运行里有几次找到了。编号对应 `eval/ground_truth.json`。

**5 次里找到 4 次以上（16 条）**

| 编号 | 严重性 | 问题 | 位置 | 命中 |
| --- | --- | --- | --- | --- |
| GT-01 | high | 主题正文 Markdown 未开 safe_mode，经 `\|safe` 输出 | `app/ydata/models.py:196` | 5 |
| GT-02 | high | 回帖正文同上 | `app/ydata/models.py:258` | 5 |
| GT-06 | high | editPostAJAX 不校验帖子归属 | `app/wiki/views.py:447` | 5 |
| GT-07 | high | XML-RPC 任意认证用户可删改任意主题 | `lib/ylinux_xmlrpc.py:39` | 5 |
| GT-10 | high | 激活/重置 key 只有 20 bit | `app/account/models.py:364` | 5 |
| GT-13 | high | 全站没有 CSRF 中间件 | `settings.py:98` | 5 |
| GT-04 | medium | 注册/重置页把 URL 里的 key 原样拼进 HTML（反射型 XSS） | `app/account/views.py:102` | 5 |
| GT-16 | medium | DEBUG=True，静态目录开了目录列表 | `settings.py:18` | 5 |
| GT-17 | medium | SECRET_KEY 和数据库口令写在仓库里 | `settings.py:79` | 5 |
| GT-18 | medium | 口令哈希是单轮 SHA-1 + 20 bit 盐 | `app/account/models.py:231` | 5 |
| GT-31 | medium | XML-RPC 认证不检查 is_active | `app/account/backends.py:19` | 5 |
| GT-15 | low | `/lab/update_post_profile` 匿名可批量改写全部帖子 | `app/ylab/views.py:37` | 5 |
| GT-19 | low | 兼容无盐 MD5 旧口令，比较不是常量时间 | `app/account/models.py:243` | 5 |
| GT-21 | low | 注销后跳转到 next 参数 | `app/account/views.py:58` | 5 |
| GT-14 | medium | 删除、重启等状态变更接受 GET | `app/admin/views.py:133` | 4 |
| GT-20 | medium | 登录后跳转到 next 参数，没有同源校验 | `app/account/views.py:38` | 4 |

**时有时无（10 条）**

| 编号 | 严重性 | 问题 | 位置 | 命中 |
| --- | --- | --- | --- | --- |
| GT-23 | medium | 上传不限类型，存到可直接访问的媒体目录 | `app/ydata/views.py:78` | 3 |
| GT-05 | low | 上传响应把文件名拼进 `<script>` | `app/ydata/views.py:91` | 3 |
| GT-22 | low | 后台登录和 del_* 跳转到 Referer | `app/admin/views.py:62` | 3 |
| GT-32 | low | 上传附件不校验主题归属 | `app/ydata/views.py:46` | 3 |
| GT-08 | medium | 受限版块只在写入时检查 has_access，读取时不检查 | `app/ydata/models.py:91` | 2 |
| GT-03 | medium | ylinux_text_filter 把附件名、主题名不转义拼进 HTML | `app/ydata/models.py:408` | 1 |
| GT-24 | low | 匿名联系表单可以往任意地址发信 | `app/home/views.py:43` | 1 |
| GT-26 | low | 没有防暴力破解，XML-RPC multicall 还能放大尝试次数 | `lib/django_xmlrpc/views.py:155` | 1 |
| GT-28 | low | 会话 cookie 没设 HttpOnly/Secure | `app/sessions/middleware.py:37` | 1 |
| GT-29 | low | 后台编辑用户表单暴露口令哈希，可改成超级用户 | `app/admin/forms.py:103` | 1 |

**一次都没找到（6 条）**

| 编号 | 严重性 | 问题 | 位置 |
| --- | --- | --- | --- |
| GT-11 | medium | 重置接口接受字面量 key `ALREADY_ACTIVATED` | `app/account/models.py:383` |
| GT-12 | medium | 重置 key 不过期，用过也不失效 | `app/account/views.py:217` |
| GT-09 | low | 编辑主题时能把主题移进自己无权访问的版块 | `app/ydata/forms.py:109` |
| GT-25 | low | 注册、重置、登录可以枚举用户 | `app/account/views.py:79` |
| GT-27 | low | XML-RPC 请求体（含口令）打印到 stdout | `lib/django_xmlrpc/views.py:82` |
| GT-30 | low | 信任 X-Forwarded-For，并向所有人展示发帖 IP | `app/ydata/util.py:169` |

## 漏掉的两个逻辑漏洞

GT-11 和 GT-12 都在重置口令流程里，要把注册激活和重置这两段代码对起来看才能发现。

注册激活后，`activation_key` 被改成一个固定字符串（`app/account/models.py:383`，常量定义在 `:392`）：

```python
profile.activation_key = self.model.ACTIVATED   # u"ALREADY_ACTIVATED"
```

重置接口直接拿 URL 里的 key 去查这张表（`app/account/views.py:205`）：

```python
register = Register.objects.get(activation_key=key)
```

所以访问 `/account/password/reset/ALREADY_ACTIVATED/`，查到的就是已激活、而且没申请过重置的账号。如果这样的账号只有一个，可以不经过邮件直接改掉它的口令；如果有多个，`get()` 抛 `MultipleObjectsReturned`，在 DEBUG=True 下会把调用栈直接显示出来。

GT-12：口令重置成功后（`views.py:217-221`）没有作废 key。`Register` 表里有 `updated` 字段，但没有任何地方拿它判断过期。`send_activation_email` 里准备了 `'expiration_days': 3`，但用到它的邮件模板被注释掉了，这个期限从来没生效过。

Agent 每次都读到了这几个文件，也找到了“key 熵太低”（GT-10），但没有接着去追“key 用完以后变成了什么”。门禁只要求“读过”和“写明数据流”，挡不住这种没往下追的情况。

## 误报

5 次运行里没有一条落在真值之外的发现，唯一反复出现的误判是附件上传的“路径穿越”（陷阱 FP-05）：

```python
# app/ydata/views.py:78
local_name = str(id) + '-' + str(req.user.id) + '-' + f.name
```

Django 的 `UploadedFile` 在设置 `name` 时已经做过 `os.path.basename`，`f.name` 里不会有 `../`。r1、r2、r3 都把它判成 high 级的“任意文件写入”，同一个模型做复核员时三次都同意了。换成 Kimi 复核后，它读到 basename 处理就否决了这条，审计员把它降为 needs_review / low。

这条在 r1 里同时覆盖了真问题 GT-32（附件可挂到任意主题），所以那一次算命中，只是严重性偏高。

## 这些结果有多可信

| 运行 | 上报 | 精确率下限 | 召回率 | high 召回 |
| --- | --- | --- | --- | --- |
| r1–r3 均值 ± 标准差 | 14.3 ± 2.1 | 0.952 ± 0.043 | 0.573 ± 0.048 | 1.0 |
| 换 Kimi 复核 | 19 | 0.947 | 0.625 | 1.0 |

- 6 条 high 每次都能找到，这部分结论比较稳。
- 召回率在 0.53–0.69 之间波动，单跑一次不能说明问题，至少要看几次的均值。
- 真值是我用 Claude 标注、再开独立会话交叉核对出来的，没有经过安全工程师复核。标注模型和被测模型（DeepSeek）不是同一个，但仍有可能共享同样的盲点。
- 提示词和门禁是在 ylinux_old 上调出来的，这里的分数偏乐观。泛化测试用的是 django.nV，召回率 0.958，但那个项目的源码里有提示漏洞位置的注释，难度偏低。

打分方法和真值的来历写在 [DESIGN.md](DESIGN.md#怎么确认结果准确)。逐条判定见 [results/EVALUATION.md](results/EVALUATION.md)。

## 修复建议（按优先级）

1. 帖子和主题正文渲染时转义 HTML：Markdown 打开 `safe_mode`，或者改用白名单清洗，模板里去掉 `|safe`。
2. XML-RPC 删改接口校验对象归属和权限，`delete_all_topic` 直接删掉；认证时检查 `is_active`。
3. 激活和重置 key 改用 `os.urandom` 生成 128 bit 以上，设过期时间，用一次就作废；“已激活”状态不要和 key 存在同一个字段里。
4. 启用 `CsrfViewMiddleware`，所有状态变更改成只接受 POST。
5. 把 `settings.py` 里的 SECRET_KEY、数据库口令移出仓库，并且轮换；生产环境关掉 DEBUG 和目录列表。
6. 口令哈希换成 PBKDF2 或 bcrypt。长期来看，Django 1.2 和 Python 2 都早已停止维护，应该整体升级。

说明：生产环境用的 `scripts/ylinux.fcgi:21` 加载的是 `ylinux.ysettings`，这个文件不在仓库里，所以第 5 条里的配置类结论只对仓库里的 `settings.py` 成立。
