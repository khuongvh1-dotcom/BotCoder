# Specialized subagents (v0.4 stub)

These are placeholders for the v0.4 milestone. The MVP only uses the `coder`
role via `src/dispatcher/sdk_dispatcher.py`. At v0.4 each task's `agent_type`
selects a specialized agent:

- `coder_agent` — implements code changes
- `tester_agent` — writes/runs tests
- `reviewer_agent` — reads the diff and comments (activates `src/reviewers/ai_reviewer.py`)
- `doc_agent` — updates documentation
- `security_agent` — scans for secrets/risk beyond the rule-based scanner
