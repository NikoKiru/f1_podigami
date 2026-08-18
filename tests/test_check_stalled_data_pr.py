"""Unit tests for the stalled-data-PR watchdog (src/check_stalled_data_pr.py).

The 2026-07-25 Hungary incident: the update run was fully green, but the PR it
opened sat BLOCKED for ~2h on a required check that failed for its own reasons
(an unpinned ruff picked up 0.16.0). ``notify-failure`` only fires when the
*run* fails, so nothing pinged. These lock in the rule that catches it (#229).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from check_stalled_data_pr import STALL_AFTER, stall_reason

NOW = datetime(2026, 7, 25, 22, 0, tzinfo=UTC)


def check(name: str, conclusion: str, completed: str = "2026-07-25T20:10:00Z") -> dict:
    return {
        "__typename": "CheckRun",
        "name": name,
        "status": "COMPLETED",
        "conclusion": conclusion,
        "startedAt": completed,
        "completedAt": completed,
    }


GREEN = [check("Lint & format", "SUCCESS"), check("Test (3.12)", "SUCCESS")]


def open_pr(
    *,
    minutes_old: int = 120,
    checks: list[dict] | None = None,
    merge_state: str = "BLOCKED",
    auto_merge: bool = True,
) -> list[dict]:
    """One open auto/update-data PR, shaped like `gh pr list --json ...` output."""
    created = NOW - timedelta(minutes=minutes_old)
    return [
        {
            "number": 226,
            "url": "https://github.com/NikoKiru/f1podigami/pull/226",
            "createdAt": created.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "mergeStateStatus": merge_state,
            "autoMergeRequest": {"enabledAt": "2026-07-25T20:05:00Z"} if auto_merge else None,
            "statusCheckRollup": list(GREEN if checks is None else checks),
        }
    ]


def test_no_open_data_pr_is_not_a_stall():
    assert stall_reason([], NOW) is None


def test_a_fresh_pr_is_left_alone_to_go_green():
    """Checks take minutes; a young PR is the normal state, not an alert."""
    young = int(STALL_AFTER.total_seconds() // 60) - 5
    assert (
        stall_reason(open_pr(minutes_old=young, checks=[check("Lint & format", "FAILURE")]), NOW)
        is None
    )


def test_failing_required_check_is_named():
    reason = stall_reason(
        open_pr(checks=[check("Lint & format", "FAILURE"), check("Test (3.12)", "SUCCESS")]),
        NOW,
    )
    assert reason and "Lint & format" in reason
    assert "Test (3.12)" not in reason


def test_a_rerun_that_went_green_clears_the_earlier_failure():
    """A force-push leaves older runs in the rollup; only the latest one counts."""
    reason = stall_reason(
        open_pr(
            merge_state="CLEAN",
            checks=[
                check("Lint & format", "FAILURE", "2026-07-25T20:10:00Z"),
                check("Lint & format", "SUCCESS", "2026-07-25T21:30:00Z"),
            ],
        ),
        NOW,
    )
    assert reason is None or "Lint & format" not in reason


def test_merge_conflict_is_reported():
    reason = stall_reason(open_pr(merge_state="DIRTY"), NOW)
    assert reason and "conflict" in reason.lower()


def test_auto_merge_never_armed_is_reported():
    """The PAT lapsing takes auto-merge with it — green checks that never merge."""
    reason = stall_reason(open_pr(merge_state="CLEAN", auto_merge=False), NOW)
    assert reason and "auto-merge" in reason.lower()


def test_an_old_pr_that_is_merely_blocked_still_alerts():
    """Whatever the cause, a data PR this old is never going to merge itself."""
    reason = stall_reason(open_pr(minutes_old=180, checks=[]), NOW)
    assert reason


def test_an_unparseable_created_at_stays_quiet():
    """Fail-safe, like the other guards: garbage in means no alert, not a spam loop."""
    pr = open_pr()
    pr[0]["createdAt"] = ""
    assert stall_reason(pr, NOW) is None


# --- main(): the $GITHUB_OUTPUT contract update.yml consumes -------------------


def run_main(prs: list[dict], monkeypatch, tmp_path) -> dict[str, str]:
    """Run main() with ``prs`` on stdin and return the $GITHUB_OUTPUT key/values."""
    import io
    import json
    import sys

    import check_stalled_data_pr as mod

    out = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(prs)))
    assert mod.main() == 0
    return dict(line.split("=", 1) for line in out.read_text(encoding="utf-8").splitlines())


def test_main_reports_no_open_pr(monkeypatch, tmp_path):
    """open=false is the recovery signal: the alert issue can be auto-closed."""
    outputs = run_main([], monkeypatch, tmp_path)
    assert outputs["open"] == "false"
    assert outputs["stalled"] == "false"


def test_main_reports_open_but_healthy_pr(monkeypatch, tmp_path):
    """A PR still inside its merge window is open (incident not over) yet not stalled."""
    fresh = open_pr(checks=list(GREEN))
    fresh[0]["createdAt"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    outputs = run_main(fresh, monkeypatch, tmp_path)
    assert outputs["open"] == "true"
    assert outputs["stalled"] == "false"
