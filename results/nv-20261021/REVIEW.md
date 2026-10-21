# 运行 `nv-20261021` 的评审

用 `audit_agent evaluate` 对照 `eval/django_nv_truth.json` 生成，只是给 report.md 打分，不改报告本身。

- 上报 22 条：命中真值 22，踩中误报陷阱 0，未匹配 0
- 精确率下限 1.0，召回率 0.958，高危及以上召回 0.923，按严重性加权召回 0.956

## 逐条判定

| 发现 | 报告严重性 | 判定 | 对应真值 / 陷阱 | 真值严重性 | 严重性对比 |
| --- | --- | --- | --- | --- | --- |
| `CMDI-001` 上传文件名进入 os.system 拼接，导致未认证命令注入（RCE） | critical | 命中真值 | NV-01, NV-02, NV-07, NV-08 | critical | 相符 |
| `SQLI-001` upload 视图用 % 格式化拼接 INSERT 语句，未认证 SQL 注入 | critical | 命中真值 | NV-01, NV-07, NV-08 | critical | 相符 |
| `FILE-001` download 视图无鉴权且路径取自数据库，可任意文件读取（路径穿越） | high | 命中真值 | NV-01, NV-08, NV-14, NV-22 | high | 相符 |
| `SESSION-001` 签名 Cookie 会话 + PickleSerializer + 仓库内硬编码 SECRET_KEY 可伪造会话并反序列化 RCE | critical | 命中真值 | NV-03 | critical | 相符 |
| `AUTH-001` 注册表单批量赋值：POST 附加 is_superuser/is_staff 即可匿名创建超级用户 | critical | 命中真值 | NV-04 | critical | 相符 |
| `AUTH-002` profile_by_id 无鉴权 IDOR + csrf_exempt：匿名改任意用户密码实现账户接管 | critical | 命中真值 | NV-02, NV-05, NV-10, NV-24 | critical | 相符 |
| `ACCESS-001` manage_groups POST 分支缺少权限检查：普通用户可提升任意用户到管理员组 | medium | 命中真值 | NV-06 | high | 相符 |
| `ACCESS-002` 项目/任务/笔记的编辑与删除端点无鉴权、无归属校验（匿名 IDOR 写操作） | high | 命中真值 | NV-11, NV-12 | high | 相符 |
| `XSS-003` task_details 页面 task.title/task.text 经 |safe 渲染，存储型 XSS | high | 命中真值 | NV-09（影响说过头：NVFP-11） | high | 相符 |
| `XSS-004` 用户名经 |safe 渲染到全站导航栏，存储型 XSS | medium | 命中真值 | NV-10 | high | 相符 |
| `XSS-002` tm_settings 页面 {{v|safe}} 渲染 request.META：请求头反射 XSS 与环境信息泄露 | medium | 命中真值 | NV-17 | medium | 相符 |
| `XSS-001` search 页面 {{q|safe}} 反射型 XSS | medium | 命中真值 | NV-15 | medium | 相符 |
| `CSRF-001` profile_by_id 改密端点豁免 CSRF，可被跨站请求改密 | medium | 命中真值 | NV-02, NV-05, NV-24 | medium | 相符 |
| `CRYPTO-001` 口令使用 MD5 哈希存储，内置超管口令可被快速离线破解 | medium | 命中真值 | NV-03, NV-19 | medium | 相符 |
| `CONFIG-002` SECRET_KEY 硬编码在仓库中（配置类，独立于会话反序列化记录） | high | 命中真值 | NV-03 | critical | 相符 |
| `CONFIG-001` DEBUG/TEMPLATE_DEBUG 开启并提交进仓库，错误页泄露敏感信息 | medium | 命中真值 | NV-03, NV-18 | medium | 相符 |
| `CONFIG-003` 会话 Cookie 未设 HttpOnly，XSS 可直接窃取会话 | low | 命中真值 | NV-03 | critical | 偏低两级以上 |
| `REDIRECT-001` logout 端点开放重定向 | medium | 命中真值 | NV-16 | medium | 相符 |
| `FILE-002` 上传文件名无校验且可路径穿越写入静态目录 | medium | 命中真值 | NV-01, NV-08, NV-22 | medium | 相符 |
| `COMP-001` 使用已停止维护的 Django 1.8.3，存在已知未修复漏洞 | info | 命中真值 | NV-21 | medium | 偏低两级以上 |
| `RESET-001` 密码重置令牌只有 6 位数字且无速率限制，可暴力枚举接管账户 | high | 命中真值 | NV-20（影响说过头：NVFP-02） | medium | 相符 |
| `ACCESS-003` task_details/profile_view 读侧 IDOR：匿名读取任意任务与用户资料 | medium | 命中真值 | NV-23 | medium | 相符 |

## 漏报

- NV-13 [high] 备注创建/编辑/删除 IDOR（taskManager/views.py:530, taskManager/views.py:554, taskManager/views.py:581）
