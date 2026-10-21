# 评测结果

用 `python -m audit_agent evaluate` 生成，真值文件是 `eval/django_nv_truth.json`（https://github.com/nVisium/django.nV）。

| 运行 | 上报 | 命中真值 | 踩中误报陷阱 | 未匹配 | 精确率下限 | 召回率 | 高危及以上召回 | 按严重性加权召回 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `nv-20261021` | 22 | 22 | 0 | 0 | 1.0 | 0.958 | 0.923 | 0.956 |
| `nv-20261021-kimi` | 19 | 17 | 2 | 0 | 0.895 | 0.833 | 0.923 | 0.856 |

“未匹配”可能是误报，也可能是真值里没收录的真问题，要人工看，所以精确率只给下限。“附带陷阱”指发现本身命中了真值，但有一部分证据或影响描述落在已知的误判上，也就是问题找对了、影响说过头了。

## `nv-20261021`

| 发现 | 状态 | 严重性 | 判定 | 对应真值 | 严重性偏差 |
| --- | --- | --- | --- | --- | --- |
| `CMDI-001` 上传文件名进入 os.system 拼接，导致未认证命令注入（RCE） | confirmed | critical | true_positive | NV-01, NV-02, NV-07, NV-08 | ok |
| `SQLI-001` upload 视图用 % 格式化拼接 INSERT 语句，未认证 SQL 注入 | confirmed | critical | true_positive | NV-01, NV-07, NV-08 | ok |
| `FILE-001` download 视图无鉴权且路径取自数据库，可任意文件读取（路径穿越） | confirmed | high | true_positive | NV-01, NV-08, NV-14, NV-22 | ok |
| `SESSION-001` 签名 Cookie 会话 + PickleSerializer + 仓库内硬编码 SECRET_KEY 可伪造会话并反序列化 RCE | confirmed | critical | true_positive | NV-03 | ok |
| `AUTH-001` 注册表单批量赋值：POST 附加 is_superuser/is_staff 即可匿名创建超级用户 | confirmed | critical | true_positive | NV-04 | ok |
| `AUTH-002` profile_by_id 无鉴权 IDOR + csrf_exempt：匿名改任意用户密码实现账户接管 | confirmed | critical | true_positive | NV-02, NV-05, NV-10, NV-24 | ok |
| `ACCESS-001` manage_groups POST 分支缺少权限检查：普通用户可提升任意用户到管理员组 | confirmed | medium | true_positive | NV-06 | ok |
| `ACCESS-002` 项目/任务/笔记的编辑与删除端点无鉴权、无归属校验（匿名 IDOR 写操作） | confirmed | high | true_positive | NV-11, NV-12 | ok |
| `XSS-003` task_details 页面 task.title/task.text 经 |safe 渲染，存储型 XSS | confirmed | high | true_positive | NV-09（附带陷阱 NVFP-11） | ok |
| `XSS-004` 用户名经 |safe 渲染到全站导航栏，存储型 XSS | confirmed | medium | true_positive | NV-10 | ok |
| `XSS-002` tm_settings 页面 {{v|safe}} 渲染 request.META：请求头反射 XSS 与环境信息泄露 | confirmed | medium | true_positive | NV-17 | ok |
| `XSS-001` search 页面 {{q|safe}} 反射型 XSS | confirmed | medium | true_positive | NV-15 | ok |
| `CSRF-001` profile_by_id 改密端点豁免 CSRF，可被跨站请求改密 | confirmed | medium | true_positive | NV-02, NV-05, NV-24 | ok |
| `CRYPTO-001` 口令使用 MD5 哈希存储，内置超管口令可被快速离线破解 | confirmed | medium | true_positive | NV-03, NV-19 | ok |
| `CONFIG-002` SECRET_KEY 硬编码在仓库中（配置类，独立于会话反序列化记录） | confirmed | high | true_positive | NV-03 | ok |
| `CONFIG-001` DEBUG/TEMPLATE_DEBUG 开启并提交进仓库，错误页泄露敏感信息 | confirmed | medium | true_positive | NV-03, NV-18 | ok |
| `CONFIG-003` 会话 Cookie 未设 HttpOnly，XSS 可直接窃取会话 | confirmed | low | true_positive | NV-03 | under |
| `REDIRECT-001` logout 端点开放重定向 | confirmed | medium | true_positive | NV-16 | ok |
| `FILE-002` 上传文件名无校验且可路径穿越写入静态目录 | confirmed | medium | true_positive | NV-01, NV-08, NV-22 | ok |
| `COMP-001` 使用已停止维护的 Django 1.8.3，存在已知未修复漏洞 | confirmed | info | true_positive | NV-21 | under |
| `RESET-001` 密码重置令牌只有 6 位数字且无速率限制，可暴力枚举接管账户 | confirmed | high | true_positive | NV-20（附带陷阱 NVFP-02） | ok |
| `ACCESS-003` task_details/profile_view 读侧 IDOR：匿名读取任意任务与用户资料 | confirmed | medium | true_positive | NV-23 | ok |

漏报：

- NV-13 [high] 备注创建/编辑/删除 IDOR

## `nv-20261021-kimi`

| 发现 | 状态 | 严重性 | 判定 | 对应真值 | 严重性偏差 |
| --- | --- | --- | --- | --- | --- |
| `RCE-001` 上传文件名拼接进 os.system 导致 shell 命令注入（未授权 RCE） | confirmed | critical | true_positive | NV-01, NV-02, NV-07, NV-08 | ok |
| `SQLI-001` upload 视图用字符串格式化拼接原始 SQL，存在 SQL 注入 | confirmed | high | true_positive | NV-01, NV-07, NV-08 | ok |
| `DESER-001` 硬编码 SECRET_KEY + signed_cookies + PickleSerializer 可伪造会话并反序列化 RCE | confirmed | critical | true_positive | NV-03 | ok |
| `AUTHZ-001` profile_by_id 未授权 IDOR：匿名可改任意用户密码（账户接管） | confirmed | critical | true_positive | NV-02, NV-05, NV-10, NV-24 | ok |
| `AUTHZ-002` manage_groups POST 分支缺少权限检查，普通用户可提权到 admin_g | confirmed | high | true_positive | NV-06 | ok |
| `AUTHZ-003` 任务/笔记/项目/文件接口普遍 IDOR：匿名可改删任意数据并下载文件 | confirmed | high | true_positive | NV-09, NV-11, NV-12, NV-14 | ok |
| `XSS-001` 任务标题/描述 |safe 渲染导致匿名可触发的存储型 XSS | confirmed | high | true_positive | NV-09 | ok |
| `XSS-002` username 经 |safe 渲染，配合未授权改名构成存储型 XSS | confirmed | high | true_positive | NV-10 | ok |
| `XSS-003` 搜索参数 q |safe 渲染导致反射型 XSS | confirmed | medium | true_positive | NV-15 | ok |
| `XSS-004` settings 视图用 |safe 渲染 request.META：信息泄露 + 请求头反射 XSS | confirmed | medium | true_positive | NV-17 | ok |
| `REDIR-001` logout 开放重定向（redirect 参数未校验） | confirmed | medium | true_positive | NV-16 | ok |
| `AUTH-001` 弱随机密码重置令牌 + 无速率限制，可暴力枚举重置任意账号口令 | confirmed | high | true_positive | NV-20（附带陷阱 NVFP-02） | ok |
| `CRYPTO-001` 使用 MD5PasswordHasher 存储口令哈希，且默认账号哈希随仓库公开 | confirmed | medium | true_positive | NV-03, NV-19 | ok |
| `CONFIG-001` DEBUG/TEMPLATE_DEBUG 开启且 ALLOWED_HOSTS 为空，错误页泄露配置与堆栈 | confirmed | medium | false_positive_trap | NVFP-13 | — |
| `INFO-001` 登录接口用户名枚举（错误文案可区分账号是否存在） | confirmed | low | true_positive_optional | NVO-02 | ok |
| `CSRF-001` 多个口令相关端点被 csrf_exempt 豁免 CSRF 防护 | confirmed | low | false_positive_trap | NVFP-01, NVFP-02 | — |
| `AUTHZ-004` 注册表单 mass assignment：匿名可自助注册 is_superuser 超级用户 | confirmed | critical | true_positive | NV-04 | ok |
| `FILE-001` 任意文件（含 HTML/JS）落盘 Web 可服务目录并可同源访问 | confirmed | medium | true_positive | NV-01, NV-08, NV-22 | ok |
| `AUTH-002` 登录接口无速率限制/锁定，可无限在线爆破口令 | confirmed | low | true_positive_optional | NVO-02 | ok |

踩中的误报陷阱：

- NVFP-01 change_password 虽 csrf_exempt，但必须提交正确旧密码，跨站请求无法改密，CSRF 影响可忽略
- NVFP-02 forgot_password/reset_password 的 csrf_exempt 作用于未认证流程，跨站提交不借用受害者身份，不构成有意义的 CSRF（真实问题是令牌弱，见 NV-20）
- NVFP-13 ALLOWED_HOSTS=[] 在 DEBUG=True 下 Django 1.8 跳过 Host 校验，应用不在邮件或链接中使用 Host，Host 头注入无实际利用面

漏报：

- NV-13 [high] 备注创建/编辑/删除 IDOR
- NV-18 [medium] 生产配置提交 DEBUG=True / TEMPLATE_DEBUG=True
- NV-21 [medium] 使用存在已知漏洞的 Django 1.8.3
- NV-23 [medium] task_details 未做访问控制，任何人可读取任意任务及其备注
