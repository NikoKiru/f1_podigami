"""Shared-drive podiums: one car, more than one driver on the step.

Before 1961 it was routine for two or three drivers to share a car during a
Grand Prix; all of them are classified at that car's finishing position. The
podium slots in ``podiums.json`` name the first-classified driver, and the rest
live in the optional ``coDrivers`` map.

The site's identity is a trio of three *distinct* drivers, so a shared step
means a race produced several trios at once rather than a wider podium. Every
compute stage asks one of the two questions answered here — who stood on this
podium, and which trios did this race produce — so the expansion rule lives in
exactly one place.
"""

from __future__ import annotations

import itertools

SLOTS = ("p1", "p2", "p3")


def slot_drivers(race: dict, slot: str) -> list[dict]:
    """Every driver classified at ``slot``, the first-classified one first."""
    extras = (race.get("coDrivers") or {}).get(slot) or []
    return [race[slot], *extras]


def has_shared_drive(race: dict) -> bool:
    """True when any podium step was held by more than one driver."""
    return any((race.get("coDrivers") or {}).get(slot) for slot in SLOTS)


def podium_drivers(race: dict) -> list[dict]:
    """Every distinct driver on the podium, in slot order, deduplicated.

    A driver can hold two steps at once — in the 1955 Argentine Grand Prix
    Farina and Trintignant each drove a share of both the second- and
    third-placed cars — so identity, not position, decides uniqueness.
    """
    out: list[dict] = []
    seen: set[str] = set()
    for slot in SLOTS:
        for d in slot_drivers(race, slot):
            if d["driverId"] not in seen:
                seen.add(d["driverId"])
                out.append(d)
    return out


def podium_trios(race: dict) -> list[tuple[str, str, str]]:
    """The sorted, distinct three-driver trios this race put on the podium.

    One trio for a normal race. For a shared step, the cartesian product across
    the slots — discarding any product that names the same driver twice, which
    is what keeps the 1955 Argentine Grand Prix honest.
    """
    per_slot = [[d["driverId"] for d in slot_drivers(race, slot)] for slot in SLOTS]
    trios = {tuple(sorted(combo)) for combo in itertools.product(*per_slot) if len(set(combo)) == 3}
    return sorted(trios)
