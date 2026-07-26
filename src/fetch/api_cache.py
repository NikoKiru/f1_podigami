"""Bypass Jolpica's response cache for requests whose answer can still change.

The API sets ``Vary: Accept, origin, accept-encoding`` and caches each variant
independently with a long TTL. Our fetchers all send ``Accept: application/json``
— a cold entry that can lag the live data by the better part of an hour. Because
the entries for different URLs expire at different times, two fetchers running
seconds apart can disagree about whether a race exists, which is how podiums.json
ran a round ahead of race_results.json on 2026-07-26.

``Cache-Control: no-cache`` is ignored by the origin. A query parameter the API
does not interpret changes the cache key and reliably reaches live data, so
freshness-critical requests carry a per-second nonce.

Use this only where staleness actually matters — the current season and the
results watcher. Historical seasons are immutable, and busting the cache for a
1950-onwards rebuild would turn every page into an origin miss for no benefit.
"""

from __future__ import annotations

import time
from collections.abc import Callable

# Ergast/Jolpica ignore unknown query parameters; "_" is the conventional
# cache-buster name and keeps the URL readable in logs.
CACHE_BUSTER = "_"


def fresh(
    params: dict | None = None,
    *,
    now: Callable[[], float] = time.time,
) -> dict:
    """Copy of ``params`` with a nonce that defeats the cached response.

    Whole-second resolution: distinct polls (minutes apart) always miss the
    cache, while a backoff retry within the same second reuses the URL.
    """
    out = dict(params or {})
    out[CACHE_BUSTER] = str(int(now()))
    return out
