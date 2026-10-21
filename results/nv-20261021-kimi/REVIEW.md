# 运行 `nv-20261021-kimi` 的评审

用 `audit_agent evaluate` 对照 `eval/django_nv_truth.json` 生成，只是给 report.md 打分，不改报告本身。

- 上报 19 条：命中真值 17，踩中误报陷阱 2，未匹配 0
- 精确率下限 0.895，召回率 0.833，高危及以上召回 0.923，按严重性加权召回 0.856

## 逐条判定

| 发现 | 报告严重性 | 判定 | 对应真值 / 陷阱 | 真值严重性 | 严重性对比 |
| --- | --- | --- | --- | --- | --- |
| `RCE-001` 上传文件名拼接进 os.system 导致 shell 命令注入（未授权 RCE） | critical | 命中真值 | NV-01, NV-02, NV-07, NV-08 | critical | 相符 |
| `SQLI-001` upload 视图用字符串格式化拼接原始 SQL，存在 SQL 注入 | high | 命中真值 | NV-01, NV-07, NV-08 | high | 相符 |
| `DESER-001` 硬编码 SECRET_KEY + signed_cookies + PickleSerializer 可伪造会话并反序列化 RCE | critical | 命中真值 | NV-03 | critical | 相符 |
| `AUTHZ-001` profile_by_id 未授权 IDOR：匿名可改任意用户密码（账户接管） | critical | 命中真值 | NV-02, NV-05, NV-10, NV-24 | critical | 相符 |
| `AUTHZ-002` manage_groups POST 分支缺少权限检查，普通用户可提权到 admin_g | high | 命中真值 | NV-06 | high | 相符 |
| `AUTHZ-003` 任务/笔记/项目/文件接口普遍 IDOR：匿名可改删任意数据并下载文件 | high | 命中真值 | NV-09, NV-11, NV-12, NV-14 | high | 相符 |
| `XSS-001` 任务标题/描述 |safe 渲染导致匿名可触发的存储型 XSS | high | 命中真值 | NV-09 | high | 相符 |
| `XSS-002` username 经 |safe 渲染，配合未授权改名构成存储型 XSS | high | 命中真值 | NV-10 | high | 相符 |
| `XSS-003` 搜索参数 q |safe 渲染导致反射型 XSS | medium | 命中真值 | NV-15 | medium | 相符 |
| `XSS-004` settings 视图用 |safe 渲染 request.META：信息泄露 + 请求头反射 XSS | medium | 命中真值 | NV-17 | medium | 相符 |
| `REDIR-001` logout 开放重定向（redirect 参数未校验） | medium | 命中真值 | NV-16 | medium | 相符 |
| `AUTH-001` 弱随机密码重置令牌 + 无速率限制，可暴力枚举重置任意账号口令 | high | 命中真值 | NV-20（影响说过头：NVFP-02） | medium | 相符 |
| `CRYPTO-001` 使用 MD5PasswordHasher 存储口令哈希，且默认账号哈希随仓库公开 | medium | 命中真值 | NV-03, NV-19 | medium | 相符 |
| `CONFIG-001` DEBUG/TEMPLATE_DEBUG 开启且 ALLOWED_HOSTS 为空，错误页泄露配置与堆栈 | medium | 误报（踩中已知陷阱） | NVFP-13 | — | — |
| `INFO-001` 登录接口用户名枚举（错误文案可区分账号是否存在） | low | 命中可选项 | NVO-02 | low | 相符 |
| `CSRF-001` 多个口令相关端点被 csrf_exempt 豁免 CSRF 防护 | low | 误报（踩中已知陷阱） | NVFP-01, NVFP-02 | — | — |
| `AUTHZ-004` 注册表单 mass assignment：匿名可自助注册 is_superuser 超级用户 | critical | 命中真值 | NV-04 | critical | 相符 |
| `FILE-001` 任意文件（含 HTML/JS）落盘 Web 可服务目录并可同源访问 | medium | 命中真值 | NV-01, NV-08, NV-22 | medium | 相符 |
| `AUTH-002` 登录接口无速率限制/锁定，可无限在线爆破口令 | low | 命中可选项 | NVO-02 | low | 相符 |

## 踩中的误报陷阱

- NVFP-01 change_password 虽 csrf_exempt，但必须提交正确旧密码，跨站请求无法改密，CSRF 影响可忽略
- NVFP-02 forgot_password/reset_password 的 csrf_exempt 作用于未认证流程，跨站提交不借用受害者身份，不构成有意义的 CSRF（真实问题是令牌弱，见 NV-20）
- NVFP-13 ALLOWED_HOSTS=[] 在 DEBUG=True 下 Django 1.8 跳过 Host 校验，应用不在邮件或链接中使用 Host，Host 头注入无实际利用面

## 漏报

- NV-13 [high] 备注创建/编辑/删除 IDOR（taskManager/views.py:530, taskManager/views.py:554, taskManager/views.py:581）
- NV-18 [medium] 生产配置提交 DEBUG=True / TEMPLATE_DEBUG=True（taskManager/settings.py:28）
- NV-21 [medium] 使用存在已知漏洞的 Django 1.8.3（requirements.txt:1）
- NV-23 [medium] task_details 未做访问控制，任何人可读取任意任务及其备注（taskManager/views.py:593, taskManager/views.py:610）
