# ylinux_old 应用安全审计报告

- 目标：`https://github.com/gwind/ylinux_old`
- Commit：`8a7316deec88287d020eca21c38dad921b623ffc`
- 模型：`deepseek-ai/DeepSeek-V3`
- 接口：`https://api.siliconflow.cn/v1`
- 开始：2026-10-20T19:56:10+08:00
- 结束：2026-10-20T19:59:20+08:00
- 结论：确认 7 个问题，最高严重性为 high。

本报告的发现列表来自 Agent 写入并经过引用核对的结构化结果。审计员综述写于复核之前，单条发现的 `status` 以复核之后的状态为准。

## 1. 审计员综述

本次审计发现多个安全风险，包括 DEBUG 模式开启、硬编码敏感信息、弱密码哈希算法、潜在命令注入风险以及未转义的 HTML 输出。这些问题可能导致信息泄露、会话伪造、命令执行和跨站脚本攻击。

## 2. 风险概览

最高风险包括硬编码数据库密码和 SECRET_KEY，以及潜在的命令注入漏洞。这些漏洞可能被攻击者利用，导致数据泄露或系统被控制。

## 3. 统计

- 已确认：7
- 待再确认：0
- 复核否决：0
- 已排除：0
- 阅读过的文件：10
- pattern_scan 次数：1
- search_code 次数：2
- prompt tokens：288286
- completion tokens：4629

## 已确认的问题

### [HIGH] 硬编码数据库密码

- 编号：`CONFIG-002`
- 类别：`config`
- CWE：`CWE-259`
- 置信度：`high`
- 状态：`confirmed`

settings.py 中数据库密码硬编码为 '123456'。

**触发条件。** settings.py 中的数据库配置

**影响。** 攻击者可能直接访问数据库，导致数据泄露或篡改。

**修复。** 使用环境变量或配置文件存储敏感信息。

**证据。**

`settings.py:49-49`

```
'PASSWORD': '123456',
```

### [HIGH] 硬编码 SECRET_KEY

- 编号：`CONFIG-003`
- 类别：`config`
- CWE：`CWE-798`
- 置信度：`high`
- 状态：`confirmed`

settings.py 中 SECRET_KEY 硬编码。

**触发条件。** settings.py 中的 SECRET_KEY 配置

**影响。** 攻击者可能伪造会话或执行其他安全敏感操作。

**修复。** 使用环境变量或配置文件存储 SECRET_KEY。

**证据。**

`settings.py:79-79`

```
SECRET_KEY = 'c#0cz^i$lyr6*b*xe-t@0tqc_c3dnju=+c1lk^k7(r^7lhz$g@'
```

### [HIGH] 弱密码哈希算法

- 编号：`CRYPTO-001`
- 类别：`crypto`
- CWE：`CWE-327`
- 置信度：`high`
- 状态：`confirmed`

account/models.py 中使用 MD5 和 SHA1 进行密码哈希。

**触发条件。** account/models.py 中的密码哈希实现

**影响。** 攻击者可能通过彩虹表或暴力破解获取用户密码。

**修复。** 使用更安全的哈希算法，如 bcrypt 或 PBKDF2。

**证据。**

`app/account/models.py:62-66`

```
if algorithm == 'md5':
        return md5_constructor(salt + raw_password).hexdigest()
    elif algorithm == 'sha1':
        return sha_constructor(salt + raw_password).hexdigest()
    raise ValueError("未知加密算法")
```

### [HIGH] 潜在命令注入风险

- 编号：`INJECTION-001`
- 类别：`injection`
- CWE：`CWE-78`
- 置信度：`high`
- 状态：`confirmed`

admin/views.py 中使用 os.system 执行用户输入的命令，可能导致命令注入。

**触发条件。** admin/views.py 中的命令执行代码

**影响。** 攻击者可能执行任意系统命令，导致系统被控制或数据泄露。

**修复。** 使用安全的 API（如 subprocess）并避免直接拼接用户输入。

**证据。**

`app/admin/views.py:363-363`

```
os.system('killall -u %s' % user)
```

### [MEDIUM] DEBUG 模式开启

- 编号：`CONFIG-001`
- 类别：`config`
- CWE：`CWE-489`
- 置信度：`high`
- 状态：`confirmed`

settings.py 中 DEBUG 设置为 True，可能导致敏感信息泄露。

**触发条件。** settings.py 中的 DEBUG 配置

**影响。** 攻击者可能获取调试信息，包括堆栈跟踪和内部状态。

**修复。** 在生产环境中将 DEBUG 设置为 False。

**证据。**

`settings.py:18-18`

```
DEBUG = True
```

### [MEDIUM] 弱随机盐生成

- 编号：`CRYPTO-002`
- 类别：`crypto`
- CWE：`CWE-330`
- 置信度：`high`
- 状态：`confirmed`

account/models.py 中使用弱随机盐生成机制。

**触发条件。** account/models.py 中的盐生成实现

**影响。** 攻击者可能预测盐值，增加密码破解的可能性。

**修复。** 使用更安全的随机数生成方法，如 secrets 模块。

**证据。**

`app/account/models.py:364-364`

```
salt = sha_constructor(str(random.random())).hexdigest()[:5]
```

### [MEDIUM] 模板中未转义的 HTML 输出

- 编号：`XSS-001`
- 类别：`xss`
- CWE：`CWE-79`
- 置信度：`high`
- 状态：`confirmed`

templates/bbs/topic.html 和 app/wiki/utils.py 中使用 |safe 过滤器输出未转义的 HTML。

**触发条件。** 模板文件中的 |safe 过滤器使用

**影响。** 攻击者可能注入恶意脚本，导致跨站脚本攻击。

**修复。** 避免使用 |safe 过滤器，除非内容完全可信。

**证据。**

`templates/bbs/topic.html:23-23`

```
{{ topic.body_html|safe }}
```

`app/wiki/utils.py:18-18`

```
<p>{{ post.body_html|safe }}</p>
```

## 需要再确认的问题

无。

## 复核员否决、尚未改判的问题

无。

## 已排除的可疑点

无。

## 未完成判断的候选

无。

## 4. 范围

审计覆盖了 settings.py、urls.py、account/models.py、admin/views.py、wiki/utils.py 和 templates/bbs/topic.html 等关键文件。

## 5. 局限

静态审计无法验证运行时行为，部分漏洞可能需要动态测试确认。

## 6. 复核意见

已核对所有高严重性发现（CONFIG-002、CONFIG-003、CRYPTO-001、INJECTION-001），证据支持结论，严重性评估合理。

## 7. 复核缺口

- `G1`（已回应）未验证的 XML-RPC 端点：审计提到“XML-RPC endpoints”但未展开，可能存在远程代码执行风险。
  - 审计员回应：XML-RPC 端点已通过 csrf_exempt 装饰器禁用 CSRF 防护，但未发现直接远程代码执行漏洞的证据。建议进一步动态测试确认其安全性。
- `G2`（已回应）会话管理问题：未检查会话固定或超时设置。
  - 审计员回应：会话管理通过 app/sessions/middleware.py 实现，未发现会话固定或超时设置问题。会话 cookie 的 secure 和 httponly 属性未显式设置，建议补充。
- `G3`（已回应）CSRF 防护缺失：未验证全局 CSRF 防护是否启用。
  - 审计员回应：全局 CSRF 防护未启用，但未发现直接依赖 CSRF 防护的敏感操作。建议在需要 CSRF 防护的端点显式启用。

## 8. 阶段记录

- `recon`：Reviewed settings.py and urls.py to understand the project's configuration, middleware, and routing. Identified DEBUG mode, database credentials, and XML-RPC endpoints.
- `hunt`：Performed pattern_scan to identify potential security issues, including DEBUG mode, hard-coded secrets, SQL injection candidates, weak hashing, open redirects, and XSS vulnerabilities.
- `investigate`：Reviewed code snippets from account/backends.py, account/models.py, account/views.py, admin/views.py, wiki/utils.py, and templates/bbs/topic.html to confirm potential security issues.
- `verify`：Verified findings related to DEBUG mode, hard-coded secrets, weak hashing, command injection, and XSS vulnerabilities.

## 9. 读过的文件

- `settings.py`
- `urls.py`
- `app/account/backends.py`
- `app/account/models.py`
- `app/account/views.py`
- `app/admin/views.py`
- `app/wiki/utils.py`
- `templates/bbs/topic.html`
- `lib/django_xmlrpc/views.py`
- `app/sessions/middleware.py`

## 10. 工具调用序列

完整参数和观察见 `trajectory.md` 与 `trace.jsonl`。顺序是模型每次返回的 tool call，不是脚本写死的。

`list_files` → `read_file` → `read_file` → `pattern_scan` → `set_stage` → `set_stage` → `read_file` → `read_file` → `read_file` → `read_file` → `read_file` → `read_file` → `read_file` → `read_file` → `set_stage` → `upsert_finding` → `upsert_finding` → `upsert_finding` → `upsert_finding` → `upsert_finding` → `upsert_finding` → `upsert_finding` → `upsert_finding` → `upsert_finding` → `upsert_finding` → `set_stage` → `finalize_report` → `search_code` → `finalize_report` → `read_file` → `read_file` → `read_file` → `read_file` → `note_gap` → `note_gap` → `note_gap` → `accept_report` → `read_file` → `read_file` → `search_code` → `resolve_gap` → `resolve_gap` → `resolve_gap` → `finalize_report` → `read_file` → `read_file` → `read_file` → `read_file` → `accept_report`

## 11. 引用核对

共核对 8 条引用，未通过 0 条。
- 通过 `CONFIG-001` `settings.py:18-18`
- 通过 `CONFIG-002` `settings.py:49-49`
- 通过 `CONFIG-003` `settings.py:79-79`
- 通过 `CRYPTO-002` `app/account/models.py:364-364`
- 通过 `XSS-001` `templates/bbs/topic.html:23-23`
- 通过 `XSS-001` `app/wiki/utils.py:18-18`
- 通过 `CRYPTO-001` `app/account/models.py:62-66`
- 通过 `INJECTION-001` `app/admin/views.py:363-363`
