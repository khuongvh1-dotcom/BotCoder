# AI Dev Orchestrator

An **AI-first development pipeline**. A local Python bot ("Orchestrator") drives Claude
(the "Coder") to implement work plan-by-plan, using **GitHub Issues** as the task queue,
**GitHub PRs** as results, and **GitHub Actions CI** as the quality gate.

> Philosophy: **AI writes code · the bot orchestrates the process · CI checks technically ·
> policy + a human approve risky areas.** This is *not* "100% autonomous AI" / blind auto-merge.

## Flow (MVP v0.1.1)

```
plan.md → classify risk → create Issue → Claude codes → path/secret guard
        → open PR → read CI → (fix loop on failure) → stop at HUMAN_REVIEW
```

No auto-merge, no parallelism, no UI yet. State lives in `state.json` (atomic, resumable).

## Layout

- `src/` — orchestrator code (see `src/main.py` for the loop).
- `projects/*.yaml` — per-repo profiles (commands, danger paths, context file).
- `config/rules.yaml` — CI gate, fix-loop, budget, execution mode, risk rules.
- `company/AI_COMPANY_POLICY.md` — company-wide policy prepended to every dispatch prompt.
- `plans/plan.md` — input plan (structured task format).
- `tasks/` — task files generated from the plan.
- `workspace/task-NNN/` — isolated checkout per task.
- `runs/<date>/task-NNN/` — audit trail (prompt, summary, diff, CI result, decision).

## Setup

```bash
# Python 3.10+ required
pip install -e .[dev]
gh auth login            # or set GITHUB_TOKEN in .env

# Claude auth — pick ONE (see .env.example):
#  A) Pro/Max plan: if the Claude Code CLI is already logged in, the SDK
#     inherits that session — no env var needed.
#  B) Pro/Max for CI/another machine: `claude setup-token` -> CLAUDE_CODE_OAUTH_TOKEN
#  C) Pay-as-you-go: ANTHROPIC_API_KEY in .env

cp .env.example .env     # fill in only if you use B or C
python scripts/check_auth.py   # verify Claude auth works
```

> Pro/Max users: an existing `claude` CLI login is enough; usage counts against
> your plan, not API credits. Precedence: `ANTHROPIC_API_KEY` >
> `CLAUDE_CODE_OAUTH_TOKEN` > CLI login.

## Run

After `pip install -e .` the `runbot` command is available (shorthand for
`python -m src.main`):

```bash
# run <path>: a local repo dir, a GitHub repo (owner/name), or a profile yaml
runbot run projects/sandbox.yaml --plan plans/plan.md
runbot run owner/my-app          # auto-create profile if missing
runbot help                      # show all commands
```

## Documentation

Full docs in [`docs/`](docs/README.md):
architecture, modules, configuration, state/data, development, roadmap, decision log.

## Roadmap

- **v0.1.1 (current)** — 1 task sequential, 1 plan, 1 sandbox repo. **Done, e2e verified.**
- **v0.2** — multiple plans (`plan_loader`), state v2, cloud dispatch via GitHub Action + cron.
- **v0.3** — safe parallelism (worker pool, scheduler, dependency graph, path/conflict locks).
- **v0.4** — specialized subagents (coder/tester/reviewer/doc/security).

See [docs/06-roadmap.md](docs/06-roadmap.md) for extension points.
