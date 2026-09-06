"""Tests for the driver-race-history fetcher: its target pool (#147) and the
retry budget that has to survive a drained API rate limit.

Network and sleep are injected so these tests are instant and offline.
"""

from fetch import fetch_driver_races as fdr


def _podium(p1, p2, p3):
    return {"p1": {"driverId": p1}, "p2": {"driverId": p2}, "p3": {"driverId": p3}}


class _Resp:
    """Minimal stand-in for a requests Response."""

    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        raise AssertionError(f"raise_for_status() on an unexpected {self.status_code}")


class _Requests:
    """Serves a scripted status sequence, counting the calls it took."""

    def __init__(self, statuses, payload):
        self.statuses = list(statuses)
        self.payload = payload
        self.calls = 0

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls += 1
        status = self.statuses.pop(0)
        return _Resp(status, self.payload if status == 200 else None)


def test_pool_includes_top_podium_getters():
    podiums = [_podium("top", f"filler2_{i}", f"filler3_{i}") for i in range(5)] + [
        _podium("other", f"filler2b_{i}", f"filler3b_{i}") for i in range(2)
    ]
    targets = fdr.target_driver_ids(podiums, grid_drivers=[], combos=[], pool_n=1)
    assert "top" in targets
    assert "other" not in targets


def test_pool_includes_current_grid():
    targets = fdr.target_driver_ids(
        podiums=[], grid_drivers=[{"driverId": "rookie", "name": "Rookie"}], combos=[]
    )
    assert "rookie" in targets


def test_pool_includes_every_combo_driver_even_outside_top_n():
    """A driver who appears in a historical combos.json trio must always get a
    race-history entry, even if their raw podium count is outside the top-N
    pool — otherwise compute_unlikeliest silently skips that trio (#147)."""
    # "star" dominates the podium-count pool; the combo drivers never podiumed.
    podiums = [_podium("star", f"filler2_{i}", f"filler3_{i}") for i in range(10)]
    combos = [{"driverIds": ["obscure_a", "obscure_b", "obscure_c"]}]
    targets = fdr.target_driver_ids(podiums, grid_drivers=[], combos=combos, pool_n=1)
    assert {"obscure_a", "obscure_b", "obscure_c"} <= targets


def test_get_rides_out_a_long_429_streak(monkeypatch):
    """Driver races is the *last* fetcher in update.py, so on a --full run it
    meets the API's hourly budget already drained by the podium/results/qualifying
    sweeps. It therefore needs the same ~4-minute retry budget those fetchers
    were given: a streak of 429s must be ridden out, not fatal.
    """
    payload = {"MRData": {"RaceTable": {"Races": []}}}
    requests_stub = _Requests([429] * 7 + [200], payload)
    monkeypatch.setattr(fdr, "requests", requests_stub)
    monkeypatch.setattr(fdr.time, "sleep", lambda _seconds: None)

    assert fdr.get("https://example.test/results.json") == payload
    assert requests_stub.calls == 8
