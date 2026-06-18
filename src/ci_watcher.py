"""Poll GitHub check runs for a PR's head commit until the required checks
complete, then return a CIResult. Also summarize failures into feedback text
for the fix loop.

Time is injected (time_fn / sleep_fn) so the polling logic is unit-testable
without real waits.
"""

from __future__ import annotations

import time
from typing import Callable, Protocol

from .config import CIRules
from .models import CIConclusion, CIResult


class ChecksProvider(Protocol):
    def get_check_runs(self, ref: str) -> list[dict]: ...


def evaluate_checks(runs: list[dict], required: list[str]) -> CIResult:
    """Decide pass/fail/pending from a snapshot of check runs.

    - If a required check is missing or not completed -> pending.
    - If any considered check concluded non-success -> failed.
    - Else -> passed.
    'required' empty means: consider all reported checks.
    """
    considered = [r for r in runs if not required or r.get("name") in required]

    # Which required checks haven't reported yet?
    reported_names = {r.get("name") for r in runs}
    missing = [name for name in required if name not in reported_names]
    if missing:
        return CIResult(conclusion=CIConclusion.PENDING,
                        summary=f"Waiting for checks: {', '.join(missing)}",
                        checks=runs)

    if not considered:
        # No checks at all yet.
        return CIResult(conclusion=CIConclusion.PENDING,
                        summary="No checks reported yet.", checks=runs)

    incomplete = [r for r in considered if r.get("status") != "completed"]
    if incomplete:
        names = ", ".join(r.get("name", "?") for r in incomplete)
        return CIResult(conclusion=CIConclusion.PENDING,
                        summary=f"Checks still running: {names}", checks=runs)

    failures = [r for r in considered if r.get("conclusion") not in ("success", "neutral", "skipped")]
    if failures:
        return CIResult(conclusion=CIConclusion.FAILED,
                        summary=summarize_failures(failures), checks=runs)

    return CIResult(conclusion=CIConclusion.PASSED, summary="All required checks passed.",
                    checks=runs)


def summarize_failures(failed_checks: list[dict]) -> str:
    lines = ["The following checks failed:"]
    for r in failed_checks:
        lines.append(f"- {r.get('name', '?')}: {r.get('conclusion', 'failure')}")
    lines.append("Inspect the test output, fix the cause, and make the checks pass.")
    return "\n".join(lines)


def wait_for_ci(
    provider: ChecksProvider,
    ref: str,
    rules: CIRules,
    time_fn: Callable[[], float] = time.monotonic,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> CIResult:
    deadline = time_fn() + rules.timeout_seconds
    last = CIResult(conclusion=CIConclusion.PENDING, summary="not started")
    while True:
        runs = provider.get_check_runs(ref)
        last = evaluate_checks(runs, rules.required_checks)
        if last.conclusion in (CIConclusion.PASSED, CIConclusion.FAILED):
            return last
        if time_fn() >= deadline:
            return CIResult(conclusion=CIConclusion.TIMEOUT,
                            summary=f"CI did not complete within {rules.timeout_seconds}s.",
                            checks=runs)
        sleep_fn(rules.poll_interval_seconds)
