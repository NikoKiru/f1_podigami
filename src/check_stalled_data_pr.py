"""Spot an ``auto/update-data`` PR that is never going to merge on its own.

The update run opening a PR is not the same as the data shipping. At the 2026
Hungarian GP the run was green end to end — guard fired, pipeline ran, PR opened
with auto-merge armed — and the site still stalled ~2h, because a *required
check on the PR* failed for a reason of its own (an unpinned ruff resolved to
0.16.0, whose formatter output changed). ``notify-failure`` only watches the
run, so nothing pinged; the PR just sat BLOCKED while the guard re-fired every
tick. This closes that last silent path by watching the PR itself (#229).

:func:`stall_reason` takes the parsed output of ``gh pr list --json ...`` (no IO,
no network) so it is trivially unit-testable; :func:`main` is the CLI glue that
reads that JSON on stdin and reports to ``$GITHUB_OUTPUT``.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime, timedelta

# How long an open data PR is given to merge itself before it counts as stuck.
# A healthy one squash-merges within ~15min of opening (its required checks are
# the binding constraint), so 45min is 3x headroom while still landing the alert
# within a single cron delivery (GitHub gives us ~1/hour, see CLAUDE.md).
STALL_AFTER = timedelta(minutes=45)

# Check conclusions (CheckRun) and states (StatusContext) that will never turn
# into a pass by themselves. NEUTRAL/SKIPPED are deliberately absent: a skipped
# required check satisfies the branch protection rule.
FAILED = {"ACTION_REQUIRED", "CANCELLED", "ERROR", "FAILURE", "STARTUP_FAILURE", "TIMED_OUT"}


def _parse(timestamp: str) -> datetime | None:
    """Parse an API timestamp (``2026-07-25T20:05:00Z``) as tz-aware UTC."""
    try:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None


def _latest_per_check(rollup: list[dict] | None) -> dict[str, str]:
    """Each check's most recent result, keyed by name.

    The data branch is force-pushed every cycle, which can leave an earlier
    commit's runs in the rollup. Without collapsing to the newest run per name,
    a failure that has since been re-run green would alert forever.
    """
    latest: dict[str, tuple[str, str]] = {}
    for entry in rollup or []:
        name = entry.get("name") or entry.get("context") or "unnamed check"
        result = (entry.get("conclusion") or entry.get("state") or "").upper()
        # ISO-8601 UTC strings sort chronologically.
        when = entry.get("completedAt") or entry.get("startedAt") or ""
        if name not in latest or when >= latest[name][0]:
            latest[name] = (when, result)
    return {name: result for name, (_when, result) in latest.items()}


def stall_reason(prs: list[dict], now: datetime) -> str | None:
    """Why the open ``auto/update-data`` PR will not merge itself, or None.

    ``prs``: parsed ``gh pr list --head auto/update-data --state open --json
    createdAt,mergeStateStatus,autoMergeRequest,statusCheckRollup,...``. At most
    one is ever open (the branch is bot-only and force-pushed).

    Fail-safe, like the other guards: anything unparseable stays quiet rather
    than firing an alert every tick.
    """
    if not prs:
        return None
    pr = prs[0]

    created = _parse(pr.get("createdAt", ""))
    if created is None or now - created < STALL_AFTER:
        return None

    failing = sorted(
        name
        for name, result in _latest_per_check(pr.get("statusCheckRollup")).items()
        if result in FAILED
    )
    if failing:
        return "required checks failing: " + ", ".join(failing)
    if (pr.get("mergeStateStatus") or "").upper() == "DIRTY":
        return "merge conflict with the base branch"
    if not pr.get("autoMergeRequest"):
        return "auto-merge is not armed"
    return (
        f"still open and not merging (mergeStateStatus: {pr.get('mergeStateStatus') or 'UNKNOWN'})"
    )


def main() -> int:  # pragma: no cover - thin CLI glue exercised in CI, not unit tests
    prs = json.load(sys.stdin)
    reason = stall_reason(prs, datetime.now(UTC))
    url = prs[0].get("url", "") if prs else ""

    if reason:
        print(f"stalled data PR: {url} — {reason}")
    else:
        print(f"no stalled data PR ({len(prs)} open)")

    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        # Single-line by construction, but never hand a name that came from the
        # API to the key=value format of $GITHUB_OUTPUT unflattened.
        flat_reason = (reason or "").replace("\n", " ")
        flat_url = url.replace("\n", " ")
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"stalled={'true' if reason else 'false'}\n")
            fh.write(f"reason={flat_reason}\n")
            fh.write(f"pr={flat_url}\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
