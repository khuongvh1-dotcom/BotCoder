"""Block changes that touch files outside the task's allowed paths or inside
forbidden paths. Uses gitignore-style globbing (fnmatch with ** support).

If a task declares no allowed_paths, allow everything except forbidden_paths
(forbidden still wins). Combine with the profile's danger paths at the call site.
"""

from __future__ import annotations

import re
from pydantic import BaseModel


class PathViolation(BaseModel):
    file: str
    reason: str           # "forbidden" | "outside_allowed"
    pattern: str = ""


def _glob_to_regex(pattern: str) -> re.Pattern:
    """Translate a gitignore-ish glob to a regex.

    Supports ** (any depth, incl. zero), * (within a path segment), ? (one char).
    A trailing /** or a bare dir pattern also matches files under it.
    """
    pattern = pattern.strip().replace("\\", "/")
    # A pattern ending in "/" means the whole directory subtree.
    if pattern.endswith("/"):
        pattern = pattern + "**"

    i = 0
    out = ["^"]
    while i < len(pattern):
        c = pattern[i]
        if c == "*":
            if pattern[i:i + 2] == "**":
                # consume "**" and an optional following "/"
                i += 2
                if pattern[i:i + 1] == "/":
                    i += 1
                out.append(".*")
                continue
            out.append("[^/]*")
            i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(c))
            i += 1
    out.append("$")
    return re.compile("".join(out))


def matches(path: str, pattern: str) -> bool:
    path = path.replace("\\", "/")
    if path.startswith("./"):
        path = path[2:]
    rx = _glob_to_regex(pattern)
    if rx.match(path):
        return True
    # Also treat a directory pattern like "dir" or "dir/**" as matching "dir/x".
    if not pattern.endswith("**") and rx.match(path.split("/")[0]):
        return True
    return False


def _matches_any(path: str, patterns: list[str]) -> str | None:
    for p in patterns:
        if matches(path, p):
            return p
    return None


def check(
    changed_files: list[str],
    allowed_paths: list[str],
    forbidden_paths: list[str],
) -> list[PathViolation]:
    violations: list[PathViolation] = []
    for f in changed_files:
        fb = _matches_any(f, forbidden_paths)
        if fb is not None:
            violations.append(PathViolation(file=f, reason="forbidden", pattern=fb))
            continue
        if allowed_paths:
            if _matches_any(f, allowed_paths) is None:
                violations.append(PathViolation(file=f, reason="outside_allowed"))
    return violations
