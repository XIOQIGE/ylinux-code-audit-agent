"""Heuristic sink finder.

Matches are candidates for the model, not findings. The model decides whether
to run the scanner at all and which categories to ask for.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from audit_agent.sandbox import Sandbox


@dataclass(frozen=True)
class Rule:
    rule_id: str
    category: str
    pattern: str
    description: str


RULES: tuple[Rule, ...] = (
    Rule("sql-execute-format", "injection", r"(execute|executemany)\s*\([^)\n]*%", "SQL execution built with percent interpolation"),
    Rule("sql-statement-format", "injection", r"\b(SELECT|INSERT|UPDATE|DELETE)\b[^\n]*%[s(]", "SQL text assembled with % interpolation"),
    Rule("sql-format-call", "injection", r"\b(SELECT|INSERT|UPDATE|DELETE)\b[^\n]*\.format\s*\(", "SQL text assembled with str.format"),
    Rule("sql-raw", "injection", r"\.(raw|extra)\s*\(|RawSQL\s*\(", "Django raw SQL or QuerySet.extra"),
    Rule("cmd-os-system", "injection", r"os\.system\s*\(", "os.system call"),
    Rule("cmd-popen", "injection", r"(os\.popen|subprocess\.(Popen|call|run|check_output|check_call|getoutput)|commands\.(getoutput|getstatusoutput))\s*\(", "Process execution API"),
    Rule("cmd-shell-true", "injection", r"shell\s*=\s*True", "subprocess shell=True"),
    Rule("code-eval", "injection", r"(?<![\w.])(eval|exec|execfile)\s*\(", "Dynamic code execution"),
    Rule("pickle-load", "deserialization", r"pickle\.loads?\s*\(|cPickle\.loads?\s*\(", "Pickle deserialization"),
    Rule("yaml-load", "deserialization", r"yaml\.load\s*\(", "yaml.load (unsafe in PyYAML before SafeLoader was the default)"),
    Rule("mark-safe", "xss", r"mark_safe\s*\(", "Django mark_safe"),
    Rule("template-safe", "xss", r"\|\s*safe\b", "Template |safe filter"),
    Rule("autoescape-off", "xss", r"autoescape\s+off", "Template autoescape disabled"),
    Rule("csrf-exempt", "csrf", r"csrf_exempt", "CSRF protection disabled on a view"),
    Rule("debug-true", "config", r"^\s*DEBUG\s*=\s*True\b", "DEBUG enabled"),
    Rule("secret-key", "config", r"^\s*SECRET_KEY\s*=", "Hard-coded SECRET_KEY"),
    Rule("weak-hash", "crypto", r"hashlib\.(md5|sha1)\s*\(|md5\.new\s*\(|(md5_constructor|sha_constructor|sha\.new)\s*\(", "MD5 or SHA1"),
    Rule("db-password", "config", r"""['"]PASSWORD['"]\s*:\s*['"][^'"]+['"]""", "Literal database password"),
    Rule("open-redirect", "redirect", r"HttpResponseRedirect\s*\([^)\n]*(request|REFERER|session|next|previous|redirect)", "Redirect target that may come from request, Referer or session"),
    Rule("redirect-referer", "redirect", r"HTTP_REFERER", "Referer header used (often as a redirect target)"),
    Rule("open-from-request", "file_access", r"open\s*\([^)\n]*request\.(GET|POST|REQUEST|FILES)", "open() using request data"),
    Rule("upload-handling", "file_access", r"\breq(uest)?\.FILES\b", "Uploaded file handling"),
    Rule("insecure-random", "crypto", r"\brandom\.(random|randint|choice)\s*\(", "Non-cryptographic random used (check if it feeds a token, salt or key)"),
    Rule("http-response-format", "xss", r"HttpResponse\s*\([^)\n]*(%|\+|\.format\s*\()", "HttpResponse body assembled from strings"),
    Rule("xmlrpc", "xml", r"xmlrpc|XMLRPC|SimpleXMLRPCServer", "XML-RPC surface"),
)


CATEGORIES = sorted({rule.category for rule in RULES})

# Rules that mark an attack surface rather than a sink. They are shown to the
# model but do not create leads that must be triaged.
SURFACE_RULES = {"xmlrpc"}


@dataclass
class Hit:
    rule_id: str
    category: str
    description: str
    path: str
    line: int
    snippet: str

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "category": self.category,
            "description": self.description,
            "path": self.path,
            "line": self.line,
            "snippet": self.snippet,
        }


def scan(
    sandbox: Sandbox,
    relative: str = ".",
    categories: list[str] | None = None,
    include_vendor: bool = False,
    max_matches: int = 2000,
    per_rule: int = 500,
) -> tuple[list[Hit], bool]:
    selected = [rule for rule in RULES if not categories or rule.category in categories]
    compiled = [(rule, re.compile(rule.pattern)) for rule in selected]
    counts = {rule.rule_id: 0 for rule in selected}
    hits: list[Hit] = []
    for path in sandbox.iter_files(relative, include_vendor=include_vendor, glob="*", max_depth=12):
        if all(counts[rule.rule_id] >= per_rule for rule in selected) or len(hits) >= max_matches:
            break
        try:
            _rel, _encoding, text = sandbox.read_text(sandbox.rel(path))
        except (OSError, UnicodeError, ValueError):
            continue
        rel = sandbox.rel(path)
        for lineno, line in enumerate(text.splitlines(), start=1):
            if len(hits) >= max_matches:
                break
            for rule, pattern in compiled:
                if counts[rule.rule_id] >= per_rule:
                    continue
                if pattern.search(line):
                    counts[rule.rule_id] += 1
                    hits.append(
                        Hit(
                            rule_id=rule.rule_id,
                            category=rule.category,
                            description=rule.description,
                            path=rel,
                            line=lineno,
                            snippet=line.strip()[:240],
                        )
                    )
    truncated = len(hits) >= max_matches and any(count < per_rule for count in counts.values())
    return hits, truncated


def group_hits(hits: list[Hit]) -> list[dict]:
    """Collapse hits to one row per (rule, file) so a full scan stays small."""
    groups: dict[tuple[str, str], dict] = {}
    for hit in hits:
        key = (hit.rule_id, hit.path)
        row = groups.get(key)
        if row is None:
            row = {
                "rule_id": hit.rule_id,
                "category": hit.category,
                "description": hit.description,
                "path": hit.path,
                "lines": [],
                "snippets": [],
            }
            groups[key] = row
        row["lines"].append(hit.line)
        if len(row["snippets"]) < 3:
            row["snippets"].append(f"{hit.line}: {hit.snippet}")
    return list(groups.values())
