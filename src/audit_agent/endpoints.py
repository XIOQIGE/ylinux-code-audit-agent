"""Django URLconf → view inventory.

Text-based on purpose: the targets include Python 2 code that ``ast`` in
Python 3 cannot parse. The output is a map for the model, not a verdict;
flags are heuristics and every lead they create still needs triage.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from audit_agent.sandbox import Sandbox, SandboxError

ROOT_URLCONF_RE = re.compile(r"""^\s*ROOT_URLCONF\s*=\s*['"]([\w.]+)['"]""", re.M)
PATTERNS_RE = re.compile(r"""\bpatterns\s*\(\s*['"]([\w.]*)['"]""")
ENTRY_RE = re.compile(
    r"""(?:\b(?:url|path|re_path)\s*\(|(?<![\w.])\()\s*r?(['"])(?P<route>.*?)(?<!\\)\1\s*,\s*"""
    r"""(?P<view>include\s*\(\s*['"][\w.]+['"]|include\s*\([^)]*\)|['"][\w.]+['"]|[\w.]+\.as_view\s*\(|[\w.]+(?!\s*\())"""
)
IMPORT_FROM_RE = re.compile(r"^\s*from\s+([\w.]*)\s+import\s+(.+)$", re.M)
IMPORT_RE = re.compile(r"^\s*import\s+([\w.]+)(?:\s+as\s+(\w+))?", re.M)
AUTH_DECORATOR_RE = re.compile(r"login_required|permission_required|user_passes_test|staff_member_required|superuser_required|admin_required")
ROLE_CHECK_RE = re.compile(r"permission_required|user_passes_test|staff_member_required|superuser_required|admin_required|is_superuser|is_staff|has_perm")
AUTH_BODY_RE = re.compile(
    r"is_authenticated|is_anonymous|is_superuser|is_staff|has_perm|PermissionDenied|HttpResponseForbidden|redirect_to_login|login_required"
)
INPUT_RE = re.compile(r"request\.(GET|POST|REQUEST|FILES|COOKIES|META|body|raw_post_data)\b")
METHOD_RE = re.compile(r"request\.method|request\.POST|require_POST|require_http_methods")
WRITE_RE = re.compile(r"\.save\s*\(|\.delete\s*\(|\.create\s*\(|\.update\s*\(|\.set_password\s*\(|os\.(remove|unlink|system)\s*\(|\.write\s*\(")
USER_SCOPE_RE = re.compile(r"request\.user\b")
ID_ROUTE_RE = re.compile(r"\(\?P<(\w*)>|<(?:\w+:)?(\w+)>")


@dataclass
class Endpoint:
    route: str
    view: str
    urlconf: str
    file: str = ""
    line: int = 0
    kind: str = ""
    decorators: list[str] = field(default_factory=list)
    auth: list[str] = field(default_factory=list)
    inputs: list[str] = field(default_factory=list)
    writes: list[int] = field(default_factory=list)
    method_check: bool = False
    user_scoped: bool = False
    flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        row = {"route": self.route, "view": self.view, "urlconf": self.urlconf}
        if self.file:
            row.update(file=self.file, line=self.line, kind=self.kind)
        else:
            row["unresolved"] = True
        for key in ("decorators", "auth", "inputs", "writes", "flags"):
            value = getattr(self, key)
            if value:
                row[key] = value
        if self.file:
            row["method_check"] = self.method_check
            row["user_scoped"] = self.user_scoped
        return row


class _Index:
    def __init__(self, sandbox: Sandbox):
        self.sandbox = sandbox
        self.files = sorted(sandbox.rel(path) for path in sandbox.iter_files(".", True, "*.py", 12))
        self._text: dict[str, str] = {}

    def text(self, rel: str) -> str:
        if rel not in self._text:
            try:
                self._text[rel] = self.sandbox.read_text(rel)[2]
            except (SandboxError, OSError, ValueError):
                self._text[rel] = ""
        return self._text[rel]

    def module_file(self, module: str, near: str = "") -> str:
        """Map a dotted module to a repository file by the longest matching path suffix."""
        if module.startswith("."):
            base = near.rsplit("/", 1)[0] if "/" in near else ""
            module = (base.replace("/", ".") + "." + module.lstrip(".")).strip(".")
        parts = [part for part in module.split(".") if part]
        for start in range(len(parts)):
            stem = "/".join(parts[start:])
            for suffix in (f"{stem}.py", f"{stem}/__init__.py"):
                exact = [path for path in self.files if path == suffix]
                if exact:
                    return exact[0]
                tail = sorted((path for path in self.files if path.endswith("/" + suffix)), key=len)
                if tail:
                    return tail[0]
        return ""

    def imports(self, rel: str) -> dict[str, str]:
        names: dict[str, str] = {}
        text = self.text(rel)
        for module, items in IMPORT_FROM_RE.findall(text):
            for item in items.replace("(", " ").replace(")", " ").replace("\\", " ").split(","):
                words = item.split()
                if not words or words[0] == "*":
                    continue
                alias = words[2] if len(words) >= 3 and words[1] == "as" else words[0]
                names[alias] = f"{module}.{words[0]}".lstrip(".") if not module.startswith(".") else f"{module}.{words[0]}"
        for module, alias in IMPORT_RE.findall(text):
            names[alias or module.split(".")[0]] = module if alias else module.split(".")[0]
        return names


def list_endpoints(sandbox: Sandbox, root_urlconf: str = "", max_depth: int = 6) -> dict:
    index = _Index(sandbox)
    root_file, root_note = _root_urlconf(index, root_urlconf)
    if not root_file:
        return {"root_urlconf": root_urlconf, "error": root_note, "endpoints": [], "unresolved_includes": []}
    endpoints: list[Endpoint] = []
    unresolved: list[dict] = []
    _walk(index, root_file, "", endpoints, unresolved, set(), max_depth)
    for endpoint in endpoints:
        _inspect(index, endpoint)
    return {
        "root_urlconf": root_file,
        "note": root_note,
        "endpoints": endpoints,
        "unresolved_includes": unresolved,
    }


def _root_urlconf(index: _Index, explicit: str) -> tuple[str, str]:
    if explicit:
        if explicit.endswith(".py") and explicit in index.files:
            return explicit, "given path"
        found = index.module_file(explicit)
        return (found, f"resolved {explicit}") if found else ("", f"cannot map {explicit} to a file")
    for rel in index.files:
        if rel.rsplit("/", 1)[-1] != "settings.py":
            continue
        match = ROOT_URLCONF_RE.search(index.text(rel))
        if match:
            found = index.module_file(match.group(1), rel)
            if found:
                return found, f"ROOT_URLCONF={match.group(1)} in {rel}"
    shallow = sorted((rel for rel in index.files if rel.rsplit("/", 1)[-1] == "urls.py"), key=lambda rel: rel.count("/"))
    if shallow:
        return shallow[0], "no ROOT_URLCONF found; using the shallowest urls.py"
    return "", "no ROOT_URLCONF and no urls.py"


def _strip_comments(text: str) -> str:
    return "\n".join("" if line.lstrip().startswith("#") else line for line in text.splitlines())


def _segments(text: str) -> list[tuple[str, int, str]]:
    """(view prefix, offset, text) per patterns() call, or the whole file for list-style urlpatterns."""
    matches = list(PATTERNS_RE.finditer(text))
    if not matches:
        return [("", 0, text)]
    rows = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        rows.append((match.group(1), match.end(), text[match.end() : end]))
    return rows


def _walk(index: _Index, rel: str, prefix: str, out: list, unresolved: list, seen: set, depth: int) -> None:
    if rel in seen or depth < 0:
        return
    seen.add(rel)
    text = _strip_comments(index.text(rel))
    imports = index.imports(rel)
    for view_prefix, offset, segment in _segments(text):
        for match in ENTRY_RE.finditer(segment):
            route = prefix.rstrip("$") + (match.group("route").lstrip("^") if prefix else match.group("route"))
            view = match.group("view").strip()
            line = text.count("\n", 0, offset + match.start()) + 1
            where = f"{rel}:{line}"
            if view.startswith("include"):
                target = re.search(r"""include\s*\(\s*['"]([\w.]+)['"]""", view)
                child = index.module_file(target.group(1), rel) if target else ""
                if child:
                    _walk(index, child, route, out, unresolved, seen, depth - 1)
                else:
                    unresolved.append({"route": route, "include": view, "urlconf": where})
                continue
            dotted = _dotted_view(view, view_prefix, imports)
            out.append(Endpoint(route=route, view=dotted, urlconf=where))


def _dotted_view(view: str, view_prefix: str, imports: dict[str, str]) -> str:
    quoted = view[:1] in "'\""
    view = re.sub(r"\.as_view\s*\($", "", view.strip("'\""))
    if quoted:
        return f"{view_prefix}.{view}" if view_prefix else view
    head, _, rest = view.partition(".")
    if head in imports:
        return imports[head] + (f".{rest}" if rest else "")
    return view


def _inspect(index: _Index, endpoint: Endpoint) -> None:
    module, _, name = endpoint.view.rpartition(".")
    if not module or not name:
        return
    near = endpoint.urlconf.split(":", 1)[0]
    rel = index.module_file(module, near)
    if not rel:
        return
    text = index.text(rel)
    lines = text.splitlines()
    pattern = re.compile(rf"^(\s*)(def|class)\s+{re.escape(name)}\b")
    for i, line in enumerate(lines):
        match = pattern.match(line)
        if not match:
            continue
        indent = len(match.group(1))
        endpoint.file, endpoint.line, endpoint.kind = rel, i + 1, match.group(2)
        j = i - 1
        while j >= 0 and lines[j].strip().startswith("@"):
            endpoint.decorators.insert(0, lines[j].strip()[:120])
            j -= 1
        body: list[tuple[int, str]] = []
        for k in range(i + 1, len(lines)):
            stripped = lines[k].strip()
            if stripped and len(lines[k]) - len(lines[k].lstrip()) <= indent and not stripped.startswith(("#", ")")):
                break
            body.append((k + 1, lines[k]))
        _summarize(endpoint, body)
        return


def _summarize(endpoint: Endpoint, body: list[tuple[int, str]]) -> None:
    text = "\n".join(line for _no, line in body)
    endpoint.auth = sorted({m.group(0) for m in AUTH_DECORATOR_RE.finditer(" ".join(endpoint.decorators))} | set(AUTH_BODY_RE.findall(text)))
    endpoint.inputs = sorted(set(INPUT_RE.findall(text)))
    endpoint.writes = [no for no, line in body if WRITE_RE.search(line) and not line.strip().startswith("#")][:8]
    endpoint.method_check = bool(METHOD_RE.search(text))
    endpoint.user_scoped = bool(USER_SCOPE_RE.search(text))
    exempt = any("csrf_exempt" in item for item in endpoint.decorators)
    takes_id = bool(ID_ROUTE_RE.search(endpoint.route))
    if not endpoint.auth and endpoint.writes:
        endpoint.flags.append("writes_without_auth_check")
    if endpoint.writes and not endpoint.method_check:
        endpoint.flags.append("writes_on_any_method")
    role_checked = any(ROLE_CHECK_RE.search(item) for item in endpoint.auth)
    if takes_id and (endpoint.writes or endpoint.auth) and not role_checked and not endpoint.user_scoped:
        endpoint.flags.append("object_id_without_owner_check")
    if exempt:
        endpoint.flags.append("csrf_exempt")
