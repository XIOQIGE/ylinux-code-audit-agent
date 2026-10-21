# 运行 `run-20261021-r3` 的评审

用 `audit_agent evaluate` 对照 `eval/ground_truth.json` 生成，只是给 report.md 打分，不改报告本身。

- 上报 16 条：命中真值 15，踩中误报陷阱 1，未匹配 0
- 精确率下限 0.938，召回率 0.625，高危及以上召回 1.0，按严重性加权召回 0.682

## 逐条判定

| 发现 | 报告严重性 | 判定 | 对应真值 / 陷阱 | 真值严重性 | 严重性对比 |
| --- | --- | --- | --- | --- | --- |
| `XSS-001` 主题与回复正文存储型 XSS（Markdown 未启用 safe_mode，模板 |safe 渲染） | high | 命中真值 | GT-01, GT-02 | high | 相符 |
| `XSS-002` 注册/密码重置视图对 URL key 未转义导致的反射型 XSS | medium | 命中真值 | GT-04 | medium | 相符 |
| `XSS-003` 上传文件名未转义嵌入响应脚本导致的 XSS（ylab/ydata 上传视图） | medium | 命中真值 | GT-05, GT-23 | medium | 相符 |
| `FILE-001` 附件上传文件名未消毒导致路径穿越任意文件写入 | high | 误报（踩中已知陷阱） | FP-05 | — | — |
| `ACCESS-001` editPostAJAX 缺少所有权校验，任意登录用户可编辑他人回复（IDOR） | medium | 命中真值 | GT-06 | high | 相符 |
| `ACCESS-002` XML-RPC 接口仅认证不鉴权：任意注册用户可删除全部主题或改写任意主题 | high | 命中真值 | GT-07, GT-31 | high | 相符 |
| `CSRF-001` 全站缺少 CSRF 防护，状态变更接口可被跨站请求伪造 | medium | 命中真值 | GT-13, GT-14 | medium | 相符 |
| `REDIRECT-001` logout/login 流程的 next 与 Referer 参数导致开放重定向 | medium | 命中真值 | GT-20, GT-21 | medium | 相符 |
| `ACCESS-003` ylab update_post_profile 未鉴权的全表写操作 | low | 命中真值 | GT-15 | low | 相符 |
| `CONFIG-001` DEBUG=True 提交进仓库并暴露 MEDIA_ROOT 目录浏览 | medium | 命中真值 | GT-16 | medium | 相符 |
| `CONFIG-002` SECRET_KEY 硬编码进仓库，会话签名与密码重置令牌可被伪造 | medium | 命中真值 | GT-17 | medium | 相符 |
| `CRYPTO-001` 密码使用弱哈希（单轮 SHA1 + 短弱随机盐） | medium | 命中真值 | GT-18, GT-19 | medium | 相符 |
| `SENSITIVE-001` AddUserForm 创建用户时口令未哈希（明文/空口令入库） | low | 命中真值 | GT-29 | low | 相符 |
| `CONFIG-003` 数据库与邮件凭据以明文弱口令形式提交进仓库 | low | 命中真值 | GT-17 | medium | 相符 |
| `CRYPTO-002` 注册/重置令牌熵仅约 20 bit 且无时效与速率限制，可枚举接管任意账号 | high | 命中真值 | GT-10 | high | 相符 |
| `FILE-002` 上传无类型白名单且落盘同源静态目录，可上传 HTML/SVG 形成同源存储型 XSS | medium | 命中真值 | GT-05, GT-23, GT-32 | medium | 相符 |

## 踩中的误报陷阱

- FP-05 上传文件名经 UploadedFile 取 basename，不存在路径穿越

## 漏报

- GT-03 [medium] ylinux_text_filter 把附件名/主题名未转义拼进 HTML（app/ydata/models.py:408, app/ydata/models.py:426, app/ydata/models.py:444）
- GT-08 [medium] 受限目录只在写入时检查 has_access，读取路径不检查（app/ydata/models.py:91, app/wiki/views.py:82, app/wiki/views.py:120）
- GT-09 [low] 编辑主题可把主题移进无权访问的目录（app/ydata/forms.py:109, app/ydata/forms.py:123）
- GT-11 [medium] 重置接口接受字面量 key ALREADY_ACTIVATED（app/account/models.py:383, app/account/models.py:392, app/account/views.py:205）
- GT-12 [medium] 重置 key 不过期、用后不失效（app/account/views.py:217）
- GT-22 [low] 后台登录与 del_* 跳转到 Referer（app/admin/views.py:62, app/admin/views.py:134, app/admin/views.py:192）
- GT-24 [low] 匿名联系表单可向任意地址发信（app/home/views.py:43）
- GT-25 [low] 注册/重置/登录可枚举用户（app/account/views.py:79, app/account/views.py:177）
- GT-26 [low] 无暴力破解防护，XML-RPC multicall 放大尝试次数（lib/django_xmlrpc/views.py:155, app/account/views.py:24, app/account/views.py:228）
- GT-27 [low] XML-RPC 请求体（含口令）打印到 stdout（lib/django_xmlrpc/views.py:82, app/ydata/views.py:97, app/ydata/views.py:124）
- GT-28 [low] 会话 cookie 未设 HttpOnly/Secure，凭据走明文 HTTP（app/sessions/middleware.py:37, app/account/views.py:191, app/account/models.py:419）
- GT-30 [low] 信任 X-Forwarded-For，并向所有用户展示发帖 IP（app/ydata/util.py:169, templates/wiki/add_post.html:25）
