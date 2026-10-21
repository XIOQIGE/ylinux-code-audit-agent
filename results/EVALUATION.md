# 评测结果

由 `python -m audit_agent evaluate` 生成。真值见 `eval/ground_truth.json`（https://github.com/gwind/ylinux_old）。

| 运行 | 上报 | 命中真值 | 踩中误报陷阱 | 未匹配 | 精确率下限 | 召回率 | 高危及以上召回 | 按严重性加权召回 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `run-20261020` | 7 | 6 | 1 | 0 | 0.857 | 0.188 | 0.5 | 0.227 |
| `run-20261021` | 15 | 15 | 0 | 0 | 1.0 | 0.688 | 1.0 | 0.727 |
| `run-20261021-kimi` | 19 | 18 | 1 | 0 | 0.947 | 0.625 | 1.0 | 0.693 |
| `run-20261021-r1` | 15 | 15 | 0 | 0 | 1.0 | 0.562 | 1.0 | 0.625 |
| `run-20261021-r2` | 12 | 11 | 1 | 0 | 0.917 | 0.531 | 1.0 | 0.602 |
| `run-20261021-r3` | 16 | 15 | 1 | 0 | 0.938 | 0.625 | 1.0 | 0.682 |

“未匹配”既可能是误报，也可能是真值清单没收录的真问题，需要人工看。所以精确率只给下限。“附带陷阱”表示发现的主体命中了真值，但部分证据或影响落在已知误判上（问题对、影响说过头）。

## `run-20261020`

| 发现 | 状态 | 严重性 | 判定 | 对应真值 | 严重性偏差 |
| --- | --- | --- | --- | --- | --- |
| `CONFIG-001` DEBUG 模式开启 | confirmed | medium | true_positive | GT-16 | ok |
| `CONFIG-002` 硬编码数据库密码 | confirmed | high | true_positive | GT-17 | ok |
| `CONFIG-003` 硬编码 SECRET_KEY | confirmed | high | true_positive | GT-17 | ok |
| `CRYPTO-002` 弱随机盐生成 | confirmed | medium | true_positive | GT-10 | ok |
| `XSS-001` 模板中未转义的 HTML 输出 | confirmed | medium | true_positive | GT-01, GT-02 | ok |
| `CRYPTO-001` 弱密码哈希算法 | confirmed | high | true_positive | GT-19 | over |
| `INJECTION-001` 潜在命令注入风险 | confirmed | high | false_positive_trap | FP-01 | — |

踩中的误报陷阱：

- FP-01 reboot 里的 os.system 没有请求数据参与，不是命令注入

漏报：

- GT-03 [medium] ylinux_text_filter 把附件名/主题名未转义拼进 HTML
- GT-04 [medium] 注册/重置链接中的 key 原样写进 HttpResponseForbidden（反射型 XSS）
- GT-05 [low] 上传响应把文件名拼进 <script>
- GT-06 [high] editPostAJAX 不校验帖子归属（IDOR）
- GT-07 [high] XML-RPC 任意认证用户可删除/编辑任意主题乃至全部主题
- GT-08 [medium] 受限目录只在写入时检查 has_access，读取路径不检查
- GT-09 [low] 编辑主题可把主题移进无权访问的目录
- GT-11 [medium] 重置接口接受字面量 key ALREADY_ACTIVATED
- GT-12 [medium] 重置 key 不过期、用后不失效
- GT-13 [high] 全站没有 CSRF 中间件
- GT-14 [medium] 删除/重启/推送等状态变更接受 GET
- GT-15 [low] /lab/update_post_profile 匿名批量改写全部帖子
- GT-18 [medium] 口令哈希为单轮 SHA-1 + 20 位随机盐
- GT-20 [medium] 登录后跳转到 next 参数，无同源校验
- GT-21 [low] 注销后跳转到 next 参数
- GT-22 [low] 后台登录与 del_* 跳转到 Referer
- GT-23 [medium] 上传不限制类型，存放在可直接访问的媒体目录
- GT-24 [low] 匿名联系表单可向任意地址发信
- GT-25 [low] 注册/重置/登录可枚举用户
- GT-26 [low] 无暴力破解防护，XML-RPC multicall 放大尝试次数
- GT-27 [low] XML-RPC 请求体（含口令）打印到 stdout
- GT-28 [low] 会话 cookie 未设 HttpOnly/Secure，凭据走明文 HTTP
- GT-29 [low] 后台编辑用户表单暴露口令哈希并可提权为超级用户
- GT-30 [low] 信任 X-Forwarded-For，并向所有用户展示发帖 IP
- GT-31 [medium] XML-RPC 认证不检查 is_active，被禁用的账户仍可调用删除接口
- GT-32 [low] 上传附件不校验主题归属，可挂到任意主题

## `run-20261021`

| 发现 | 状态 | 严重性 | 判定 | 对应真值 | 严重性偏差 |
| --- | --- | --- | --- | --- | --- |
| `XSS-001` Markdown 渲染未开 safe_mode，主题/回复内容可注入原始 HTML 造成全站存储型 XSS | confirmed | high | true_positive | GT-01, GT-02 | ok |
| `XSS-002` 注册/重置密码错误页把 URL 中的 key 未转义拼接进 HTML，反射型 XSS | confirmed | medium | true_positive | GT-04 | ok |
| `REDIRECT-001` 登录/退出/后台登录处基于 next 与 Referer 的开放重定向 | confirmed | low | true_positive | GT-20, GT-21, GT-22 | ok |
| `CRYPTO-001` SECRET_KEY 硬编码入库，会话防篡改校验与重置令牌失去保密性 | confirmed | high | true_positive | GT-17（附带陷阱 FP-03） | ok |
| `CRYPTO-002` 弱口令哈希：单轮 SHA1/MD5 + 弱随机盐 | confirmed | medium | true_positive | GT-18, GT-19 | ok |
| `CRYPTO-003` 激活/重置 key 弱熵（20 bit 盐）可暴力枚举导致账户接管 | confirmed | high | true_positive | GT-10 | ok |
| `CSRF-001` 全站未启用 CSRF 防护，后台删除等写操作可被跨站伪造 | confirmed | medium | true_positive | GT-13, GT-14 | ok |
| `CONFIG-001` DEBUG=True 提交进配置，且 MEDIA_ROOT 开启目录浏览 | confirmed | medium | true_positive | GT-16 | ok |
| `CONFIG-002` 数据库口令明文弱口令提交进仓库 | confirmed | low | true_positive | GT-17 | ok |
| `ACCESS-001` editPostAJAX 缺少帖子归属校验，任意登录用户可篡改他人帖子 | confirmed | medium | true_positive | GT-06 | ok |
| `FILE-001` 上传文件名未清洗：头注入/JS 注入风险，XML-RPC 可投放任意内容到媒体目录 | confirmed | low | true_positive | GT-05, GT-23, GT-32 | ok |
| `ACCESS-002` XML-RPC 删除/编辑接口缺少对象级授权，任意用户可删改全站内容 | confirmed | medium | true_positive | GT-07, GT-31 | ok |
| `ACCESS-003` update_post_profile 维护端点无鉴权，匿名可触发全表重写 | confirmed | low | true_positive | GT-15 | ok |
| `COOKIE-001` 会话 Cookie 未设置 HttpOnly/Secure，XSS 可直接窃取会话 | confirmed | low | true_positive | GT-28 | ok |
| `AUTH-001` 所有认证入口缺少速率限制/失败锁定，口令可在线爆破 | confirmed | low | true_positive | GT-26, GT-31 | ok |

漏报：

- GT-03 [medium] ylinux_text_filter 把附件名/主题名未转义拼进 HTML
- GT-08 [medium] 受限目录只在写入时检查 has_access，读取路径不检查
- GT-09 [low] 编辑主题可把主题移进无权访问的目录
- GT-11 [medium] 重置接口接受字面量 key ALREADY_ACTIVATED
- GT-12 [medium] 重置 key 不过期、用后不失效
- GT-24 [low] 匿名联系表单可向任意地址发信
- GT-25 [low] 注册/重置/登录可枚举用户
- GT-27 [low] XML-RPC 请求体（含口令）打印到 stdout
- GT-29 [low] 后台编辑用户表单暴露口令哈希并可提权为超级用户
- GT-30 [low] 信任 X-Forwarded-For，并向所有用户展示发帖 IP

## `run-20261021-kimi`

| 发现 | 状态 | 严重性 | 判定 | 对应真值 | 严重性偏差 |
| --- | --- | --- | --- | --- | --- |
| `XSS-001` 知识库/论坛帖子与主题正文存在存储型 XSS（Markdown 未启用 safe_mode 且模板 |safe 输出） | confirmed | high | true_positive | GT-01, GT-02 | ok |
| `XSS-002` 附件文件名注入帖子渲染 HTML 导致存储型 XSS | confirmed | high | true_positive | GT-02, GT-03, GT-23 | ok |
| `XSS-003` 注册/密码重置视图将 URL key 未转义回显导致反射型 XSS | confirmed | medium | true_positive | GT-04 | ok |
| `AUTHZ-001` XML-RPC 接口认证后无授权检查：任意注册用户可删除全站主题或篡改他人主题 | confirmed | high | true_positive | GT-07, GT-31 | ok |
| `ACCESS-001` editPostAJAX 缺少属主校验：登录用户可篡改任意他人帖子 | confirmed | medium | true_positive | GT-06 | ok |
| `ACCESS-002` /lab/update_post_profile 匿名可触发全站帖子批量改写 | confirmed | medium | true_positive | GT-15 | ok |
| `CSRF-001` 全站缺少 CSRF 防护，Cookie 会话下的所有写操作可被跨站伪造 | confirmed | medium | true_positive | GT-13 | ok |
| `CRYPTO-001` 密码重置/激活密钥仅 20 位熵且无尝试限制，可枚举实现账户接管 | confirmed | high | true_positive | GT-10 | ok |
| `CRYPTO-002` 弱口令哈希（单轮 SHA1/MD5、弱盐）且登录接口无限速 | confirmed | medium | true_positive | GT-18, GT-19 | ok |
| `CONFIG-001` DEBUG=True 随仓库提交，且媒体目录带目录索引对外服务 | confirmed | medium | true_positive | GT-16 | ok |
| `CONFIG-002` SECRET_KEY 硬编码提交进公开仓库，会话签名与令牌生成失效 | confirmed | medium | true_positive | GT-17 | ok |
| `CONFIG-003` 数据库口令 '123456' 明文提交进仓库 | confirmed | low | true_positive | GT-17 | ok |
| `FILE-001` 附件上传文件名直接拼入保存路径（依赖框架 basename 清洗的纵深防御项） | needs_review | low | false_positive_trap | FP-05 | — |
| `REDIRECT-001` 登录/退出 next 参数未校验导致开放重定向 | confirmed | low | true_positive | GT-20, GT-21 | ok |
| `EMAIL-001` 联系表单可被匿名滥用为任意收件人的邮件中继 | confirmed | low | true_positive | GT-24 | ok |
| `DESER-001` 会话数据 pickle 反序列化 + 公开 SECRET_KEY 的 MD5 签名（潜在 RCE） | needs_review | low | true_positive_optional | OPT-05 | ok |
| `XSS-004` 上传响应将文件名未转义拼入 HTML/JS 导致 self-XSS | confirmed | low | true_positive | GT-05, GT-23 | ok |
| `ACCESS-003` 附件查看/下载端点无访问控制（权限模型不一致的加固项） | confirmed | low | true_positive | GT-08 | ok |
| `ACCESS-004` 版块组权限未在阅读路径强制：受限版块主题/帖子/附件匿名可读 | confirmed | medium | true_positive | GT-08 | ok |

踩中的误报陷阱：

- FP-05 上传文件名经 UploadedFile 取 basename，不存在路径穿越

漏报：

- GT-09 [low] 编辑主题可把主题移进无权访问的目录
- GT-11 [medium] 重置接口接受字面量 key ALREADY_ACTIVATED
- GT-12 [medium] 重置 key 不过期、用后不失效
- GT-14 [medium] 删除/重启/推送等状态变更接受 GET
- GT-22 [low] 后台登录与 del_* 跳转到 Referer
- GT-25 [low] 注册/重置/登录可枚举用户
- GT-26 [low] 无暴力破解防护，XML-RPC multicall 放大尝试次数
- GT-27 [low] XML-RPC 请求体（含口令）打印到 stdout
- GT-28 [low] 会话 cookie 未设 HttpOnly/Secure，凭据走明文 HTTP
- GT-29 [low] 后台编辑用户表单暴露口令哈希并可提权为超级用户
- GT-30 [low] 信任 X-Forwarded-For，并向所有用户展示发帖 IP
- GT-32 [low] 上传附件不校验主题归属，可挂到任意主题

## `run-20261021-r1`

| 发现 | 状态 | 严重性 | 判定 | 对应真值 | 严重性偏差 |
| --- | --- | --- | --- | --- | --- |
| `XSS-001` wiki 主题与回复正文存在存储型 XSS（Markdown 未启用 safe_mode，body_html 以 |safe 渲染） | confirmed | high | true_positive | GT-01, GT-02 | ok |
| `XSS-002` account.views.register / password_reset 激活 key 未转义反射型 XSS | confirmed | medium | true_positive | GT-04 | ok |
| `FILE-001` ydata 附件上传文件名未校验导致路径穿越任意文件写入 | confirmed | high | true_positive | GT-32（附带陷阱 FP-05） | over |
| `ACCESS-002` editPostAJAX 越权编辑他人帖子（水平越权） | confirmed | medium | true_positive | GT-06 | ok |
| `ACCESS-001` XML-RPC 删除/编辑主题接口缺少所有权与权限校验 | confirmed | high | true_positive | GT-07, GT-31 | ok |
| `CSRF-001` 全站缺少 CSRF 防护且状态变更端点可被 GET 触发 | confirmed | medium | true_positive | GT-13, GT-14 | ok |
| `CRYPTO-001` 用户口令使用单轮 SHA1 + 弱盐存储 | confirmed | medium | true_positive | GT-18, GT-19 | ok |
| `CRYPTO-002` 密码重置令牌熵过低且无过期/防爆破机制 | confirmed | medium | true_positive | GT-10 | ok |
| `CONFIG-001` DEBUG=True 生产配置泄露堆栈、设置与媒体目录 | confirmed | medium | true_positive | GT-16 | ok |
| `CONFIG-002` SECRET_KEY 硬编码入仓库致会话完整性校验可被伪造 | confirmed | medium | true_positive | GT-17（附带陷阱 FP-03） | ok |
| `REDIR-001` logout 与管理登录存在开放重定向 | confirmed | low | true_positive | GT-21, GT-22 | ok |
| `FILE-002` 附件下载缺少鉴权与目录权限校验 | confirmed | low | true_positive | GT-08 | ok |
| `MISC-001` ylab update_post_profile 匿名批量改写帖子数据 | confirmed | low | true_positive | GT-15 | ok |
| `CONFIG-003` 数据库口令硬编码提交仓库（当前 sqlite 未生效） | confirmed | low | true_positive | GT-17 | ok |
| `ACCESS-003` 受限目录的读取路径未做组权限校验（读侧越权） | confirmed | medium | true_positive | GT-08 | ok |

漏报：

- GT-03 [medium] ylinux_text_filter 把附件名/主题名未转义拼进 HTML
- GT-05 [low] 上传响应把文件名拼进 <script>
- GT-09 [low] 编辑主题可把主题移进无权访问的目录
- GT-11 [medium] 重置接口接受字面量 key ALREADY_ACTIVATED
- GT-12 [medium] 重置 key 不过期、用后不失效
- GT-20 [medium] 登录后跳转到 next 参数，无同源校验
- GT-23 [medium] 上传不限制类型，存放在可直接访问的媒体目录
- GT-24 [low] 匿名联系表单可向任意地址发信
- GT-25 [low] 注册/重置/登录可枚举用户
- GT-26 [low] 无暴力破解防护，XML-RPC multicall 放大尝试次数
- GT-27 [low] XML-RPC 请求体（含口令）打印到 stdout
- GT-28 [low] 会话 cookie 未设 HttpOnly/Secure，凭据走明文 HTTP
- GT-29 [low] 后台编辑用户表单暴露口令哈希并可提权为超级用户
- GT-30 [low] 信任 X-Forwarded-For，并向所有用户展示发帖 IP

## `run-20261021-r2`

| 发现 | 状态 | 严重性 | 判定 | 对应真值 | 严重性偏差 |
| --- | --- | --- | --- | --- | --- |
| `XSS-001` 主题/回复正文 Markdown 渲染未启用 safe_mode，存储型 XSS | confirmed | high | true_positive | GT-01, GT-02 | ok |
| `FILE-001` 附件上传文件名路径穿越，可向 MEDIA_ROOT 任意位置写文件 | confirmed | high | false_positive_trap | FP-05 | — |
| `ACL-001` XML-RPC 写接口只有认证没有授权：任意注册用户可删除/篡改全站主题 | confirmed | high | true_positive | GT-07, GT-31 | ok |
| `CSRF-001` 全站缺少 CSRF 防护，删除/重启等敏感操作可用 GET 跨站触发 | confirmed | medium | true_positive | GT-13, GT-14 | ok |
| `ACL-002` editPostAJAX 缺少属主校验：任意登录用户可编辑他人帖子 | confirmed | medium | true_positive | GT-06 | ok |
| `XSS-002` 注册/密码重置 key 参数反射型 XSS（匿名可达） | confirmed | medium | true_positive | GT-04 | ok |
| `REDIR-001` logout/login 的 next 与 admin Referer 重定向未校验（开放重定向） | confirmed | low | true_positive | GT-20, GT-21, GT-22 | ok |
| `CRYPTO-001` 口令使用无迭代 SHA1 + 5 字符弱盐存储 | confirmed | medium | true_positive | GT-18, GT-19 | ok |
| `CRYPTO-002` 密码重置/激活 key 熵仅 20 位，可在线爆破接管账号 | confirmed | medium | true_positive | GT-10 | ok |
| `CONFIG-001` DEBUG=True 且 /ymedia/ 静态目录带目录列举暴露在生产 | confirmed | medium | true_positive | GT-16 | ok |
| `CONFIG-002` SECRET_KEY 与数据库口令硬编码提交进仓库 | confirmed | medium | true_positive | GT-17 | ok |
| `LAB-001` lab 调试端点未授权暴露：匿名批量改写帖子与测试上传 | confirmed | low | true_positive | GT-15 | ok |

踩中的误报陷阱：

- FP-05 上传文件名经 UploadedFile 取 basename，不存在路径穿越

漏报：

- GT-03 [medium] ylinux_text_filter 把附件名/主题名未转义拼进 HTML
- GT-05 [low] 上传响应把文件名拼进 <script>
- GT-08 [medium] 受限目录只在写入时检查 has_access，读取路径不检查
- GT-09 [low] 编辑主题可把主题移进无权访问的目录
- GT-11 [medium] 重置接口接受字面量 key ALREADY_ACTIVATED
- GT-12 [medium] 重置 key 不过期、用后不失效
- GT-23 [medium] 上传不限制类型，存放在可直接访问的媒体目录
- GT-24 [low] 匿名联系表单可向任意地址发信
- GT-25 [low] 注册/重置/登录可枚举用户
- GT-26 [low] 无暴力破解防护，XML-RPC multicall 放大尝试次数
- GT-27 [low] XML-RPC 请求体（含口令）打印到 stdout
- GT-28 [low] 会话 cookie 未设 HttpOnly/Secure，凭据走明文 HTTP
- GT-29 [low] 后台编辑用户表单暴露口令哈希并可提权为超级用户
- GT-30 [low] 信任 X-Forwarded-For，并向所有用户展示发帖 IP
- GT-32 [low] 上传附件不校验主题归属，可挂到任意主题

## `run-20261021-r3`

| 发现 | 状态 | 严重性 | 判定 | 对应真值 | 严重性偏差 |
| --- | --- | --- | --- | --- | --- |
| `XSS-001` 主题与回复正文存储型 XSS（Markdown 未启用 safe_mode，模板 |safe 渲染） | confirmed | high | true_positive | GT-01, GT-02 | ok |
| `XSS-002` 注册/密码重置视图对 URL key 未转义导致的反射型 XSS | confirmed | medium | true_positive | GT-04 | ok |
| `XSS-003` 上传文件名未转义嵌入响应脚本导致的 XSS（ylab/ydata 上传视图） | confirmed | medium | true_positive | GT-05, GT-23 | ok |
| `FILE-001` 附件上传文件名未消毒导致路径穿越任意文件写入 | confirmed | high | false_positive_trap | FP-05 | — |
| `ACCESS-001` editPostAJAX 缺少所有权校验，任意登录用户可编辑他人回复（IDOR） | confirmed | medium | true_positive | GT-06 | ok |
| `ACCESS-002` XML-RPC 接口仅认证不鉴权：任意注册用户可删除全部主题或改写任意主题 | confirmed | high | true_positive | GT-07, GT-31 | ok |
| `CSRF-001` 全站缺少 CSRF 防护，状态变更接口可被跨站请求伪造 | confirmed | medium | true_positive | GT-13, GT-14 | ok |
| `REDIRECT-001` logout/login 流程的 next 与 Referer 参数导致开放重定向 | confirmed | medium | true_positive | GT-20, GT-21 | ok |
| `ACCESS-003` ylab update_post_profile 未鉴权的全表写操作 | confirmed | low | true_positive | GT-15 | ok |
| `CONFIG-001` DEBUG=True 提交进仓库并暴露 MEDIA_ROOT 目录浏览 | confirmed | medium | true_positive | GT-16 | ok |
| `CONFIG-002` SECRET_KEY 硬编码进仓库，会话签名与密码重置令牌可被伪造 | confirmed | medium | true_positive | GT-17 | ok |
| `CRYPTO-001` 密码使用弱哈希（单轮 SHA1 + 短弱随机盐） | confirmed | medium | true_positive | GT-18, GT-19 | ok |
| `SENSITIVE-001` AddUserForm 创建用户时口令未哈希（明文/空口令入库） | confirmed | low | true_positive | GT-29 | ok |
| `CONFIG-003` 数据库与邮件凭据以明文弱口令形式提交进仓库 | confirmed | low | true_positive | GT-17 | ok |
| `CRYPTO-002` 注册/重置令牌熵仅约 20 bit 且无时效与速率限制，可枚举接管任意账号 | confirmed | high | true_positive | GT-10 | ok |
| `FILE-002` 上传无类型白名单且落盘同源静态目录，可上传 HTML/SVG 形成同源存储型 XSS | confirmed | medium | true_positive | GT-05, GT-23, GT-32 | ok |

踩中的误报陷阱：

- FP-05 上传文件名经 UploadedFile 取 basename，不存在路径穿越

漏报：

- GT-03 [medium] ylinux_text_filter 把附件名/主题名未转义拼进 HTML
- GT-08 [medium] 受限目录只在写入时检查 has_access，读取路径不检查
- GT-09 [low] 编辑主题可把主题移进无权访问的目录
- GT-11 [medium] 重置接口接受字面量 key ALREADY_ACTIVATED
- GT-12 [medium] 重置 key 不过期、用后不失效
- GT-22 [low] 后台登录与 del_* 跳转到 Referer
- GT-24 [low] 匿名联系表单可向任意地址发信
- GT-25 [low] 注册/重置/登录可枚举用户
- GT-26 [low] 无暴力破解防护，XML-RPC multicall 放大尝试次数
- GT-27 [low] XML-RPC 请求体（含口令）打印到 stdout
- GT-28 [low] 会话 cookie 未设 HttpOnly/Secure，凭据走明文 HTTP
- GT-30 [low] 信任 X-Forwarded-For，并向所有用户展示发帖 IP

## 重复运行的波动

均值 ± 样本标准差（最小 – 最大）。同一套代码、同一模型、同一目标，差异只来自模型采样。

| 组 | 次数 | 上报数 | 精确率下限 | 召回率 | 高危及以上召回 | 加权召回 |
| --- | --- | --- | --- | --- | --- | --- |
| `deepseek-x3` | 3 | 14.333 ± 2.082 (12 – 16) | 0.952 ± 0.043 (0.917 – 1) | 0.573 ± 0.048 (0.531 – 0.625) | 1.0 ± 0.0 (1 – 1) | 0.636 ± 0.041 (0.602 – 0.682) |
| `deepseek-x4` | 4 | 14.5 ± 1.732 (12 – 16) | 0.964 ± 0.043 (0.917 – 1) | 0.602 ± 0.07 (0.531 – 0.688) | 1.0 ± 0.0 (1 – 1) | 0.659 ± 0.056 (0.602 – 0.727) |

### `deepseek-x3`：每条真值被找到的次数

| 真值 | 严重性 | 标题 | 命中 |
| --- | --- | --- | --- |
| GT-01 | high | 主题正文 Markdown 未开 safe_mode，经 |safe 输出（存储型 XSS） | 3/3 |
| GT-02 | high | 回帖正文 Markdown 未开 safe_mode，经 |safe / POST_HTML 输出（存储型 XSS） | 3/3 |
| GT-06 | high | editPostAJAX 不校验帖子归属（IDOR） | 3/3 |
| GT-07 | high | XML-RPC 任意认证用户可删除/编辑任意主题乃至全部主题 | 3/3 |
| GT-10 | high | 激活/重置 key 只有 5 位十六进制随机盐，可暴力枚举 | 3/3 |
| GT-13 | high | 全站没有 CSRF 中间件 | 3/3 |
| GT-03 | medium | ylinux_text_filter 把附件名/主题名未转义拼进 HTML | 0/3 |
| GT-11 | medium | 重置接口接受字面量 key ALREADY_ACTIVATED | 0/3 |
| GT-12 | medium | 重置 key 不过期、用后不失效 | 0/3 |
| GT-08 | medium | 受限目录只在写入时检查 has_access，读取路径不检查 | 1/3 |
| GT-23 | medium | 上传不限制类型，存放在可直接访问的媒体目录 | 1/3 |
| GT-20 | medium | 登录后跳转到 next 参数，无同源校验 | 2/3 |
| GT-04 | medium | 注册/重置链接中的 key 原样写进 HttpResponseForbidden（反射型 XSS） | 3/3 |
| GT-14 | medium | 删除/重启/推送等状态变更接受 GET | 3/3 |
| GT-16 | medium | DEBUG=True 且 static serve 开启目录列表 | 3/3 |
| GT-17 | medium | SECRET_KEY 与数据库密码硬编码入库 | 3/3 |
| GT-18 | medium | 口令哈希为单轮 SHA-1 + 20 位随机盐 | 3/3 |
| GT-31 | medium | XML-RPC 认证不检查 is_active，被禁用的账户仍可调用删除接口 | 3/3 |
| GT-09 | low | 编辑主题可把主题移进无权访问的目录 | 0/3 |
| GT-24 | low | 匿名联系表单可向任意地址发信 | 0/3 |
| GT-25 | low | 注册/重置/登录可枚举用户 | 0/3 |
| GT-26 | low | 无暴力破解防护，XML-RPC multicall 放大尝试次数 | 0/3 |
| GT-27 | low | XML-RPC 请求体（含口令）打印到 stdout | 0/3 |
| GT-28 | low | 会话 cookie 未设 HttpOnly/Secure，凭据走明文 HTTP | 0/3 |
| GT-30 | low | 信任 X-Forwarded-For，并向所有用户展示发帖 IP | 0/3 |
| GT-05 | low | 上传响应把文件名拼进 <script> | 1/3 |
| GT-29 | low | 后台编辑用户表单暴露口令哈希并可提权为超级用户 | 1/3 |
| GT-22 | low | 后台登录与 del_* 跳转到 Referer | 2/3 |
| GT-32 | low | 上传附件不校验主题归属，可挂到任意主题 | 2/3 |
| GT-15 | low | /lab/update_post_profile 匿名批量改写全部帖子 | 3/3 |
| GT-19 | low | 接受无盐 MD5 旧口令，非常量时间比较 | 3/3 |
| GT-21 | low | 注销后跳转到 next 参数 | 3/3 |

每次都找到 15 条，从未找到 10 条，其余 7 条时有时无。

### `deepseek-x4`：每条真值被找到的次数

| 真值 | 严重性 | 标题 | 命中 |
| --- | --- | --- | --- |
| GT-01 | high | 主题正文 Markdown 未开 safe_mode，经 |safe 输出（存储型 XSS） | 4/4 |
| GT-02 | high | 回帖正文 Markdown 未开 safe_mode，经 |safe / POST_HTML 输出（存储型 XSS） | 4/4 |
| GT-06 | high | editPostAJAX 不校验帖子归属（IDOR） | 4/4 |
| GT-07 | high | XML-RPC 任意认证用户可删除/编辑任意主题乃至全部主题 | 4/4 |
| GT-10 | high | 激活/重置 key 只有 5 位十六进制随机盐，可暴力枚举 | 4/4 |
| GT-13 | high | 全站没有 CSRF 中间件 | 4/4 |
| GT-03 | medium | ylinux_text_filter 把附件名/主题名未转义拼进 HTML | 0/4 |
| GT-11 | medium | 重置接口接受字面量 key ALREADY_ACTIVATED | 0/4 |
| GT-12 | medium | 重置 key 不过期、用后不失效 | 0/4 |
| GT-08 | medium | 受限目录只在写入时检查 has_access，读取路径不检查 | 1/4 |
| GT-23 | medium | 上传不限制类型，存放在可直接访问的媒体目录 | 2/4 |
| GT-20 | medium | 登录后跳转到 next 参数，无同源校验 | 3/4 |
| GT-04 | medium | 注册/重置链接中的 key 原样写进 HttpResponseForbidden（反射型 XSS） | 4/4 |
| GT-14 | medium | 删除/重启/推送等状态变更接受 GET | 4/4 |
| GT-16 | medium | DEBUG=True 且 static serve 开启目录列表 | 4/4 |
| GT-17 | medium | SECRET_KEY 与数据库密码硬编码入库 | 4/4 |
| GT-18 | medium | 口令哈希为单轮 SHA-1 + 20 位随机盐 | 4/4 |
| GT-31 | medium | XML-RPC 认证不检查 is_active，被禁用的账户仍可调用删除接口 | 4/4 |
| GT-09 | low | 编辑主题可把主题移进无权访问的目录 | 0/4 |
| GT-24 | low | 匿名联系表单可向任意地址发信 | 0/4 |
| GT-25 | low | 注册/重置/登录可枚举用户 | 0/4 |
| GT-27 | low | XML-RPC 请求体（含口令）打印到 stdout | 0/4 |
| GT-30 | low | 信任 X-Forwarded-For，并向所有用户展示发帖 IP | 0/4 |
| GT-26 | low | 无暴力破解防护，XML-RPC multicall 放大尝试次数 | 1/4 |
| GT-28 | low | 会话 cookie 未设 HttpOnly/Secure，凭据走明文 HTTP | 1/4 |
| GT-29 | low | 后台编辑用户表单暴露口令哈希并可提权为超级用户 | 1/4 |
| GT-05 | low | 上传响应把文件名拼进 <script> | 2/4 |
| GT-22 | low | 后台登录与 del_* 跳转到 Referer | 3/4 |
| GT-32 | low | 上传附件不校验主题归属，可挂到任意主题 | 3/4 |
| GT-15 | low | /lab/update_post_profile 匿名批量改写全部帖子 | 4/4 |
| GT-19 | low | 接受无盐 MD5 旧口令，非常量时间比较 | 4/4 |
| GT-21 | low | 注销后跳转到 next 参数 | 4/4 |

每次都找到 15 条，从未找到 8 条，其余 9 条时有时无。
