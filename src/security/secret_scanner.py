"""Scan changed files for likely secrets before committing.

Second line of defense (the first is .gitignore + the company policy telling the
coder never to commit secrets). If any hit is found, the orchestrator blocks the
commit and parks the task as BLOCKED.
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel

# (name, compiled regex). Patterns aim for high precision to avoid false blocks.
_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("anthropic_api_key", re.compile(r"ANTHROPIC_API_KEY\s*=\s*\S+")),
    ("supabase_service_role", re.compile(r"SUPABASE_SERVICE_ROLE_KEY\s*=\s*\S+")),
    ("private_key_block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("github_pat", re.compile(r"\bghp_[A-Za-z0-9]{20,}\b")),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("generic_secret_assign",
     re.compile(r"(?i)\b(secret|token|password|passwd|api_?key)\b\s*[:=]\s*['\"][^'\"]{8,}['\"]")),
]

# Filenames that should never be committed at all.
_FORBIDDEN_NAMES = {".env"}


class SecretHit(BaseModel):
    file: str
    rule: str
    line: int = 0
    snippet: str = ""


def _redact(text: str) -> str:
    if len(text) <= 12:
        return text[:3] + "***"
    return text[:6] + "***" + text[-3:]


def scan_text(text: str, file: str = "") -> list[SecretHit]:
    hits: list[SecretHit] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for rule, rx in _PATTERNS:
            m = rx.search(line)
            if m:
                hits.append(SecretHit(file=file, rule=rule, line=lineno,
                                      snippet=_redact(m.group(0))))
    return hits


def scan(changed_files: list[str], workspace: str | Path = ".") -> list[SecretHit]:
    ws = Path(workspace)
    hits: list[SecretHit] = []
    for rel in changed_files:
        name = Path(rel).name
        if name in _FORBIDDEN_NAMES:
            hits.append(SecretHit(file=rel, rule="forbidden_file", snippet=name))
            continue
        path = ws / rel
        if not path.exists() or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        hits.extend(h.model_copy(update={"file": rel}) for h in scan_text(text, rel))
    return hits
