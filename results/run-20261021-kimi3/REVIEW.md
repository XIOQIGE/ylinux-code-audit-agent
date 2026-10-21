# 运行 `run-20261021-kimi3` 的评审

用 `audit_agent evaluate` 对照 `eval/ground_truth.json` 生成，只是给 report.md 打分，不改报告本身。

- 上报 15 条：命中真值 14，踩中误报陷阱 1，未匹配 0
- 精确率下限 0.933，召回率 0.531，高危及以上召回 1.0，按严重性加权召回 0.602

## 逐条判定

| 发现 | 报告严重性 | 判定 | 对应真值 / 陷阱 | 真值严重性 | 严重性对比 |
| --- | --- | --- | --- | --- | --- |
| `XSS-001` 主题正文存储型 XSS：Markdown 渲染未启用 safe_mode，原始 HTML 原样输出并经 |safe 渲染 | high | 命中真值 | GT-01 | high | 相符 |
| `XSS-002` 回复正文存储型 XSS：markup='none' 的帖子用无 safe_mode 的 Markdown 渲染并经 |safe 输出 | high | 命中真值 | GT-02 | high | 相符 |
| `XSS-003` 注册/密码重置 key 未转义反射进 403 页面导致反射型 XSS | medium | 命中真值 | GT-04 | medium | 相符 |
| `XSS-005` 附件文件名未转义拼入正文 HTML 造成属性注入型存储 XSS | medium | 命中真值 | GT-03 | medium | 相符 |
| `ACCESS-001` editPostAJAX 缺少帖子属主校验：任意登录用户可修改任意帖子 | medium | 命中真值 | GT-06 | high | 相符 |
| `ACCESS-002` XML-RPC 仅认证无授权：任意注册用户可删除全站主题、修改任意主题、绕过目录组权限 | high | 命中真值 | GT-07, GT-31 | high | 相符 |
| `ACCESS-003` ylab update_post_profile 匿名批量改写全站帖子数据 | low | 命中真值 | GT-15 | low | 相符 |
| `CSRF-001` 全站未启用 CSRF 中间件，所有 Cookie 会话写操作可被跨站伪造 | medium | 命中真值 | GT-13 | high | 相符 |
| `CRYPTO-001` 弱口令哈希：单轮 SHA1+5字符随机盐，可低成本离线爆破 | medium | 命中真值 | GT-18, GT-19 | medium | 相符 |
| `CRYPTO-002` 密码重置/激活令牌熵仅 20bit 且不过期：可枚举重置链接接管账户 | medium | 命中真值 | GT-10 | high | 相符 |
| `SESSION-001` 会话存储使用 pickle 反序列化 + MD5 校验，签名密钥已提交进仓库 | medium | 误报（踩中已知陷阱） | FP-03 | — | — |
| `CONFIG-001` DEBUG=True 提交进仓库并暴露媒体目录列表 | medium | 命中真值 | GT-16 | medium | 相符 |
| `CONFIG-002` SECRET_KEY 硬编码并提交进公开仓库 | medium | 命中真值 | GT-17 | medium | 相符 |
| `CONFIG-003` 数据库口令 123456 明文提交进仓库 | low | 命中真值 | GT-17 | medium | 相符 |
| `REDIRECT-001` 登录/登出/管理员登录基于 next 与 Referer 的开放重定向 | medium | 命中真值 | GT-20, GT-21, GT-22 | medium | 相符 |

## 踩中的误报陷阱

- FP-03 pickle 会话后端未启用且数据存服务端，不能评为中危以上

## 漏报

- GT-05 [low] 上传响应把文件名拼进 <script>（app/ydata/views.py:91, app/ylab/views.py:32）
- GT-08 [medium] 受限目录只在写入时检查 has_access，读取路径不检查（app/ydata/models.py:91, app/wiki/views.py:82, app/wiki/views.py:120）
- GT-09 [low] 编辑主题可把主题移进无权访问的目录（app/ydata/forms.py:109, app/ydata/forms.py:123）
- GT-11 [medium] 重置接口接受字面量 key ALREADY_ACTIVATED（app/account/models.py:383, app/account/models.py:392, app/account/views.py:205）
- GT-12 [medium] 重置 key 不过期、用后不失效（app/account/views.py:217）
- GT-14 [medium] 删除/重启/推送等状态变更接受 GET（app/admin/views.py:133, app/admin/views.py:191, app/admin/views.py:256）
- GT-23 [medium] 上传不限制类型，存放在可直接访问的媒体目录（app/ydata/views.py:78）
- GT-24 [low] 匿名联系表单可向任意地址发信（app/home/views.py:43）
- GT-25 [low] 注册/重置/登录可枚举用户（app/account/views.py:79, app/account/views.py:177）
- GT-26 [low] 无暴力破解防护，XML-RPC multicall 放大尝试次数（lib/django_xmlrpc/views.py:155, app/account/views.py:24, app/account/views.py:228）
- GT-27 [low] XML-RPC 请求体（含口令）打印到 stdout（lib/django_xmlrpc/views.py:82, app/ydata/views.py:97, app/ydata/views.py:124）
- GT-28 [low] 会话 cookie 未设 HttpOnly/Secure，凭据走明文 HTTP（app/sessions/middleware.py:37, app/account/views.py:191, app/account/models.py:419）
- GT-29 [low] 后台编辑用户表单暴露口令哈希并可提权为超级用户（app/admin/forms.py:103, app/admin/forms.py:115）
- GT-30 [low] 信任 X-Forwarded-For，并向所有用户展示发帖 IP（app/ydata/util.py:169, templates/wiki/add_post.html:25）
- GT-32 [low] 上传附件不校验主题归属，可挂到任意主题（app/ydata/views.py:46, app/ydata/views.py:72, app/ydata/views.py:86）
