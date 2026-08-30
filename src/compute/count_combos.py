"""Aggregate per-race podiums into unique 3-driver combinations (order independent)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from compute.shared_drives import podium_drivers, podium_trios  # noqa: E402
from datalib import save_combos  # noqa: E402

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
IN_PATH = DATA_DIR / "podiums.json"
OUT_PATH = DATA_DIR / "combos.json"


def main() -> int:
    podiums = json.loads(IN_PATH.read_text(encoding="utf-8"))

    combos: dict[tuple[str, str, str], dict] = {}
    name_by_id: dict[str, str] = {}

    for race in podiums:
        for d in podium_drivers(race):
            name_by_id[d["driverId"]] = d["name"]
        race_ref = {
            "season": race["season"],
            "round": race["round"],
            "raceName": race["raceName"],
        }
        # A shared car puts four or more drivers on the podium, so one race can
        # produce several distinct trios — each is a real combination, and each
        # counts this race once.
        for key in podium_trios(race):
            combo = combos.setdefault(key, {"driverIds": list(key), "count": 0, "races": []})
            combo["count"] += 1
            combo["races"].append(dict(race_ref))

    out = []
    for combo in combos.values():
        names = [name_by_id[d] for d in combo["driverIds"]]
        races_chrono = sorted(combo["races"], key=lambda r: (int(r["season"]), int(r["round"])))
        last = races_chrono[-1]
        first = races_chrono[0]
        out.append(
            {
                "drivers": names,
                "driverIds": combo["driverIds"],
                "count": combo["count"],
                "lastRace": last,
                "firstRace": first,
                "lastRaceKey": int(last["season"]) * 1000 + int(last["round"]),
                "races": races_chrono,
            }
        )

    out.sort(key=lambda c: (-c["count"], " | ".join(c["drivers"]).lower()))

    save_combos(out)

    total_races = sum(c["count"] for c in out)
    print(f"Wrote {OUT_PATH}")
    print(f"  unique combinations: {len(out)}")
    print(f"  trio appearances: {total_races} across {len(podiums)} races")
    print()
    print("Top 10 by count:")
    for i, c in enumerate(out[:10], 1):
        last = c["lastRace"]
        print(
            f"  {i:2}. {c['count']:3}x  {' / '.join(c['drivers'])}  (last: {last['season']} {last['raceName']})"
        )
    print()
    print("Top 10 most recent combos:")
    by_recent = sorted(out, key=lambda c: -c["lastRaceKey"])
    for i, c in enumerate(by_recent[:10], 1):
        last = c["lastRace"]
        print(
            f"  {i:2}. {last['season']} R{last['round']:>2}  {' / '.join(c['drivers'])}  ({c['count']}x)"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
