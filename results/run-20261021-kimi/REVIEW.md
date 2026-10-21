# 运行 `run-20261021-kimi` 的评审

用 `audit_agent evaluate` 对照 `eval/ground_truth.json` 生成，只是给 report.md 打分，不改报告本身。

- 上报 19 条：命中真值 18，踩中误报陷阱 1，未匹配 0
- 精确率下限 0.947，召回率 0.625，高危及以上召回 1.0，按严重性加权召回 0.693

## 逐条判定

| 发现 | 报告严重性 | 判定 | 对应真值 / 陷阱 | 真值严重性 | 严重性对比 |
| --- | --- | --- | --- | --- | --- |
| `XSS-001` 知识库/论坛帖子与主题正文存在存储型 XSS（Markdown 未启用 safe_mode 且模板 |safe 输出） | high | 命中真值 | GT-01, GT-02 | high | 相符 |
| `XSS-002` 附件文件名注入帖子渲染 HTML 导致存储型 XSS | high | 命中真值 | GT-02, GT-03, GT-23 | high | 相符 |
| `XSS-003` 注册/密码重置视图将 URL key 未转义回显导致反射型 XSS | medium | 命中真值 | GT-04 | medium | 相符 |
| `AUTHZ-001` XML-RPC 接口认证后无授权检查：任意注册用户可删除全站主题或篡改他人主题 | high | 命中真值 | GT-07, GT-31 | high | 相符 |
| `ACCESS-001` editPostAJAX 缺少属主校验：登录用户可篡改任意他人帖子 | medium | 命中真值 | GT-06 | high | 相符 |
| `ACCESS-002` /lab/update_post_profile 匿名可触发全站帖子批量改写 | medium | 命中真值 | GT-15 | low | 相符 |
| `CSRF-001` 全站缺少 CSRF 防护，Cookie 会话下的所有写操作可被跨站伪造 | medium | 命中真值 | GT-13 | high | 相符 |
| `CRYPTO-001` 密码重置/激活密钥仅 20 位熵且无尝试限制，可枚举实现账户接管 | high | 命中真值 | GT-10 | high | 相符 |
| `CRYPTO-002` 弱口令哈希（单轮 SHA1/MD5、弱盐）且登录接口无限速 | medium | 命中真值 | GT-18, GT-19 | medium | 相符 |
| `CONFIG-001` DEBUG=True 随仓库提交，且媒体目录带目录索引对外服务 | medium | 命中真值 | GT-16 | medium | 相符 |
| `CONFIG-002` SECRET_KEY 硬编码提交进公开仓库，会话签名与令牌生成失效 | medium | 命中真值 | GT-17 | medium | 相符 |
| `CONFIG-003` 数据库口令 '123456' 明文提交进仓库 | low | 命中真值 | GT-17 | medium | 相符 |
| `FILE-001` 附件上传文件名直接拼入保存路径（依赖框架 basename 清洗的纵深防御项） | low | 误报（踩中已知陷阱） | FP-05 | — | — |
| `REDIRECT-001` 登录/退出 next 参数未校验导致开放重定向 | low | 命中真值 | GT-20, GT-21 | low | 相符 |
| `EMAIL-001` 联系表单可被匿名滥用为任意收件人的邮件中继 | low | 命中真值 | GT-24 | low | 相符 |
| `DESER-001` 会话数据 pickle 反序列化 + 公开 SECRET_KEY 的 MD5 签名（潜在 RCE） | low | 命中可选项 | OPT-05 | info | 相符 |
| `XSS-004` 上传响应将文件名未转义拼入 HTML/JS 导致 self-XSS | low | 命中真值 | GT-05, GT-23 | low | 相符 |
| `ACCESS-003` 附件查看/下载端点无访问控制（权限模型不一致的加固项） | low | 命中真值 | GT-08 | medium | 相符 |
| `ACCESS-004` 版块组权限未在阅读路径强制：受限版块主题/帖子/附件匿名可读 | medium | 命中真值 | GT-08 | medium | 相符 |

## 踩中的误报陷阱

- FP-05 上传文件名经 UploadedFile 取 basename，不存在路径穿越

## 漏报

- GT-09 [low] 编辑主题可把主题移进无权访问的目录（app/ydata/forms.py:109, app/ydata/forms.py:123）
- GT-11 [medium] 重置接口接受字面量 key ALREADY_ACTIVATED（app/account/models.py:383, app/account/models.py:392, app/account/views.py:205）
- GT-12 [medium] 重置 key 不过期、用后不失效（app/account/views.py:217）
- GT-14 [medium] 删除/重启/推送等状态变更接受 GET（app/admin/views.py:133, app/admin/views.py:191, app/admin/views.py:256）
- GT-22 [low] 后台登录与 del_* 跳转到 Referer（app/admin/views.py:62, app/admin/views.py:134, app/admin/views.py:192）
- GT-25 [low] 注册/重置/登录可枚举用户（app/account/views.py:79, app/account/views.py:177）
- GT-26 [low] 无暴力破解防护，XML-RPC multicall 放大尝试次数（lib/django_xmlrpc/views.py:155, app/account/views.py:24, app/account/views.py:228）
- GT-27 [low] XML-RPC 请求体（含口令）打印到 stdout（lib/django_xmlrpc/views.py:82, app/ydata/views.py:97, app/ydata/views.py:124）
- GT-28 [low] 会话 cookie 未设 HttpOnly/Secure，凭据走明文 HTTP（app/sessions/middleware.py:37, app/account/views.py:191, app/account/models.py:419）
- GT-29 [low] 后台编辑用户表单暴露口令哈希并可提权为超级用户（app/admin/forms.py:103, app/admin/forms.py:115）
- GT-30 [low] 信任 X-Forwarded-For，并向所有用户展示发帖 IP（app/ydata/util.py:169, templates/wiki/add_post.html:25）
- GT-32 [low] 上传附件不校验主题归属，可挂到任意主题（app/ydata/views.py:46, app/ydata/views.py:72, app/ydata/views.py:86）
