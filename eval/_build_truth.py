import json
from pathlib import Path


def L(path, a, b=None):
    return {"path": path, "start_line": a, "end_line": b or a}


ALSO = {
    "GT-05": ["file_access"],
    "GT-06": ["auth"],
    "GT-07": ["xml"],
    "GT-08": ["auth", "sensitive_data"],
    "GT-09": ["auth"],
    "GT-10": ["auth"],
    "GT-11": ["access_control"],
    "GT-14": ["access_control", "other"],
    "GT-15": ["auth", "other"],
    "GT-16": ["sensitive_data"],
    "GT-17": ["config", "crypto"],
    "GT-18": ["auth"],
    "GT-19": ["auth"],
    "GT-23": ["xss"],
    "GT-24": ["auth", "access_control", "injection"],
    "GT-25": ["sensitive_data", "other"],
    "GT-26": ["xml", "other"],
    "GT-27": ["config"],
    "GT-28": ["sensitive_data", "auth"],
    "GT-29": ["sensitive_data", "auth"],
    "GT-30": ["sensitive_data", "auth", "config"],
    "GT-31": ["access_control", "xml"],
    "GT-32": ["file_access"],
    "OPT-07": ["xml"],
    "OPT-08": ["sensitive_data"],
    "OPT-09": ["xml", "other"],
    "OPT-02": ["injection"],
    "OPT-03": ["xml", "sensitive_data"],
    "OPT-04": ["config"],
    "OPT-05": ["crypto"],
}


def I(id, sev, cat, title, *locs):
    item = {"id": id, "severity": sev, "category": cat, "title": title, "locations": list(locs)}
    if id in ALSO:
        item["also_categories"] = ALSO[id]
    return item


issues = [
    I("GT-01", "high", "xss", "主题正文 Markdown 未开 safe_mode，经 |safe 输出（存储型 XSS）",
      L("app/ydata/models.py", 196, 200), L("templates/wiki/topic.html", 54), L("templates/bbs/topic.html", 23),
      L("app/ydata/forms.py", 97, 98), L("app/ydata/forms.py", 126, 127)),
    I("GT-02", "high", "xss", "回帖正文 Markdown 未开 safe_mode，经 |safe / POST_HTML 输出（存储型 XSS）",
      L("app/ydata/models.py", 258, 261), L("app/wiki/utils.py", 18), L("templates/wiki/topic.html", 59),
      L("templates/wiki/post.html", 12), L("templates/wiki/replayAJAX.html", 16), L("templates/wiki/editPostAJAX.html", 19),
      L("templates/bbs/topic.html", 30), L("app/ydata/forms.py", 46)),
    I("GT-03", "medium", "xss", "ylinux_text_filter 把附件名/主题名未转义拼进 HTML",
      L("app/ydata/models.py", 408), L("app/ydata/models.py", 426), L("app/ydata/models.py", 444)),
    I("GT-04", "medium", "xss", "注册/重置链接中的 key 原样写进 HttpResponseForbidden（反射型 XSS）",
      L("app/account/views.py", 102), L("app/account/views.py", 208)),
    I("GT-05", "low", "xss", "上传响应把文件名拼进 <script>",
      L("app/ydata/views.py", 91, 92), L("app/ylab/views.py", 32, 33)),
    I("GT-06", "high", "access_control", "editPostAJAX 不校验帖子归属（IDOR）",
      L("app/wiki/views.py", 447, 460)),
    I("GT-07", "high", "access_control", "XML-RPC 任意认证用户可删除/编辑任意主题乃至全部主题",
      L("lib/ylinux_xmlrpc.py", 39, 45), L("lib/ylinux_xmlrpc.py", 53, 55), L("lib/ylinux_xmlrpc.py", 66),
      L("lib/ylinux_xmlrpc.py", 174, 181), L("lib/ylinux_xmlrpc.py", 199, 205), L("settings.py", 164, 171)),
    I("GT-08", "medium", "access_control", "受限目录只在写入时检查 has_access，读取路径不检查",
      L("app/ydata/models.py", 91, 101), L("app/wiki/views.py", 82, 103), L("app/wiki/views.py", 120, 128),
      L("app/bbs/views.py", 31, 56), L("app/ydata/views.py", 116, 149), L("lib/ylinux_xmlrpc.py", 136), L("lib/ylinux_xmlrpc.py", 149),
      L("app/wiki/views.py", 105, 117), L("app/wiki/views.py", 319, 320), L("app/wiki/views.py", 368, 388), L("lib/ylinux_xmlrpc.py", 161)),
    I("GT-09", "low", "access_control", "编辑主题可把主题移进无权访问的目录",
      L("app/ydata/forms.py", 109), L("app/ydata/forms.py", 123)),
    I("GT-10", "high", "crypto", "激活/重置 key 只有 5 位十六进制随机盐，可暴力枚举",
      L("app/account/models.py", 364, 367), L("app/account/models.py", 427, 430)),
    I("GT-11", "medium", "auth", "重置接口接受字面量 key ALREADY_ACTIVATED",
      L("app/account/models.py", 383), L("app/account/models.py", 392), L("app/account/views.py", 205, 212)),
    I("GT-12", "medium", "auth", "重置 key 不过期、用后不失效",
      L("app/account/views.py", 217, 221)),
    I("GT-13", "high", "csrf", "全站没有 CSRF 中间件",
      L("settings.py", 98, 104)),
    I("GT-14", "medium", "csrf", "删除/重启/推送等状态变更接受 GET",
      L("app/admin/views.py", 133), L("app/admin/views.py", 191), L("app/admin/views.py", 256), L("app/admin/views.py", 353),
      L("app/admin/views.py", 362, 363), L("app/admin/views.py", 410, 427), L("app/admin/views.py", 431, 481),
      L("app/wiki/views.py", 247, 250), L("app/wiki/views.py", 280), L("app/admin/urls.py", 16, 52)),
    I("GT-15", "low", "access_control", "/lab/update_post_profile 匿名批量改写全部帖子",
      L("app/ylab/views.py", 37, 46)),
    I("GT-16", "medium", "config", "DEBUG=True 且 static serve 开启目录列表",
      L("settings.py", 18, 19), L("settings.py", 162), L("urls.py", 59, 62)),
    I("GT-17", "medium", "sensitive_data", "SECRET_KEY 与数据库密码硬编码入库",
      L("settings.py", 79), L("settings.py", 49)),
    I("GT-18", "medium", "crypto", "口令哈希为单轮 SHA-1 + 20 位随机盐",
      L("app/account/models.py", 231, 234)),
    I("GT-19", "low", "crypto", "接受无盐 MD5 旧口令，非常量时间比较",
      L("app/account/models.py", 243, 244), L("app/account/models.py", 76), L("app/account/models.py", 55, 60)),
    I("GT-20", "medium", "redirect", "登录后跳转到 next 参数，无同源校验",
      L("app/account/views.py", 38), L("app/account/views.py", 44)),
    I("GT-21", "low", "redirect", "注销后跳转到 next 参数",
      L("app/account/views.py", 58, 60)),
    I("GT-22", "low", "redirect", "后台登录与 del_* 跳转到 Referer",
      L("app/admin/views.py", 62, 65), L("app/admin/views.py", 134), L("app/admin/views.py", 192),
      L("app/admin/views.py", 257), L("app/admin/views.py", 354)),
    I("GT-23", "medium", "file_access", "上传不限制类型，存放在可直接访问的媒体目录",
      L("app/ydata/views.py", 78, 90)),
    I("GT-24", "low", "other", "匿名联系表单可向任意地址发信",
      L("app/home/views.py", 43, 46)),
    I("GT-25", "low", "auth", "注册/重置/登录可枚举用户",
      L("app/account/views.py", 79, 81), L("app/account/views.py", 177, 180)),
    I("GT-26", "low", "auth", "无暴力破解防护，XML-RPC multicall 放大尝试次数",
      L("lib/django_xmlrpc/views.py", 155), L("app/account/views.py", 24, 40), L("app/account/views.py", 228, 246),
      L("app/admin/views.py", 48, 62), L("lib/ylinux_xmlrpc.py", 39, 45)),
    I("GT-27", "low", "sensitive_data", "XML-RPC 请求体（含口令）打印到 stdout",
      L("lib/django_xmlrpc/views.py", 82, 83), L("app/ydata/views.py", 97), L("app/ydata/views.py", 124)),
    I("GT-28", "low", "config", "会话 cookie 未设 HttpOnly/Secure，凭据走明文 HTTP",
      L("app/sessions/middleware.py", 37, 41), L("app/account/views.py", 191), L("app/account/models.py", 419)),
    I("GT-29", "low", "access_control", "后台编辑用户表单暴露口令哈希并可提权为超级用户",
      L("app/admin/forms.py", 103), L("app/admin/forms.py", 115)),
    I("GT-30", "low", "other", "信任 X-Forwarded-For，并向所有用户展示发帖 IP",
      L("app/ydata/util.py", 169), L("templates/wiki/add_post.html", 25)),
    # Added after the independent cross-check (eval/ground_truth_crosscheck.json), re-read against the source.
    I("GT-31", "medium", "auth", "XML-RPC 认证不检查 is_active，被禁用的账户仍可调用删除接口",
      L("lib/ylinux_xmlrpc.py", 39, 45), L("app/account/backends.py", 19, 25)),
    I("GT-32", "low", "access_control", "上传附件不校验主题归属，可挂到任意主题",
      L("app/ydata/views.py", 46, 50), L("app/ydata/views.py", 72, 75), L("app/ydata/views.py", 86, 88)),
]

# Real but marginal; matching one counts as a true positive, missing one does not hurt recall.
optional = [
    I("OPT-01", "low", "xml", "XML-RPC 解析可能受实体膨胀 DoS 影响（取决于 expat 版本）", L("lib/django_xmlrpc/views.py", 87)),
    I("OPT-02", "low", "xss", "后台推送邮件把主题名、回帖摘要未转义拼进 HTML", L("app/admin/views.py", 444), L("app/admin/views.py", 454), L("app/admin/views.py", 478)),
    I("OPT-03", "info", "other", "GET /xmlrpc/ 匿名列出全部方法签名", L("lib/django_xmlrpc/views.py", 94, 118)),
    I("OPT-04", "info", "sensitive_data", "运维脚本在命令行传 MySQL 口令、打印用户口令",
      L("scripts/back_web.sh", 9), L("scripts/back_web.sh", 27), L("scripts/ylinux-client.py", 197)),
    I("OPT-05", "info", "deserialization", "自定义 pickle 会话后端未启用（SESSION_ENGINE 未设置），且数据存服务端",
      L("app/sessions/backends/base.py", 92, 98), L("app/sessions/models.py", 60, 67)),
    # Proposed by the cross-check; plausible but not re-verified end to end, so they cannot cost recall.
    I("OPT-06", "low", "xss", "重置页把引号本地部分的 email 未转义输出（依赖 Django 1.2 EmailField 正则，未在真实框架中验证）",
      L("app/account/views.py", 213)),
    I("OPT-07", "low", "access_control", "XML-RPC new_topic 不检查目录 has_access", L("lib/ylinux_xmlrpc.py", 199, 205)),
    I("OPT-08", "low", "access_control", "隐藏/回收站主题只在 wiki 目录列表过滤，其他入口照常可读",
      L("app/wiki/views.py", 81, 103), L("app/bbs/views.py", 40), L("app/wiki/views.py", 32, 34), L("lib/ylinux_xmlrpc.py", 149)),
    I("OPT-09", "info", "sensitive_data", "XML-RPC 把异常原文返回给调用方",
      L("lib/ylinux_xmlrpc.py", 140, 141), L("lib/ylinux_xmlrpc.py", 152, 153), L("lib/ylinux_xmlrpc.py", 184, 185)),
]


def T(id, title, *locs, categories=None, cwes=None, min_severity=None):
    trap = {"id": id, "title": title, "locations": list(locs)}
    if categories:
        trap["wrong_categories"] = categories
    if cwes:
        trap["wrong_cwes"] = cwes
    if min_severity:
        trap["wrong_min_severity"] = min_severity
    return trap


traps = [
    T("FP-01", "reboot 里的 os.system 没有请求数据参与，不是命令注入", L("app/admin/views.py", 362, 363), categories=["injection"]),
    T("FP-02", "get_group_permissions 的 % 只拼标识符常量，用户 id 走参数化", L("app/account/backends.py", 43, 57), categories=["injection"]),
    T("FP-03", "pickle 会话后端未启用且数据存服务端，不能评为中危以上", L("app/sessions/backends/base.py", 92, 98),
      L("app/sessions/models.py", 60, 67), min_severity="medium"),
    T("FP-04", "login() 已 cycle_key，会话固定已处理", L("app/account/__init__.py", 66, 73)),
    T("FP-05", "上传文件名经 UploadedFile 取 basename，不存在路径穿越", L("app/ydata/views.py", 78), cwes=["CWE-22", "CWE-23", "CWE-73"]),
    T("FP-06", "AddPostForm 附件文件名由整数生成", L("app/ydata/forms.py", 62, 64)),
    T("FP-07", "XML-RPC new_media 因 settings 未导入而不可用", L("lib/ylinux_xmlrpc.py", 105, 127), min_severity="medium"),
    T("FP-08", "未注册的 Blogger API 函数不可达", L("lib/ylinux_xmlrpc.py", 218, 251)),
    T("FP-09", "handle_xmlrpc 的 csrf_exempt 不是额外问题", L("lib/django_xmlrpc/views.py", 73)),
    T("FP-10", "test_xmlrpc 未注册", L("lib/django_xmlrpc/views.py", 68, 71)),
    T("FP-12", "replayAJAX 的 ajaxFunc 来自 \\d+ 且自动转义", L("templates/wiki/replayAJAX.html", 25), categories=["xss"]),
    T("FP-15", "Feed 内容由 feedgenerator 转义", L("app/wiki/views.py", 295, 320), categories=["xss"]),
    T("FP-17", "manage_topic / del_post 有归属校验", L("app/wiki/views.py", 240, 246), L("app/wiki/views.py", 275, 279), categories=["access_control"]),
    T("FP-18", "AddTopicForm.save 使用 URL 里的 catalog", L("app/ydata/forms.py", 91), categories=["access_control"]),
    T("FP-19", "remove_attachment 不删除任何东西", L("app/ydata/views.py", 109, 114), categories=["access_control", "file_access"]),
    T("FP-20", "static.serve 会规范化路径，不存在穿越", L("urls.py", 59, 62), cwes=["CWE-22", "CWE-23"]),
    T("FP-21", "account/tokens.py 没有任何 URL 使用", L("app/account/tokens.py", 1, 66)),
    T("FP-22", "_CheckLogin 只拼同站路径", L("app/account/decorators.py", 80, 82), categories=["redirect"]),
]

truth = {
    "target": "https://github.com/gwind/ylinux_old",
    "commit": "8a7316deec88287d020eca21c38dad921b623ffc",
    "notes": "由开发助手（Claude，独立于被测 Agent 的会话）逐条打开源码标注，再由另一个独立子代理盲审交叉核对（见 ground_truth_crosscheck.json），"
             "未经人类安全工程师复核。issues 计入召回；optional 命中算真阳性但漏报不扣分；false_positive_traps 是已知会被误判的位置，"
             "按精确行（不加容差）匹配，满足 wrong_* 任一条件即判为误报。SESSION_ENGINE 未设置，生产 fcgi 读取仓库外的 ylinux.ysettings。",
    "issues": issues,
    "optional": optional,
    "false_positive_traps": traps,
}

out = Path(__file__).with_name("ground_truth.json")
out.write_text(json.dumps(truth, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"wrote {out} issues={len(issues)} optional={len(optional)} traps={len(traps)}")
