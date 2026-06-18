# Sandbox Plan

## TASK 001: Implement add function
Risk: safe
Repo: ai-sandbox
Parallel: true
Depends on:
- none
Conflict group: core
Estimated size: small
Agent type: coder
Allowed paths:
- calc.py
- tests/test_calc.py
Forbidden paths:
- .github/**
- pyproject.toml
Goal: Hoàn thiện hàm add(a, b) trong calc.py để trả về a + b.
Acceptance criteria:
- add(2, 3) == 5
- pytest pass
Test commands:
- pytest
Rollback note: revert branch nếu fail.
