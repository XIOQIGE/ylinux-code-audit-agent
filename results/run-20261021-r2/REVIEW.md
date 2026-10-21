# 运行 `run-20261021-r2` 的评审

用 `audit_agent evaluate` 对照 `eval/ground_truth.json` 生成，只是给 report.md 打分，不改报告本身。

- 上报 12 条：命中真值 11，踩中误报陷阱 1，未匹配 0
- 精确率下限 0.917，召回率 0.531，高危及以上召回 1.0，按严重性加权召回 0.602

## 逐条判定

| 发现 | 报告严重性 | 判定 | 对应真值 / 陷阱 | 真值严重性 | 严重性对比 |
| --- | --- | --- | --- | --- | --- |
| `XSS-001` 主题/回复正文 Markdown 渲染未启用 safe_mode，存储型 XSS | high | 命中真值 | GT-01, GT-02 | high | 相符 |
| `FILE-001` 附件上传文件名路径穿越，可向 MEDIA_ROOT 任意位置写文件 | high | 误报（踩中已知陷阱） | FP-05 | — | — |
| `ACL-001` XML-RPC 写接口只有认证没有授权：任意注册用户可删除/篡改全站主题 | high | 命中真值 | GT-07, GT-31 | high | 相符 |
| `CSRF-001` 全站缺少 CSRF 防护，删除/重启等敏感操作可用 GET 跨站触发 | medium | 命中真值 | GT-13, GT-14 | medium | 相符 |
| `ACL-002` editPostAJAX 缺少属主校验：任意登录用户可编辑他人帖子 | medium | 命中真值 | GT-06 | high | 相符 |
| `XSS-002` 注册/密码重置 key 参数反射型 XSS（匿名可达） | medium | 命中真值 | GT-04 | medium | 相符 |
| `REDIR-001` logout/login 的 next 与 admin Referer 重定向未校验（开放重定向） | low | 命中真值 | GT-20, GT-21, GT-22 | low | 相符 |
| `CRYPTO-001` 口令使用无迭代 SHA1 + 5 字符弱盐存储 | medium | 命中真值 | GT-18, GT-19 | medium | 相符 |
| `CRYPTO-002` 密码重置/激活 key 熵仅 20 位，可在线爆破接管账号 | medium | 命中真值 | GT-10 | high | 相符 |
| `CONFIG-001` DEBUG=True 且 /ymedia/ 静态目录带目录列举暴露在生产 | medium | 命中真值 | GT-16 | medium | 相符 |
| `CONFIG-002` SECRET_KEY 与数据库口令硬编码提交进仓库 | medium | 命中真值 | GT-17 | medium | 相符 |
| `LAB-001` lab 调试端点未授权暴露：匿名批量改写帖子与测试上传 | low | 命中真值 | GT-15 | low | 相符 |

## 踩中的误报陷阱

- FP-05 上传文件名经 UploadedFile 取 basename，不存在路径穿越

## 漏报

- GT-03 [medium] ylinux_text_filter 把附件名/主题名未转义拼进 HTML（app/ydata/models.py:408, app/ydata/models.py:426, app/ydata/models.py:444）
- GT-05 [low] 上传响应把文件名拼进 <script>（app/ydata/views.py:91, app/ylab/views.py:32）
- GT-08 [medium] 受限目录只在写入时检查 has_access，读取路径不检查（app/ydata/models.py:91, app/wiki/views.py:82, app/wiki/views.py:120）
- GT-09 [low] 编辑主题可把主题移进无权访问的目录（app/ydata/forms.py:109, app/ydata/forms.py:123）
- GT-11 [medium] 重置接口接受字面量 key ALREADY_ACTIVATED（app/account/models.py:383, app/account/models.py:392, app/account/views.py:205）
- GT-12 [medium] 重置 key 不过期、用后不失效（app/account/views.py:217）
- GT-23 [medium] 上传不限制类型，存放在可直接访问的媒体目录（app/ydata/views.py:78）
- GT-24 [low] 匿名联系表单可向任意地址发信（app/home/views.py:43）
- GT-25 [low] 注册/重置/登录可枚举用户（app/account/views.py:79, app/account/views.py:177）
- GT-26 [low] 无暴力破解防护，XML-RPC multicall 放大尝试次数（lib/django_xmlrpc/views.py:155, app/account/views.py:24, app/account/views.py:228）
- GT-27 [low] XML-RPC 请求体（含口令）打印到 stdout（lib/django_xmlrpc/views.py:82, app/ydata/views.py:97, app/ydata/views.py:124）
- GT-28 [low] 会话 cookie 未设 HttpOnly/Secure，凭据走明文 HTTP（app/sessions/middleware.py:37, app/account/views.py:191, app/account/models.py:419）
- GT-29 [low] 后台编辑用户表单暴露口令哈希并可提权为超级用户（app/admin/forms.py:103, app/admin/forms.py:115）
- GT-30 [low] 信任 X-Forwarded-For，并向所有用户展示发帖 IP（app/ydata/util.py:169, templates/wiki/add_post.html:25）
- GT-32 [low] 上传附件不校验主题归属，可挂到任意主题（app/ydata/views.py:46, app/ydata/views.py:72, app/ydata/views.py:86）
