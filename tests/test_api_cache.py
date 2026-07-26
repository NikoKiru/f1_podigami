"""Tests for the Jolpica response-cache bypass.

The API answers from a cache keyed on the request headers
(``Vary: Accept, origin, accept-encoding``) with a long TTL, and each variant
ages independently. Every fetcher sends ``Accept: application/json``, which is
a cold, rarely-refreshed entry: measured on 2026-07-26 it served a 57-minute-old
body for ``/2026/results.json`` (220 rows, missing the finished round 11) while
the header-less variant of the same URL was 13 minutes old and had it.

That is what pulled podiums.json and race_results.json out of step, and what
left the results watcher polling a stale ``last/results`` feed for an hour.
``Cache-Control: no-cache`` is ignored by the origin; a unique query parameter
is the one bypass that works, so freshness-critical requests carry a nonce.
"""

from fetch.api_cache import CACHE_BUSTER, fresh


class Clock:
    """Wall-clock stand-in returning whatever the test sets."""

    def __init__(self, t: float = 1000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


def test_adds_a_nonce_parameter():
    out = fresh({"limit": 100}, now=Clock())
    assert out["limit"] == 100
    assert CACHE_BUSTER in out


def test_does_not_mutate_the_callers_params():
    params = {"limit": 100, "offset": 0}
    fresh(params, now=Clock())
    assert params == {"limit": 100, "offset": 0}


def test_works_without_any_params():
    assert set(fresh(now=Clock())) == {CACHE_BUSTER}
    assert set(fresh(None, now=Clock())) == {CACHE_BUSTER}


def test_nonce_changes_as_time_moves_on():
    """Consecutive polls must not collide, or the watcher caches its own
    stale answer and waits out the whole budget on it."""
    clock = Clock(1000.0)
    first = fresh(now=clock)[CACHE_BUSTER]
    clock.t += 180.0
    assert fresh(now=clock)[CACHE_BUSTER] != first


def test_nonce_is_stable_within_the_same_second():
    """Retries after a backoff inside one second reuse the URL rather than
    burning a second origin miss."""
    clock = Clock(1000.4)
    first = fresh(now=clock)[CACHE_BUSTER]
    clock.t = 1000.9
    assert fresh(now=clock)[CACHE_BUSTER] == first
