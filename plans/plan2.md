# Sandbox Plan 2

## TASK 002: Implement subtract function
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
Goal: Thêm hàm subtract(a, b) vào calc.py trả về a - b. Giữ nguyên hàm add đã có.
Acceptance criteria:
- subtract(5, 3) == 2
- add(2, 3) == 5 (không phá hàm cũ)
- pytest pass
Test commands:
- pytest
Rollback note: revert branch nếu fail.
