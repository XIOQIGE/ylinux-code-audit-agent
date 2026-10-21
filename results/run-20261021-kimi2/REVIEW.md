# 运行 `run-20261021-kimi2` 的评审

用 `audit_agent evaluate` 对照 `eval/ground_truth.json` 生成，只是给 report.md 打分，不改报告本身。

- 上报 13 条：命中真值 12，踩中误报陷阱 1，未匹配 0
- 精确率下限 0.923，召回率 0.5，高危及以上召回 1.0，按严重性加权召回 0.568

## 逐条判定

| 发现 | 报告严重性 | 判定 | 对应真值 / 陷阱 | 真值严重性 | 严重性对比 |
| --- | --- | --- | --- | --- | --- |
| `XSS-001` Markdown 渲染不转义 HTML 且模板用 |safe 输出，导致存储型 XSS | high | 命中真值 | GT-01, GT-02 | high | 相符 |
| `ACCESS-001` editPostAJAX 缺少属主校验，任意登录用户可篡改他人帖子 | high | 命中真值 | GT-06 | high | 相符 |
| `CRYPTO-001` 密码重置激活密钥熵值过低，可在线枚举实现任意账号接管 | critical | 命中真值 | GT-10 | high | 相符 |
| `ACCESS-002` XML-RPC 接口缺少权限/属主校验，普通账号可删除或改写全站内容 | high | 命中真值 | GT-07, GT-31 | high | 相符 |
| `CSRF-001` 全站缺少 CSRF 防护，状态变更接口可被跨站请求触发 | medium | 命中真值 | GT-13 | high | 相符 |
| `ACCESS-003` 维护端点 update_post_profile 无认证，匿名 GET 即可全表改写帖子数据 | medium | 命中真值 | GT-15 | low | 相符 |
| `CONFIG-001` DEBUG=True 硬编码且静态目录开启目录索引，泄露目录结构与调试信息 | medium | 命中真值 | GT-16 | medium | 相符 |
| `CONFIG-002` SECRET_KEY 硬编码进仓库，会话完整性校验可被伪造 | medium | 命中真值 | GT-17 | medium | 相符 |
| `CONFIG-003` 数据库弱口令明文提交进仓库 | low | 命中真值 | GT-17 | medium | 相符 |
| `CRYPTO-002` 口令使用弱哈希（单轮 SHA1 + 5 字符盐）存储 | medium | 命中真值 | GT-18, GT-19 | medium | 相符 |
| `REDIRECT-001` 登录/退出/后台登录存在开放重定向 | low | 命中真值 | GT-20, GT-21 | low | 相符 |
| `DESER-001` 会话数据使用 pickle 反序列化且完整性密钥公开，存在伪造会话风险 | medium | 误报（踩中已知陷阱） | FP-03 | — | — |
| `XSS-002` 附件上传不校验类型，DEBUG 静态服务下可投递同源存储型 XSS | medium | 命中真值 | GT-05, GT-23 | medium | 相符 |

## 踩中的误报陷阱

- FP-03 pickle 会话后端未启用且数据存服务端，不能评为中危以上

## 漏报

- GT-03 [medium] ylinux_text_filter 把附件名/主题名未转义拼进 HTML（app/ydata/models.py:408, app/ydata/models.py:426, app/ydata/models.py:444）
- GT-04 [medium] 注册/重置链接中的 key 原样写进 HttpResponseForbidden（反射型 XSS）（app/account/views.py:102, app/account/views.py:208）
- GT-08 [medium] 受限目录只在写入时检查 has_access，读取路径不检查（app/ydata/models.py:91, app/wiki/views.py:82, app/wiki/views.py:120）
- GT-09 [low] 编辑主题可把主题移进无权访问的目录（app/ydata/forms.py:109, app/ydata/forms.py:123）
- GT-11 [medium] 重置接口接受字面量 key ALREADY_ACTIVATED（app/account/models.py:383, app/account/models.py:392, app/account/views.py:205）
- GT-12 [medium] 重置 key 不过期、用后不失效（app/account/views.py:217）
- GT-14 [medium] 删除/重启/推送等状态变更接受 GET（app/admin/views.py:133, app/admin/views.py:191, app/admin/views.py:256）
- GT-22 [low] 后台登录与 del_* 跳转到 Referer（app/admin/views.py:62, app/admin/views.py:134, app/admin/views.py:192）
- GT-24 [low] 匿名联系表单可向任意地址发信（app/home/views.py:43）
- GT-25 [low] 注册/重置/登录可枚举用户（app/account/views.py:79, app/account/views.py:177）
- GT-26 [low] 无暴力破解防护，XML-RPC multicall 放大尝试次数（lib/django_xmlrpc/views.py:155, app/account/views.py:24, app/account/views.py:228）
- GT-27 [low] XML-RPC 请求体（含口令）打印到 stdout（lib/django_xmlrpc/views.py:82, app/ydata/views.py:97, app/ydata/views.py:124）
- GT-28 [low] 会话 cookie 未设 HttpOnly/Secure，凭据走明文 HTTP（app/sessions/middleware.py:37, app/account/views.py:191, app/account/models.py:419）
- GT-29 [low] 后台编辑用户表单暴露口令哈希并可提权为超级用户（app/admin/forms.py:103, app/admin/forms.py:115）
- GT-30 [low] 信任 X-Forwarded-For，并向所有用户展示发帖 IP（app/ydata/util.py:169, templates/wiki/add_post.html:25）
- GT-32 [low] 上传附件不校验主题归属，可挂到任意主题（app/ydata/views.py:46, app/ydata/views.py:72, app/ydata/views.py:86）
