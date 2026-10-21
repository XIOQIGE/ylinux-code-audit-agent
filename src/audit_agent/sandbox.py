"""Read-only access to the target repository.

The audit model can ask for any relative path. This module is the boundary
that keeps those paths inside the checkout and refuses to execute anything.
"""

from __future__ import annotations

import os
import re
from fnmatch import fnmatch
from pathlib import Path

# Directory names treated as static assets or bundled third-party code. Extra
# target-specific prefixes come from Sandbox(vendor=...) / AUDIT_VENDOR_DIRS.
VENDOR_DIR_NAMES = {"static", "staticfiles", "assets", "vendor", "third_party", "thirdparty", "bower_components", "site-packages"}
SKIP_DIRS = {".git", "__pycache__", ".svn", ".hg", "node_modules"}
TEXT_SUFFIXES = {
    "",
    ".py",
    ".html",
    ".htm",
    ".txt",
    ".js",
    ".css",
    ".sh",
    ".xml",
    ".json",
    ".md",
    ".rst",
    ".ini",
    ".cfg",
    ".yml",
    ".yaml",
    ".toml",
    ".fcgi",
    ".htaccess",
}
MAX_FILE_BYTES = 1_500_000


class SandboxError(ValueError):
    """Raised when a tool asks for something outside the repository."""


class Sandbox:
    def __init__(self, root: Path, vendor: tuple[str, ...] | list[str] = ()):
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise SandboxError(f"target root does not exist: {self.root}")
        self.vendor_prefixes = tuple(item.strip().strip("/") + "/" for item in vendor if item.strip())

    def resolve(self, relative: str | None) -> Path:
        raw = (relative or ".").strip().replace("\\", "/")
        if raw in {"", "."}:
            return self.root
        path = Path(raw)
        candidate = path.resolve() if path.is_absolute() else (self.root / raw).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise SandboxError("path escapes the target repository") from exc
        return candidate

    def rel(self, path: Path) -> str:
        return path.resolve().relative_to(self.root).as_posix()

    def is_vendor(self, relative: str, is_dir: bool = False) -> bool:
        posix = relative.replace("\\", "/").strip("/")
        if posix.startswith("./"):
            posix = posix[2:]
        if any(posix == prefix.rstrip("/") or posix.startswith(prefix) for prefix in self.vendor_prefixes):
            return True
        parts = posix.split("/")
        dirs = parts if is_dir else parts[:-1]
        return any(part.lower() in VENDOR_DIR_NAMES or part.lower().endswith("media") for part in dirs)

    def vendor_description(self) -> str:
        extra = ", ".join(prefix.rstrip("/") for prefix in self.vendor_prefixes)
        base = "directories named " + "/".join(sorted(VENDOR_DIR_NAMES)) + " or ending in 'media'"
        return base + (f", plus {extra}" if extra else "")

    def read_text(self, relative: str) -> tuple[str, str, str]:
        """Return (relative_posix, encoding, text)."""
        path = self.resolve(relative)
        if not path.is_file():
            raise SandboxError(f"not a file: {relative}")
        size = path.stat().st_size
        if size > MAX_FILE_BYTES:
            raise SandboxError(f"file is too large to read ({size} bytes): {relative}")
        data = path.read_bytes()
        encoding = _decode_encoding(data)
        text = data.decode(encoding)
        return self.rel(path), encoding, text

    def read_window(self, relative: str, start: int, end: int) -> dict:
        rel, encoding, text = self.read_text(relative)
        lines = text.splitlines()
        total = len(lines)
        if total == 0:
            return {
                "path": rel,
                "encoding": encoding,
                "total_lines": 0,
                "start_line": 1,
                "end_line": 0,
                "text": "",
            }
        start = max(1, start)
        end = min(total, end)
        if end < start:
            raise SandboxError(f"empty line range {start}-{end} (file has {total} lines)")
        selected = lines[start - 1 : end]
        numbered = "\n".join(f"{lineno}| {line}" for lineno, line in enumerate(selected, start=start))
        return {
            "path": rel,
            "encoding": encoding,
            "total_lines": total,
            "start_line": start,
            "end_line": end,
            "text": numbered,
        }

    def iter_files(self, relative: str, include_vendor: bool, glob: str, max_depth: int):
        base = self.resolve(relative)
        if base.is_file():
            rel = self.rel(base)
            if _glob_ok(rel, glob) and (include_vendor or not self.is_vendor(rel)):
                yield base
            return
        base_depth = len(base.relative_to(self.root).parts) if base != self.root else 0
        for dirpath, dirnames, filenames in os.walk(base):
            current = Path(dirpath)
            rel_dir = self.rel(current) if current != self.root else ""
            depth = 0 if not rel_dir else len(Path(rel_dir).parts)
            if depth - base_depth > max_depth:
                dirnames[:] = []
                continue
            dirnames[:] = [
                name
                for name in dirnames
                if name not in SKIP_DIRS and (include_vendor or not self.is_vendor(f"{rel_dir}/{name}".strip("/"), is_dir=True))
            ]
            for name in filenames:
                path = current / name
                rel = self.rel(path)
                if not include_vendor and self.is_vendor(rel):
                    continue
                if not _glob_ok(rel, glob):
                    continue
                if ".min.js" in name or name.endswith(".min.css"):
                    continue
                if glob in {"", "*"} and path.suffix.lower() not in TEXT_SUFFIXES:
                    continue
                try:
                    if path.stat().st_size > MAX_FILE_BYTES:
                        continue
                except OSError:
                    continue
                yield path


def _glob_ok(relative: str, glob: str) -> bool:
    name = Path(relative).name
    if glob and glob != "*":
        return fnmatch(name, glob) or fnmatch(relative, glob)
    return True


def _decode_encoding(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            data.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    return "latin-1"


_PREFIX = re.compile(r"^\s*\d+\|\s?")


def strip_line_prefix(quote: str) -> str:
    """Drop the `12| ` prefix added by read_window, if the model copied it."""
    return "\n".join(_PREFIX.sub("", line) for line in quote.replace("\r\n", "\n").split("\n"))
