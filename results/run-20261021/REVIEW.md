# 运行 `run-20261021` 的评审

用 `audit_agent evaluate` 对照 `eval/ground_truth.json` 生成，只是给 report.md 打分，不改报告本身。

- 上报 15 条：命中真值 15，踩中误报陷阱 0，未匹配 0
- 精确率下限 1.0，召回率 0.688，高危及以上召回 1.0，按严重性加权召回 0.727

## 逐条判定

| 发现 | 报告严重性 | 判定 | 对应真值 / 陷阱 | 真值严重性 | 严重性对比 |
| --- | --- | --- | --- | --- | --- |
| `XSS-001` Markdown 渲染未开 safe_mode，主题/回复内容可注入原始 HTML 造成全站存储型 XSS | high | 命中真值 | GT-01, GT-02 | high | 相符 |
| `XSS-002` 注册/重置密码错误页把 URL 中的 key 未转义拼接进 HTML，反射型 XSS | medium | 命中真值 | GT-04 | medium | 相符 |
| `REDIRECT-001` 登录/退出/后台登录处基于 next 与 Referer 的开放重定向 | low | 命中真值 | GT-20, GT-21, GT-22 | low | 相符 |
| `CRYPTO-001` SECRET_KEY 硬编码入库，会话防篡改校验与重置令牌失去保密性 | high | 命中真值 | GT-17（影响说过头：FP-03） | medium | 相符 |
| `CRYPTO-002` 弱口令哈希：单轮 SHA1/MD5 + 弱随机盐 | medium | 命中真值 | GT-18, GT-19 | medium | 相符 |
| `CRYPTO-003` 激活/重置 key 弱熵（20 bit 盐）可暴力枚举导致账户接管 | high | 命中真值 | GT-10 | high | 相符 |
| `CSRF-001` 全站未启用 CSRF 防护，后台删除等写操作可被跨站伪造 | medium | 命中真值 | GT-13, GT-14 | medium | 相符 |
| `CONFIG-001` DEBUG=True 提交进配置，且 MEDIA_ROOT 开启目录浏览 | medium | 命中真值 | GT-16 | medium | 相符 |
| `CONFIG-002` 数据库口令明文弱口令提交进仓库 | low | 命中真值 | GT-17 | medium | 相符 |
| `ACCESS-001` editPostAJAX 缺少帖子归属校验，任意登录用户可篡改他人帖子 | medium | 命中真值 | GT-06 | high | 相符 |
| `FILE-001` 上传文件名未清洗：头注入/JS 注入风险，XML-RPC 可投放任意内容到媒体目录 | low | 命中真值 | GT-05, GT-23, GT-32 | low | 相符 |
| `ACCESS-002` XML-RPC 删除/编辑接口缺少对象级授权，任意用户可删改全站内容 | medium | 命中真值 | GT-07, GT-31 | medium | 相符 |
| `ACCESS-003` update_post_profile 维护端点无鉴权，匿名可触发全表重写 | low | 命中真值 | GT-15 | low | 相符 |
| `COOKIE-001` 会话 Cookie 未设置 HttpOnly/Secure，XSS 可直接窃取会话 | low | 命中真值 | GT-28 | low | 相符 |
| `AUTH-001` 所有认证入口缺少速率限制/失败锁定，口令可在线爆破 | low | 命中真值 | GT-26, GT-31 | low | 相符 |

## 漏报

- GT-03 [medium] ylinux_text_filter 把附件名/主题名未转义拼进 HTML（app/ydata/models.py:408, app/ydata/models.py:426, app/ydata/models.py:444）
- GT-08 [medium] 受限目录只在写入时检查 has_access，读取路径不检查（app/ydata/models.py:91, app/wiki/views.py:82, app/wiki/views.py:120）
- GT-09 [low] 编辑主题可把主题移进无权访问的目录（app/ydata/forms.py:109, app/ydata/forms.py:123）
- GT-11 [medium] 重置接口接受字面量 key ALREADY_ACTIVATED（app/account/models.py:383, app/account/models.py:392, app/account/views.py:205）
- GT-12 [medium] 重置 key 不过期、用后不失效（app/account/views.py:217）
- GT-24 [low] 匿名联系表单可向任意地址发信（app/home/views.py:43）
- GT-25 [low] 注册/重置/登录可枚举用户（app/account/views.py:79, app/account/views.py:177）
- GT-27 [low] XML-RPC 请求体（含口令）打印到 stdout（lib/django_xmlrpc/views.py:82, app/ydata/views.py:97, app/ydata/views.py:124）
- GT-29 [low] 后台编辑用户表单暴露口令哈希并可提权为超级用户（app/admin/forms.py:103, app/admin/forms.py:115）
- GT-30 [low] 信任 X-Forwarded-For，并向所有用户展示发帖 IP（app/ydata/util.py:169, templates/wiki/add_post.html:25）
