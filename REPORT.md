# ylinux_old 安全审计分析报告

这份报告回答三个问题：这个网站有哪些安全问题，Agent 找到了哪些、漏了哪些，这些结论有多可信。

- 审计对象：[gwind/ylinux_old](https://github.com/gwind/ylinux_old)，commit `8a7316deec88287d020eca21c38dad921b623ffc`
- 它是什么：2010–2011 年用 Django 1.2 / Python 2 写的中文 Linux 社区，有论坛、Wiki、附件上传，还有一个 XML-RPC 接口（一种老式的远程调用协议，让桌面客户端不开浏览器也能发帖、删帖）
- 依据：Agent 的 7 次真实运行，结果合并后我逐条回到源码确认过。每次运行的原始报告在 `results/<运行目录>/report.md`

## 一句话结论

如果按仓库里的代码和配置上线，这个网站有 4 类几乎没有门槛的严重问题：

1. **注册个账号就能在帖子里埋脚本**，所有看帖的人都会中招（存储型 XSS）。
2. **任何一个普通账号都能一键删光全站主题**（XML-RPC 接口不检查权限）。
3. **知道对方邮箱，就能猜出重置口令的链接，接管账号**（随机数太短）。
4. **全站没有 CSRF 防护**，管理员点开一个恶意网页，就可能在不知情的情况下删掉内容。

这 4 类 Agent 7 次都找到了。它一直没找到的，是重置口令流程里两个要把前后代码连起来想才能发现的逻辑漏洞，以及一些低危的小问题。

## 怎么读这份报告

报告里会出现几种漏洞类型，第一次出现时我会解释。严重性从高到低是 critical、high、medium、low、info。每条问题都给出“文件:行号”，可以直接打开源码对照。问题编号（如 GT-01）对应标准答案文件 `eval/ground_truth.json`，“GT”是 ground truth（真值）的缩写。

## 一、严重问题逐条讲解

### 1. 存储型 XSS：帖子里的脚本会在别人浏览器里运行（high）

**什么是 XSS。** XSS（Cross-Site Scripting，跨站脚本，[CWE-79](https://cwe.mitre.org/data/definitions/79.html)）是指攻击者把一段 JavaScript 塞进网页，别人打开页面时这段脚本就在他的浏览器里执行，可以偷走登录状态、冒充他发帖。“存储型”是说脚本被存进了数据库，每个看帖的人都会触发，危害最大。它属于 [OWASP Top 10](https://owasp.org/Top10/) 里的“注入”类。

**问题在哪。** 网站的帖子支持 Markdown 格式（一种用简单符号写排版的格式）。Markdown 库有个 `safe_mode` 选项，打开后会把用户写的 HTML 标签转义掉。代码里有两条分支，一条开了、一条没开，而所有发帖的地方都把格式写死成走没开的那条：

```python
# app/ydata/forms.py:46  —— 发帖时 markup 固定为 'none'
post = Post(topic=self.topic, user=self.user, user_ip=self.ip, markup='none', body=self.cleaned_data['body'])

# app/ydata/models.py:255-260  —— 'none' 这条分支没有 safe_mode
elif self.markup == 'markdown':
    self.body_html = unicode(Markdown(self.body, safe_mode='escape'))
elif self.markup == 'none':
    self.body_html = Markdown(extensions=['fenced_code']).convert(ylinux_text_filter(self.body))
```

生成的 HTML 最后在模板里用 `|safe` 输出（`templates/wiki/topic.html:54`、`:59`）。`|safe` 是 Django 模板的写法，意思是“这段内容我信得过，不要转义”。主题正文（`models.py:196-198`）也是同样的情况。

**谁能利用。** 网站开放注册，任何人注册后发一个带 `<script>` 的帖子即可。会话 cookie 又没设 HttpOnly（一个让 JavaScript 读不到 cookie 的开关），所以脚本能直接拿走访客的登录状态。

**怎么修。** 渲染时打开 `safe_mode`，或者用白名单清洗 HTML；模板里去掉 `|safe`。

### 2. XML-RPC 接口：普通账号能删光全站（high）

**什么是越权。** “认证”是确认你是谁（输对了用户名和密码），“鉴权”是确认你能做什么（是不是管理员、这条内容是不是你的）。只做认证不做鉴权，就是越权（Broken Access Control，[CWE-285](https://cwe.mitre.org/data/definitions/285.html)，OWASP Top 10 排第一）。

**问题在哪。**

```python
# lib/ylinux_xmlrpc.py:39-45
def has_auth(user, passwd):
    user = authenticate(username=user, password=passwd)
    if user is not None:
        return True
```

删主题、删全部主题、改主题这三个接口都只调用了 `has_auth`，即只要用户名密码对就放行。其中 `delete_all_topic` 只有一句 `Topic.objects.all().delete()`（`:66`），也就是删除所有主题。另外，登录校验（`app/account/backends.py:19-25`）只核对密码，不看账号是否已被禁用（`is_active`），被管理员封掉的账号照样能调。

**谁能利用。** 任何能注册的人。

**怎么修。** 每个删改接口检查操作人是不是内容的主人或管理员；`delete_all_topic` 直接删掉；登录时检查 `is_active`。

### 3. 激活和重置口令用的 key 太容易猜（high）

**问题在哪。** 注册激活和找回口令都靠邮件里一串 key。这串 key 本该是谁都猜不到的随机数，但它是这样生成的：

```python
# app/account/models.py:364-367
salt = sha_constructor(str(random.random())).hexdigest()[:5]
activation_key = sha_constructor(salt+email).hexdigest()
```

看起来是一长串 SHA-1 哈希，但真正随机的只有 `salt` 那 5 位十六进制数，也就是 16^5 ≈ 105 万种可能；邮箱是攻击者已知的。105 万次尝试对程序来说很快就能试完。重新生成 key 的 `reset_activation_key`（`:427-430`）用的是同样写法。这类问题叫“随机数熵不足”（[CWE-331](https://cwe.mitre.org/data/definitions/331.html)），“熵”可以理解为随机程度，20 bit 就是 2 的 20 次方 ≈ 105 万。

**谁能利用。** 知道受害者邮箱的任何人。重置接口没有次数限制，key 也不会过期，可以在线一个个试。

**怎么修。** 用 `os.urandom` 生成至少 128 bit 的随机 key，设过期时间，用过一次就作废。

### 4. 能编辑任何人的回帖（high）

**问题在哪。**

```python
# app/wiki/views.py:445-460
@login_required
def editPostAJAX(request, postID):
    post = get_object_or_404(Post, pk = postID)
    ...
    post.body = post_body
    post.save()
```

`@login_required` 只保证“登录了”，代码按网址里的编号取出帖子就直接改，没有判断这帖子是不是当前用户发的。这种“改一下网址里的编号就能动别人的数据”叫 IDOR（Insecure Direct Object Reference，不安全的直接对象引用，[CWE-639](https://cwe.mitre.org/data/definitions/639.html)）。

**怎么修。** 保存前检查 `post.user == request.user`，不是本人就拒绝。

### 5. 全站没有 CSRF 防护（high）

**什么是 CSRF。** CSRF（Cross-Site Request Forgery，跨站请求伪造，[CWE-352](https://cwe.mitre.org/data/definitions/352.html)）是指：你已经登录了 A 网站，又打开了攻击者的 B 网页，B 网页偷偷让你的浏览器向 A 发请求。浏览器会自动带上你在 A 的登录状态，A 就以为是你本人在操作。Django 自带的 `CsrfViewMiddleware` 就是防这个的。

**问题在哪。** `settings.py:98-104` 的中间件列表里没有 `CsrfViewMiddleware`。更糟的是后台删除操作用 GET 请求就能触发，删完还按 Referer 跳回去（`app/admin/views.py:130-134`）。攻击者只要在网页里放一个 `<img src="https://网站/admin/删除地址">`，管理员一打开，内容就被删了。

**怎么修。** 启用 `CsrfViewMiddleware`，所有会改数据的操作只接受 POST。

## 二、全部问题清单，以及 Agent 找到了几次

标准答案里一共 32 个真问题。下表的“命中”是 7 次运行里有几次找到了这一条。同一个 Agent 每次跑的结果会有出入，因为模型每次的回答带有随机性，所以要看多次。

**稳定找到：7 次里 6 次以上（15 条）**

| 编号 | 严重性 | 问题 | 位置 | 命中 |
| --- | --- | --- | --- | --- |
| GT-01 | high | 主题正文 Markdown 没开 safe_mode，经 `\|safe` 输出（XSS） | `app/ydata/models.py:196` | 7 |
| GT-02 | high | 回帖正文同上 | `app/ydata/models.py:258` | 7 |
| GT-06 | high | editPostAJAX 不检查帖子是谁的 | `app/wiki/views.py:447` | 7 |
| GT-07 | high | XML-RPC 任何登录用户都能删改任意主题 | `lib/ylinux_xmlrpc.py:39` | 7 |
| GT-10 | high | 激活 / 重置 key 只有 20 bit 随机量 | `app/account/models.py:364` | 7 |
| GT-13 | high | 全站没有 CSRF 中间件 | `settings.py:98` | 7 |
| GT-16 | medium | DEBUG=True（出错时把代码细节显示给访客），静态目录允许列出文件 | `settings.py:18` | 7 |
| GT-17 | medium | 密钥 SECRET_KEY 和数据库口令直接写在代码里 | `settings.py:79` | 7 |
| GT-18 | medium | 口令只做一次 SHA-1 加 20 bit 盐，太容易破解 | `app/account/models.py:231` | 7 |
| GT-31 | medium | XML-RPC 登录不检查账号是否被禁用 | `app/account/backends.py:19` | 7 |
| GT-04 | medium | 注册 / 重置页把网址里的 key 原样拼进 HTML（反射型 XSS：脚本藏在链接里，点了才中招） | `app/account/views.py:102` | 6 |
| GT-20 | medium | 登录后跳转到 `next` 参数指定的任何网址（开放跳转，可用来钓鱼） | `app/account/views.py:38` | 6 |
| GT-15 | low | `/lab/update_post_profile` 不登录就能批量改写所有帖子 | `app/ylab/views.py:37` | 7 |
| GT-19 | low | 兼容无盐 MD5 旧口令，比较方式可被计时攻击 | `app/account/models.py:243` | 7 |
| GT-21 | low | 注销后跳转到 `next` 参数 | `app/account/views.py:58` | 7 |

**时有时无（11 条）**

| 编号 | 严重性 | 问题 | 位置 | 命中 |
| --- | --- | --- | --- | --- |
| GT-14 | medium | 删除、重启等操作用 GET 就能触发 | `app/admin/views.py:133` | 4 |
| GT-23 | medium | 上传不限文件类型，存到能直接访问的目录 | `app/ydata/views.py:78` | 4 |
| GT-05 | low | 上传结果页把文件名拼进 `<script>` | `app/ydata/views.py:91` | 4 |
| GT-22 | low | 后台登录和删除后跳转到 Referer | `app/admin/views.py:62` | 4 |
| GT-32 | low | 上传附件时不检查主题是不是自己的 | `app/ydata/views.py:46` | 3 |
| GT-08 | medium | 受限版块只在发帖时检查权限，看帖时不检查 | `app/ydata/models.py:91` | 2 |
| GT-03 | medium | 附件名、主题名不转义就拼进 HTML | `app/ydata/models.py:408` | 2 |
| GT-24 | low | 匿名联系表单能往任意邮箱发信 | `app/home/views.py:43` | 1 |
| GT-26 | low | 没有防暴力破解，XML-RPC 还能一次请求试多个口令 | `lib/django_xmlrpc/views.py:155` | 1 |
| GT-28 | low | 会话 cookie 没设 HttpOnly / Secure | `app/sessions/middleware.py:37` | 1 |
| GT-29 | low | 后台编辑用户的表单暴露口令哈希，还能改成超级用户 | `app/admin/forms.py:103` | 1 |

**一次都没找到（6 条）**

| 编号 | 严重性 | 问题 | 位置 |
| --- | --- | --- | --- |
| GT-11 | medium | 重置接口接受字面量 key `ALREADY_ACTIVATED` | `app/account/models.py:383` |
| GT-12 | medium | 重置 key 不过期，用过也不作废 | `app/account/views.py:217` |
| GT-09 | low | 编辑主题时能把它挪进自己无权访问的版块 | `app/ydata/forms.py:109` |
| GT-25 | low | 注册、重置、登录的提示能用来判断某用户名是否存在 | `app/account/views.py:79` |
| GT-27 | low | XML-RPC 把请求内容（含口令）打印到标准输出 | `lib/django_xmlrpc/views.py:82` |
| GT-30 | low | 信任客户端伪造的 X-Forwarded-For 头，并向所有人展示发帖 IP | `app/ydata/util.py:169` |

规律很明显：high 级全部稳定找到，漏掉的大多是 low 级，以及下面要讲的两个逻辑漏洞。

## 三、Agent 漏掉的两个逻辑漏洞

GT-11 和 GT-12 都出在“找回口令”流程里。单看哪一段代码都没毛病，要把“注册激活”和“重置口令”两段连起来才看得出来。

**GT-11：用一个固定的单词当 key 也能重置口令。** 用户激活账号后，代码把他的 key 改成一个固定字符串，表示“已激活”（`app/account/models.py:383`，常量定义在 `:392`）：

```python
profile.activation_key = self.model.ACTIVATED   # 值是 u"ALREADY_ACTIVATED"
```

而重置口令的接口直接拿网址里的 key 去数据库里找人（`app/account/views.py:205`）：

```python
register = Register.objects.get(activation_key=key)
```

于是访问 `/account/password/reset/ALREADY_ACTIVATED/`，就能找到“已激活、而且最近没申请过重置”的账号。如果这样的账号只有一个，不用收邮件就能直接改掉他的口令；如果有多个，程序报错，在 DEBUG=True 下错误页面还会把内部代码细节显示出来。

**GT-12：重置链接永远有效。** 口令重置成功后（`views.py:217-221`），key 没有作废，以后还能再用。发邮件时准备了 `'expiration_days': 3`（3 天过期），但用到它的模板被注释掉了，这个期限从来没生效。

**为什么 Agent 没找到。** 它每次都读了这几个文件，也每次都报了“key 太短”（GT-10），但没有接着追问“key 用完以后变成了什么”。门禁只能检查“读过没有”“写没写数据流”，管不住“读了但没往下想”。这是这套方法目前最主要的短板。

## 四、Agent 犯过的错（误报）

7 次运行里，没有一条报告落在“既不是真问题、也不是已知陷阱”的地方。反复出现的误判有两处，它们都被事先列在标准答案的“误报陷阱”里（FP 是 false positive，误报）。

**FP-05：把附件上传判成“路径穿越”。** 路径穿越是指在文件名里写 `../../` 跳出上传目录，把文件写到服务器任意位置（[CWE-22](https://cwe.mitre.org/data/definitions/22.html)）。Agent 看到了这行：

```python
# app/ydata/views.py:78
local_name = str(id) + '-' + str(req.user.id) + '-' + f.name
```

以为 `f.name` 可以带 `../`。实际上 Django 在接收上传文件时已经只保留了文件名本身（相当于 `os.path.basename`），`../` 进不来。新版 6 次运行里审计员每次都报了这条，5 次定成 high。

这条最能说明复核员的价值：DeepSeek 自己当复核员时 3 次都同意了；换成 Kimi 当复核员，3 次都否决了，理由都是 Django 已经处理过文件名。被否决后，审计员一次降成“需要再确认 / low”，一次直接撤回，还有一次因为复核中途中断，停在“已否决”。

**FP-03：把没用上的 pickle 会话后端判成反序列化漏洞。** pickle 是 Python 的一种数据存储格式，加载来路不明的 pickle 数据可以执行任意代码（[CWE-502](https://cwe.mitre.org/data/definitions/502.html)）。项目里确实自带了一套用 pickle 的会话代码，但 `settings.py` 没设 `SESSION_ENGINE`，实际用的是 Django 默认的数据库会话，那套代码根本没被加载；而且会话内容存在服务器上，攻击者碰不到。kimi2、kimi3 两次把它报成 medium，恰好都在复核中断后没来得及复核。

## 五、这些结论有多可信

| 运行组 | 每次报出 | 精确率下限 | 召回率 | high 召回 |
| --- | --- | --- | --- | --- |
| r1–r3（DeepSeek 复核） | 14.3 ± 2.1 | 0.952 ± 0.043 | 0.573 ± 0.048 | 1.0 |
| kimi1–3（Kimi 复核） | 15.7 ± 3.1 | 0.934 ± 0.012 | 0.552 ± 0.065 | 1.0 |

“± ”后面是标准差，表示多次运行之间的波动大小。精确率只给“下限”，因为没对上标准答案的报告也可能是标准答案漏收的真问题。

- **可以放心的部分：** 报告里的每段代码引用都回到源文件按行号核对过（全部通过）；6 个 high 级问题每次都找到；报出来的平均 93% 以上是真问题。
- **要打折扣的部分：** 一次只能找到 55%–57% 的问题，单跑一次的结果不能当作“只有这些漏洞”。
- **标准答案本身的局限：** 它是我借助 Claude（和被测的 DeepSeek 不是同一个模型）标注、另开会话交叉核对、我再抽查得出的，没有经过专业安全工程师复核。
- **偏乐观的地方：** Agent 的规则是看着 ylinux_old 的错误调出来的。换到另一个项目 django.nV 上（代码和规则都不改），召回率是 0.83–0.96，但那个项目是教学用的，源码里有注释标出了漏洞位置，难度偏低。

打分规则和标准答案怎么来的，详见 [DESIGN.md](DESIGN.md#二怎么确认结果是准的)；每条报告的逐一判定见 [results/EVALUATION.md](results/EVALUATION.md)。

## 六、修复建议（按优先级）

1. 帖子和主题正文渲染时转义 HTML（Markdown 打开 `safe_mode` 或用白名单清洗），模板里去掉 `|safe`。
2. XML-RPC 的删改接口检查内容归属和权限，`delete_all_topic` 直接删掉；登录时检查账号是否被禁用。
3. 激活和重置 key 改用 `os.urandom` 生成 128 bit 以上，设过期时间，用一次就作废；“已激活”状态单独存一个字段，不要和 key 混用。
4. 启用 `CsrfViewMiddleware`，会改数据的操作只接受 POST。
5. 把 `settings.py` 里的 SECRET_KEY、数据库口令移出代码并更换；生产环境关掉 DEBUG 和目录列表。
6. 口令改用 PBKDF2 或 bcrypt 这类专门的口令哈希算法。长远看，Django 1.2 和 Python 2 都早已停止维护，应整体升级。

补充说明：线上实际运行用的启动脚本 `scripts/ylinux.fcgi:21` 加载的是 `ylinux.ysettings`，这个配置文件不在仓库里。所以第 5 条这类配置问题，结论只对仓库里的 `settings.py` 成立，线上配置可能不一样。
