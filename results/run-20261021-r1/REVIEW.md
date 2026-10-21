# 运行 `run-20261021-r1` 的评审

由 `audit_agent evaluate` 按 `eval/ground_truth.json` 自动生成，是对 report.md 的外部打分，不修改报告本身。

- 上报 15 条：命中真值 15，踩中误报陷阱 0，未匹配 0
- 精确率下限 1.0，召回率 0.562，高危及以上召回 1.0，按严重性加权召回 0.625

## 逐条判定

| 发现 | 报告严重性 | 判定 | 对应真值 / 陷阱 | 真值严重性 | 严重性对比 |
| --- | --- | --- | --- | --- | --- |
| `XSS-001` wiki 主题与回复正文存在存储型 XSS（Markdown 未启用 safe_mode，body_html 以 |safe 渲染） | high | 命中真值 | GT-01, GT-02 | high | 相符 |
| `XSS-002` account.views.register / password_reset 激活 key 未转义反射型 XSS | medium | 命中真值 | GT-04 | medium | 相符 |
| `FILE-001` ydata 附件上传文件名未校验导致路径穿越任意文件写入 | high | 命中真值 | GT-32（影响说过头：FP-05） | low | 偏高两级以上 |
| `ACCESS-002` editPostAJAX 越权编辑他人帖子（水平越权） | medium | 命中真值 | GT-06 | high | 相符 |
| `ACCESS-001` XML-RPC 删除/编辑主题接口缺少所有权与权限校验 | high | 命中真值 | GT-07, GT-31 | high | 相符 |
| `CSRF-001` 全站缺少 CSRF 防护且状态变更端点可被 GET 触发 | medium | 命中真值 | GT-13, GT-14 | medium | 相符 |
| `CRYPTO-001` 用户口令使用单轮 SHA1 + 弱盐存储 | medium | 命中真值 | GT-18, GT-19 | medium | 相符 |
| `CRYPTO-002` 密码重置令牌熵过低且无过期/防爆破机制 | medium | 命中真值 | GT-10 | high | 相符 |
| `CONFIG-001` DEBUG=True 生产配置泄露堆栈、设置与媒体目录 | medium | 命中真值 | GT-16 | medium | 相符 |
| `CONFIG-002` SECRET_KEY 硬编码入仓库致会话完整性校验可被伪造 | medium | 命中真值 | GT-17（影响说过头：FP-03） | medium | 相符 |
| `REDIR-001` logout 与管理登录存在开放重定向 | low | 命中真值 | GT-21, GT-22 | low | 相符 |
| `FILE-002` 附件下载缺少鉴权与目录权限校验 | low | 命中真值 | GT-08 | medium | 相符 |
| `MISC-001` ylab update_post_profile 匿名批量改写帖子数据 | low | 命中真值 | GT-15 | low | 相符 |
| `CONFIG-003` 数据库口令硬编码提交仓库（当前 sqlite 未生效） | low | 命中真值 | GT-17 | medium | 相符 |
| `ACCESS-003` 受限目录的读取路径未做组权限校验（读侧越权） | medium | 命中真值 | GT-08 | medium | 相符 |

## 漏报

- GT-03 [medium] ylinux_text_filter 把附件名/主题名未转义拼进 HTML（app/ydata/models.py:408, app/ydata/models.py:426, app/ydata/models.py:444）
- GT-05 [low] 上传响应把文件名拼进 <script>（app/ydata/views.py:91, app/ylab/views.py:32）
- GT-09 [low] 编辑主题可把主题移进无权访问的目录（app/ydata/forms.py:109, app/ydata/forms.py:123）
- GT-11 [medium] 重置接口接受字面量 key ALREADY_ACTIVATED（app/account/models.py:383, app/account/models.py:392, app/account/views.py:205）
- GT-12 [medium] 重置 key 不过期、用后不失效（app/account/views.py:217）
- GT-20 [medium] 登录后跳转到 next 参数，无同源校验（app/account/views.py:38, app/account/views.py:44）
- GT-23 [medium] 上传不限制类型，存放在可直接访问的媒体目录（app/ydata/views.py:78）
- GT-24 [low] 匿名联系表单可向任意地址发信（app/home/views.py:43）
- GT-25 [low] 注册/重置/登录可枚举用户（app/account/views.py:79, app/account/views.py:177）
- GT-26 [low] 无暴力破解防护，XML-RPC multicall 放大尝试次数（lib/django_xmlrpc/views.py:155, app/account/views.py:24, app/account/views.py:228）
- GT-27 [low] XML-RPC 请求体（含口令）打印到 stdout（lib/django_xmlrpc/views.py:82, app/ydata/views.py:97, app/ydata/views.py:124）
- GT-28 [low] 会话 cookie 未设 HttpOnly/Secure，凭据走明文 HTTP（app/sessions/middleware.py:37, app/account/views.py:191, app/account/models.py:419）
- GT-29 [low] 后台编辑用户表单暴露口令哈希并可提权为超级用户（app/admin/forms.py:103, app/admin/forms.py:115）
- GT-30 [low] 信任 X-Forwarded-For，并向所有用户展示发帖 IP（app/ydata/util.py:169, templates/wiki/add_post.html:25）
