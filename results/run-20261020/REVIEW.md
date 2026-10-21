# 运行 `run-20261020` 的评审

用 `audit_agent evaluate` 对照 `eval/ground_truth.json` 生成，只是给 report.md 打分，不改报告本身。

- 上报 7 条：命中真值 6，踩中误报陷阱 1，未匹配 0
- 精确率下限 0.857，召回率 0.188，高危及以上召回 0.5，按严重性加权召回 0.227

## 逐条判定

| 发现 | 报告严重性 | 判定 | 对应真值 / 陷阱 | 真值严重性 | 严重性对比 |
| --- | --- | --- | --- | --- | --- |
| `CONFIG-001` DEBUG 模式开启 | medium | 命中真值 | GT-16 | medium | 相符 |
| `CONFIG-002` 硬编码数据库密码 | high | 命中真值 | GT-17 | medium | 相符 |
| `CONFIG-003` 硬编码 SECRET_KEY | high | 命中真值 | GT-17 | medium | 相符 |
| `CRYPTO-002` 弱随机盐生成 | medium | 命中真值 | GT-10 | high | 相符 |
| `XSS-001` 模板中未转义的 HTML 输出 | medium | 命中真值 | GT-01, GT-02 | high | 相符 |
| `CRYPTO-001` 弱密码哈希算法 | high | 命中真值 | GT-19 | low | 偏高两级以上 |
| `INJECTION-001` 潜在命令注入风险 | high | 误报（踩中已知陷阱） | FP-01 | — | — |

## 踩中的误报陷阱

- FP-01 reboot 里的 os.system 没有请求数据参与，不是命令注入

## 漏报

- GT-03 [medium] ylinux_text_filter 把附件名/主题名未转义拼进 HTML（app/ydata/models.py:408, app/ydata/models.py:426, app/ydata/models.py:444）
- GT-04 [medium] 注册/重置链接中的 key 原样写进 HttpResponseForbidden（反射型 XSS）（app/account/views.py:102, app/account/views.py:208）
- GT-05 [low] 上传响应把文件名拼进 <script>（app/ydata/views.py:91, app/ylab/views.py:32）
- GT-06 [high] editPostAJAX 不校验帖子归属（IDOR）（app/wiki/views.py:447）
- GT-07 [high] XML-RPC 任意认证用户可删除/编辑任意主题乃至全部主题（lib/ylinux_xmlrpc.py:39, lib/ylinux_xmlrpc.py:53, lib/ylinux_xmlrpc.py:66）
- GT-08 [medium] 受限目录只在写入时检查 has_access，读取路径不检查（app/ydata/models.py:91, app/wiki/views.py:82, app/wiki/views.py:120）
- GT-09 [low] 编辑主题可把主题移进无权访问的目录（app/ydata/forms.py:109, app/ydata/forms.py:123）
- GT-11 [medium] 重置接口接受字面量 key ALREADY_ACTIVATED（app/account/models.py:383, app/account/models.py:392, app/account/views.py:205）
- GT-12 [medium] 重置 key 不过期、用后不失效（app/account/views.py:217）
- GT-13 [high] 全站没有 CSRF 中间件（settings.py:98）
- GT-14 [medium] 删除/重启/推送等状态变更接受 GET（app/admin/views.py:133, app/admin/views.py:191, app/admin/views.py:256）
- GT-15 [low] /lab/update_post_profile 匿名批量改写全部帖子（app/ylab/views.py:37）
- GT-18 [medium] 口令哈希为单轮 SHA-1 + 20 位随机盐（app/account/models.py:231）
- GT-20 [medium] 登录后跳转到 next 参数，无同源校验（app/account/views.py:38, app/account/views.py:44）
- GT-21 [low] 注销后跳转到 next 参数（app/account/views.py:58）
- GT-22 [low] 后台登录与 del_* 跳转到 Referer（app/admin/views.py:62, app/admin/views.py:134, app/admin/views.py:192）
- GT-23 [medium] 上传不限制类型，存放在可直接访问的媒体目录（app/ydata/views.py:78）
- GT-24 [low] 匿名联系表单可向任意地址发信（app/home/views.py:43）
- GT-25 [low] 注册/重置/登录可枚举用户（app/account/views.py:79, app/account/views.py:177）
- GT-26 [low] 无暴力破解防护，XML-RPC multicall 放大尝试次数（lib/django_xmlrpc/views.py:155, app/account/views.py:24, app/account/views.py:228）
- GT-27 [low] XML-RPC 请求体（含口令）打印到 stdout（lib/django_xmlrpc/views.py:82, app/ydata/views.py:97, app/ydata/views.py:124）
- GT-28 [low] 会话 cookie 未设 HttpOnly/Secure，凭据走明文 HTTP（app/sessions/middleware.py:37, app/account/views.py:191, app/account/models.py:419）
- GT-29 [low] 后台编辑用户表单暴露口令哈希并可提权为超级用户（app/admin/forms.py:103, app/admin/forms.py:115）
- GT-30 [low] 信任 X-Forwarded-For，并向所有用户展示发帖 IP（app/ydata/util.py:169, templates/wiki/add_post.html:25）
- GT-31 [medium] XML-RPC 认证不检查 is_active，被禁用的账户仍可调用删除接口（lib/ylinux_xmlrpc.py:39, app/account/backends.py:19）
- GT-32 [low] 上传附件不校验主题归属，可挂到任意主题（app/ydata/views.py:46, app/ydata/views.py:72, app/ydata/views.py:86）
