# 关键决策

从 `trace.jsonl` 自动抽取。完整上下文见 `trajectory.md`。

## 门禁

- auditor step 42 `finalize_report` 通过
- critic step 32 `accept_report` 通过
- auditor step 6 `finalize_report` 通过
- critic step 4 `accept_report` 通过

## 发现的写入被拒与改判

- auditor step 32 `XSS-002` 写入被拒：evidence quote did not match the file
- auditor step 37 `ACCESS-002` 写入被拒：evidence quote did not match the file
- auditor step 38 `ACCESS-002` 写入被拒：evidence quote did not match the file

## 复核

- critic step 28 `XSS-001` 同意。最弱一环：（未填）
- critic step 28 `XSS-002` 同意。最弱一环：（未填）
- critic step 28 `REDIRECT-001` 复核被拒：read_file each evidence location with at least 10 lines of context on both sides before judging it
- critic step 28 `CRYPTO-001` 复核被拒：read_file each evidence location with at least 10 lines of context on both sides before judging it
- critic step 28 `CRYPTO-002` 同意。最弱一环：（未填）
- critic step 28 `CRYPTO-003` 复核被拒：read_file each evidence location with at least 10 lines of context on both sides before judging it
- critic step 28 `CSRF-001` 同意。最弱一环：（未填）
- critic step 28 `CONFIG-001` 同意。最弱一环：（未填）
- critic step 28 `CONFIG-002` 复核被拒：read_file each evidence location with at least 10 lines of context on both sides before judging it
- critic step 28 `ACCESS-001` 同意。最弱一环：（未填）
- critic step 28 `FILE-001` 同意。最弱一环：（未填）
- critic step 28 `ACCESS-002` 复核被拒：read_file each evidence location with at least 10 lines of context on both sides before judging it
- critic step 28 `ACCESS-003` 同意。最弱一环：（未填）
- critic step 30 `REDIRECT-001` 同意。最弱一环：（未填）
- critic step 30 `CRYPTO-001` 同意。最弱一环：（未填）
- critic step 30 `CRYPTO-003` 同意。最弱一环：（未填）
- critic step 30 `CONFIG-002` 同意。最弱一环：（未填）
- critic step 30 `ACCESS-002` 同意。最弱一环：（未填）
- critic step 3 `COOKIE-001` 同意。最弱一环：（未填）
- critic step 3 `AUTH-001` 同意。最弱一环：（未填）

## 缺口

- critic step 31 `note_gap` G1：会话 Cookie 未设置 HttpOnly/Secure 标志：app/sessions/middleware.py:37-41 的 set_cookie 未传 httponly，且未启用 SESSION_COOKIE_SECURE。在 XSS-001（已确认的全站存储型 XSS）成立的前提下，攻击脚本可直接读取 document.cookie 窃取会话（含管理员会话），显著放大影响面。建议审计员复核该加固缺失，或至少在 XSS-001 的 impact 中计入 Cookie 可直接窃取的后果。
- critic step 31 `note_gap` G2：所有认证入口缺少速率限制/失败锁定：account/views.py 的 login、ajax_login，app/admin/views.py:48-70 的 admin login，以及 lib/ylinux_xmlrpc.py:39-45 的 has_auth 均允许无限次口令尝试。结合 CRYPTO-002 的单轮 SHA1 弱哈希，攻击者可在短时间内在线爆破普通用户乃至管理员口令，属未覆盖的认证滥用问题，建议补一条 low/medium 发现。
- auditor step 3 `resolve_gap` G1：已复核 app/sessions/middleware.py:37-41：set_cookie 未传 httponly（Django 1.3 默认 False），且 settings.py 未启用 SESSION_COOKIE_SECURE。新增 finding COOKIE-001（sensitive_data，CWE-1004，low，confirmed），说明该缺失使 XSS-001 的脚本可直接读取 document.cookie 窃取会话；XSS-001 的 impact 原本已计入会话窃取后果。（被拒：search_code or read_file the implementation behind this gap before resolving it; do not answer from framework defaults）
- auditor step 3 `resolve_gap` G2：已复核 account/views.py login（26-40）、ajax_login（233-246）、admin/views.py login（51-62）与 lib/ylinux_xmlrpc.py has_auth（39-45）：均无失败计数/锁定/限速。新增 finding AUTH-001（auth，CWE-307，low，confirmed），并说明与 CRYPTO-002 弱哈希组合后在线爆破弱口令接管账户/后台的实际影响。（被拒：search_code or read_file the implementation behind this gap before resolving it; do not answer from framework defaults）
- auditor step 5 `resolve_gap` G1：重新读 app/sessions/middleware.py:37-41：set_cookie 仅传 max_age/expires/domain/path/secure，未传 httponly；search_code 全仓库无 SESSION_COOKIE_SECURE/SESSION_COOKIE_HTTPONLY 或 httponly 配置。已新增 finding COOKIE-001（CWE-1004，low，confirmed）说明该缺失使 XSS-001 脚本可直接读取 document.cookie 窃取会话，且 XSS-001 impact 已计入会话窃取后果。
- auditor step 5 `resolve_gap` G2：重读三个登录实现（account/views.py:26-40、admin/views.py:51-62、lib/ylinux_xmlrpc.py:39-45）并 search_code 全仓库无 lock/throttle/rate_limit/attempt 计数逻辑，确认所有认证入口无任何失败锁定或限速。已新增 finding AUTH-001（CWE-307，low，confirmed），说明与 CRYPTO-002 弱哈希组合后在线爆破弱口令接管账户/后台的影响。

## 判为无害的扫描线索

- auditor step 40 L4 判为无害：SQL 仅用 % 拼接经 quote_name 的固定表/列名，用户值走 cursor.execute(sql, [user_obj.id]) 参数列表，不构成注入。
- auditor step 40 L11, L12 判为无害：os.popen('whoami') 与 os.system('killall -u %s' % user) 中的 user 取自 whoami 输出（服务进程身份），不是请求数据，无命令注入；仅管理员权限可调用，且是固定命令。
- auditor step 40 L14 判为无害：robots 响应为固定字符串，无用户输入。
- auditor step 40 L21 判为无害：sha1 仅用于附件去重哈希，非安全用途。
- auditor step 40 L22 判为无害：`current` 是 datetime.now() 的 repr，非用户输入，拼接固定 JS 无注入。
- auditor step 40 L24 判为无害：XML-RPC 方法凭据随每次调用在请求体内传递，不依赖 Cookie 会话，csrf_exempt 无 CSRF 风险；站点整体 CSRF 缺失已由 CSRF-001 覆盖。
