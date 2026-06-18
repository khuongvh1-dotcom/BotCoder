"""Quick check that Claude auth works for the SDK dispatcher.

Run after putting CLAUDE_CODE_OAUTH_TOKEN (or ANTHROPIC_API_KEY) in .env:

    python scripts/check_auth.py

It sends a one-line prompt and prints Claude's reply, so you know the
subscription token / API key is valid before running the full orchestrator.
"""

from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv


async def _ping() -> str:
    from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

    options = ClaudeAgentOptions(max_turns=1, allowed_tools=[])
    out = ""
    async for message in query(prompt="Reply with exactly: AUTH_OK", options=options):
        if isinstance(message, ResultMessage):
            if message.is_error:
                raise RuntimeError(message.result or "error result")
            out = message.result or out
    return out.strip()


def main() -> int:
    load_dotenv()
    has_oauth = bool(os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"))
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    # No env var is required: the SDK falls back to the Claude Code CLI login.
    print(f"auth: oauth={has_oauth} api_key={has_key} "
          f"(none -> uses Claude Code CLI login / subscription)")
    try:
        reply = asyncio.run(_ping())
    except Exception as exc:
        print(f"AUTH FAILED: {type(exc).__name__}: {exc}")
        return 1
    print(f"Claude replied: {reply!r}")
    print("AUTH OK" if "AUTH_OK" in reply else "Got a reply but unexpected content.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
