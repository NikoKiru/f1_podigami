# Shared-Drive Podiums Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Credit every driver who shared a car onto a 1950s podium, so the 20 driver trios that really happened stop being listed as never-happened.

**Architecture:** `Podium` gains an optional `coDrivers` map, backfilled from the already-committed `race_results.json`. A new `src/compute/shared_drives.py` owns the two questions every consumer asks — "who was on this podium?" and "which trios did this race produce?" — and the five compute scripts route through it. `combos.html` derives its shared-car markers at render time from `podiums.json`; no new field enters `combos.json`.

**Tech Stack:** Python 3.11+, Pydantic v2 (`src/datalib`), pytest, ruff. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-27-shared-drive-podiums-design.md`

## Global Constraints

- **The trio identity is unchanged.** A combo is exactly three distinct drivers. A shared podium step means the race produced *several* trios, never a 4-driver combo.
- **A driver may never appear twice in one trio.** In the 1955 Argentine Grand Prix (R1) Farina and Trintignant each drove a share of both the second- and third-placed cars, so they sit at two positions at once; products naming a driver twice are discarded.
- **`p1`/`p2`/`p3` keep their current meaning:** the first driver the API classifies at that position. `coDrivers` carries the rest. This keeps `test_race_results_podiums_agree_with_podiums_dataset` passing untouched.
- **`coDrivers` is omitted, never null.** 1143 of 1161 podium entries must serialize byte-identically. Achieved with a `model_serializer` on `Podium` alone — **do not** add `exclude_none=True` to `repository._save`: `podigami.json`, `model_eval.json` and `grid_penalties.json` contain explicit nulls today and would all break the byte-identical round-trip.
- **Nothing may be added to `RaceRef` or `Combo`.** An optional field on `RaceRef` would emit `"shared": null` on every race entry in the 490 KB `combos.json`.
- **`model_v2.py`, `backtest.py` and `data/model_eval.json` are out of scope.** Do not touch them; changing the pre-1961 tie-break would perturb the frozen backtest window.
- Run `python -m ruff check .` and `python -m ruff format .` before every commit. CI fails on either.
- Expected end-state numbers, all verified against the committed data: **754 unique combos** (from 734), counts summing to **1185** trio appearances across **1161** races, **18** shared-drive races, **40** combos carrying a shared-car badge, **42** shared race pills.

## File Structure

**Created**
- `src/compute/shared_drives.py` — the only place that knows how a shared podium expands. `slot_drivers`, `podium_drivers`, `podium_trios`, `has_shared_drive`.
- `tests/test_shared_drives.py` — unit tests for the above, including the 1955 Argentina case.

**Modified**
- `src/datalib/schemas.py:44-50` — `Podium.coDrivers` + its serializer.
- `src/fetch/fetch_podiums.py` — record co-drivers from live responses; add `--backfill-shared`.
- `src/compute/count_combos.py:23-35` — expand each race into its trios.
- `src/compute/compute_podigami.py:395-401` — `seen` set and `name_by_id` cover co-drivers.
- `src/compute/compute_soulmates.py:30-56` — count co-drivers.
- `src/compute/compute_overdue.py:87-91`, `src/compute/compute_unlikeliest.py:50-55` — count co-drivers.
- `src/build/build_combos_html.py` — shared-car badge on combo rows, co-driver `title` on race pills.
- `src/build/build_podigami_html.py:249-265` — stacked-step markup in the last-race card.
- `assets/combos.css`, `assets/podigami.css` — styling for both.
- `tests/test_pipeline_integrity.py:29-37`, `tests/test_data_integrity.py:54-70` — updated invariants.
- `data/podiums.json`, `data/combos.json`, `data/soulmates.json`, `data/overdue.json`, `data/unlikeliest.json`, `data/podigami.json` — regenerated.
- `README.md`, `RELEASE_NOTES.md`.

---

### Task 1: `coDrivers` on the podium schema

**Files:**
- Modify: `src/datalib/schemas.py:44-50`
- Test: `tests/test_datalib.py`

**Interfaces:**
- Produces: `Podium.coDrivers: dict[str, list[DriverRef]] | None` — keys are `"p1"`, `"p2"`, `"p3"`; each value is the drivers who shared that position's car, in classification order after the primary. Absent when the podium was normal.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_datalib.py`:

```python
def test_podium_without_codrivers_roundtrips_without_the_key():
    """The 1143 normal races must serialise exactly as they do today: a podium
    that omits coDrivers must not gain a null key on the way back out."""
    payload = {
        "season": "1950",
        "round": "1",
        "raceName": "British Grand Prix",
        "p1": {"driverId": "farina", "name": "Nino Farina"},
        "p2": {"driverId": "fagioli", "name": "Luigi Fagioli"},
        "p3": {"driverId": "reg_parnell", "name": "Reg Parnell"},
    }
    dumped = Podium.model_validate(payload).model_dump(mode="json")
    assert dumped == payload
    assert "coDrivers" not in dumped


def test_podium_carries_shared_drive_codrivers():
    """1956 Belgium: Perdisa and Moss shared the third-placed Maserati."""
    payload = {
        "season": "1956",
        "round": "4",
        "raceName": "Belgian Grand Prix",
        "p1": {"driverId": "collins", "name": "Peter Collins"},
        "p2": {"driverId": "frere", "name": "Paul Frère"},
        "p3": {"driverId": "perdisa", "name": "Cesare Perdisa"},
        "coDrivers": {"p3": [{"driverId": "moss", "name": "Stirling Moss"}]},
    }
    pod = Podium.model_validate(payload)
    assert pod.coDrivers["p3"][0].driverId == "moss"
    assert pod.model_dump(mode="json") == payload
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_datalib.py -k codrivers -v`

Expected: FAIL — `ValidationError: 1 validation error for Podium / coDrivers / Extra inputs are not permitted` (the `_Base` config forbids unknown keys).

- [ ] **Step 3: Add the field and its serializer**

In `src/datalib/schemas.py`, extend the import at the top:

```python
from pydantic import BaseModel, ConfigDict, model_serializer, model_validator
```

Then replace the `Podium` class:

```python
class Podium(_Base):
    """One race's podium.

    ``p1``/``p2``/``p3`` name the first driver the API classifies at each
    position. Before 1961 two or three drivers routinely shared one car and are
    all classified at the same position; the extras live in ``coDrivers``, keyed
    by slot.

    The field is dropped from the serialisation when absent so the 1143 races
    without a shared drive stay byte-identical. This is deliberately local to
    this model: other datasets (podigami, model_eval, grid_penalties) do write
    explicit nulls, and a global ``exclude_none`` would rewrite all of them.
    """

    season: str
    round: str
    raceName: str
    p1: DriverRef
    p2: DriverRef
    p3: DriverRef
    coDrivers: dict[str, list[DriverRef]] | None = None

    @model_serializer(mode="wrap")
    def _omit_absent_codrivers(self, handler):
        data = handler(self)
        if data.get("coDrivers") is None:
            data.pop("coDrivers", None)
        return data
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_datalib.py -k codrivers -v`

Expected: PASS, 2 tests.

- [ ] **Step 5: Verify nothing else regressed**

Run: `PYTHONPATH=src python -m pytest tests/test_datalib.py tests/test_data_integrity.py -q`

Expected: PASS. `test_dataset_roundtrips_byte_identical` must still pass for **every** dataset — the serializer touches `Podium` only, and `podiums.json` has no nulls today. If any dataset fails, revert the serializer rather than reformatting committed data.

- [ ] **Step 6: Lint and commit**

```bash
python -m ruff check . && python -m ruff format .
git add src/datalib/schemas.py tests/test_datalib.py
git commit -m "feat(datalib): carry shared-drive co-drivers on Podium"
```

---

### Task 2: Backfill `coDrivers` into `podiums.json`

**Files:**
- Modify: `src/fetch/fetch_podiums.py`
- Test: `tests/test_data_integrity.py`

**Interfaces:**
- Consumes: `Podium.coDrivers` (Task 1).
- Produces: `data/podiums.json` with `coDrivers` on exactly 18 entries; `fetch_podiums.main(["--backfill-shared"])` returning `0`.

**Why a backfill and not `--full`:** a full podiums fetch is hundreds of API calls for history already committed in `race_results.json`. The backfill reads that file, and only calls the API for driver names it cannot resolve locally — exactly three (`portago`, `ayulo`, `bettenhausen`), each verified present at `/ergast/f1/drivers/{driverId}.json` and resolving to "Alfonso de Portago", "Manny Ayulo" and "Tony Bettenhausen".

- [ ] **Step 1: Write the failing test**

Append to `tests/test_data_integrity.py`:

```python
def test_codrivers_match_duplicate_positions_in_race_results():
    """Every shared podium step in race_results.json is recorded in podiums.json
    and vice versa — no shared drive silently dropped, none invented."""
    from collections import defaultdict

    truth: dict[tuple[str, str], dict[str, list[str]]] = {}
    for race in load_race_results():
        by_pos: dict[int, list[str]] = defaultdict(list)
        for row in race.results:
            if row.position in (1, 2, 3):
                by_pos[row.position].append(row.driverId)
        extra = {f"p{p}": ids[1:] for p, ids in by_pos.items() if len(ids) > 1}
        if extra:
            truth[(race.season, race.round)] = extra

    recorded = {
        (p.season, p.round): {k: [d.driverId for d in v] for k, v in (p.coDrivers or {}).items()}
        for p in load_podiums()
        if p.coDrivers
    }

    assert len(truth) == 18, f"expected 18 shared-drive races, found {len(truth)}"
    assert recorded == truth


def test_codriver_is_never_the_primary_of_its_own_slot():
    for p in load_podiums():
        for slot, extras in (p.coDrivers or {}).items():
            assert slot in ("p1", "p2", "p3")
            primary = getattr(p, slot).driverId
            ids = [d.driverId for d in extras]
            assert primary not in ids, f"{p.season} R{p.round} {slot} repeats {primary}"
            assert len(set(ids)) == len(ids)
            assert all(d.name.strip() for d in extras)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_data_integrity.py -k codriver -v`

Expected: FAIL on `test_codrivers_match_duplicate_positions_in_race_results` — `recorded` is `{}` because nothing has been backfilled yet.

- [ ] **Step 3: Record co-drivers from live API responses**

In `src/fetch/fetch_podiums.py`, inside `main`'s fetch loop, replace the three lines that keep only the first result:

```python
                results = race.get("Results") or []
                if not results:
                    continue
                entry[f"p{position}"] = driver_record(results[0])
                extras = [driver_record(r) for r in results[1:]]
                if extras:
                    entry.setdefault("coDrivers", {})[f"p{position}"] = extras
```

An empty map must never reach `save_podiums`, so add this immediately before `save_podiums(complete)`:

```python
    for r in complete:
        if not r.get("coDrivers"):
            r.pop("coDrivers", None)
```

- [ ] **Step 4: Add the offline backfill**

Add near the other module constants in `src/fetch/fetch_podiums.py`:

```python
RESULTS_PATH = DATA_DIR / "race_results.json"
```

and these two functions above `main`:

```python
def resolve_driver_name(driver_id: str) -> str:
    """Look up one driver's display name from the API.

    Only reached for a driver who appears nowhere else in podiums.json — three
    of them in all of history (Portago, Ayulo, Bettenhausen), because a shared
    drive was their only podium.
    """
    data = get(f"{API_ROOT}/drivers/{driver_id}.json", {})
    drivers = data["MRData"]["DriverTable"]["Drivers"]
    if not drivers:
        raise RuntimeError(f"API knows no driver {driver_id!r}")
    d = drivers[0]
    return f"{d['givenName']} {d['familyName']}"


def backfill_shared() -> int:
    """Fill coDrivers on the committed podiums.json from race_results.json.

    Shared drives are a closed set of pre-1961 races, and race_results.json
    already records every driver at the shared car's position — so this needs no
    historical re-fetch, just the local join.
    """
    podiums = json.loads(OUT_PATH.read_text(encoding="utf-8"))
    results = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))

    name_by_id = {r[s]["driverId"]: r[s]["name"] for r in podiums for s in ("p1", "p2", "p3")}

    shared: dict[tuple[str, str], dict[str, list[str]]] = {}
    for race in results:
        by_pos: dict[int, list[str]] = {}
        for row in race["results"]:
            if row["position"] in (1, 2, 3):
                by_pos.setdefault(row["position"], []).append(row["driverId"])
        extra = {f"p{p}": ids[1:] for p, ids in by_pos.items() if len(ids) > 1}
        if extra:
            shared[(race["season"], race["round"])] = extra

    unknown = sorted(
        {d for slots in shared.values() for ids in slots.values() for d in ids} - set(name_by_id)
    )
    for driver_id in unknown:
        name_by_id[driver_id] = resolve_driver_name(driver_id)
        print(f"  resolved {driver_id} -> {name_by_id[driver_id]}")
        time.sleep(SLEEP_BETWEEN)

    filled = 0
    for race in podiums:
        race.pop("coDrivers", None)
        slots = shared.get((race["season"], race["round"]))
        if not slots:
            continue
        race["coDrivers"] = {
            slot: [{"driverId": d, "name": name_by_id[d]} for d in ids]
            for slot, ids in sorted(slots.items())
        }
        filled += 1

    save_podiums(podiums)
    print(f"Backfilled shared drives into {OUT_PATH}: {filled} races")
    return 0
```

Register the flag alongside `--full` in `main`, and dispatch on it right after parsing:

```python
    parser.add_argument(
        "--backfill-shared",
        action="store_true",
        help="fill coDrivers from the committed race_results.json (no full re-fetch)",
    )
    args = parser.parse_args(argv)

    if args.backfill_shared:
        return backfill_shared()
```

- [ ] **Step 5: Run the backfill**

Run: `python src/fetch/fetch_podiums.py --backfill-shared`

Expected: three `resolved ...` lines (`ayulo -> Manny Ayulo`, `bettenhausen -> Tony Bettenhausen`, `portago -> Alfonso de Portago`), then `Backfilled shared drives into .../podiums.json: 18 races`.

- [ ] **Step 6: Verify the data**

```bash
PYTHONPATH=src python -m pytest tests/test_data_integrity.py tests/test_datalib.py -q
git diff --stat data/podiums.json
git diff data/podiums.json | grep -c '^-[^-]'
```

Expected: tests PASS, and the deletion count is **0** — the diff must be pure additions (18 inserted `coDrivers` blocks). Any modified or deleted line means the serializer or key order is wrong; stop and fix Task 1 rather than committing a reformat.

- [ ] **Step 7: Lint and commit**

```bash
python -m ruff check . && python -m ruff format .
git add src/fetch/fetch_podiums.py tests/test_data_integrity.py data/podiums.json
git commit -m "feat(fetch): record shared-drive co-drivers and backfill history"
```

---

### Task 3: The shared-drive expansion helper

**Files:**
- Create: `src/compute/shared_drives.py`
- Test: `tests/test_shared_drives.py`

**Interfaces:**
- Consumes: raw podium dicts as loaded from `data/podiums.json` (the compute scripts read raw JSON, not models).
- Produces:
  - `slot_drivers(race: dict, slot: str) -> list[dict]` — `[{"driverId", "name"}, ...]`, primary first.
  - `podium_drivers(race: dict) -> list[dict]` — every distinct driver on the podium, slot order, deduplicated by `driverId`.
  - `podium_trios(race: dict) -> list[tuple[str, str, str]]` — sorted distinct legal trio keys.
  - `has_shared_drive(race: dict) -> bool`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_shared_drives.py`:

```python
"""The rules for expanding a shared-car podium into driver trios."""

from compute.shared_drives import (
    has_shared_drive,
    podium_drivers,
    podium_trios,
    slot_drivers,
)


def _ref(did):
    return {"driverId": did, "name": did.title()}


NORMAL = {
    "season": "2021",
    "round": "21",
    "raceName": "Saudi Arabian Grand Prix",
    "p1": _ref("hamilton"),
    "p2": _ref("max_verstappen"),
    "p3": _ref("bottas"),
}

# 1956 Belgium: Perdisa and Moss shared the third-placed Maserati.
BELGIUM_1956 = {
    "season": "1956",
    "round": "4",
    "raceName": "Belgian Grand Prix",
    "p1": _ref("collins"),
    "p2": _ref("frere"),
    "p3": _ref("perdisa"),
    "coDrivers": {"p3": [_ref("moss")]},
}

# 1955 Argentina: Farina and Trintignant each drove a share of BOTH the
# second- and third-placed cars, so they appear at two positions at once.
ARGENTINA_1955 = {
    "season": "1955",
    "round": "1",
    "raceName": "Argentine Grand Prix",
    "p1": _ref("fangio"),
    "p2": _ref("farina"),
    "p3": _ref("maglioli"),
    "coDrivers": {
        "p2": [_ref("gonzalez"), _ref("trintignant")],
        "p3": [_ref("farina"), _ref("trintignant")],
    },
}


def test_normal_race_is_not_shared():
    assert has_shared_drive(NORMAL) is False
    assert slot_drivers(NORMAL, "p3") == [_ref("bottas")]
    assert podium_trios(NORMAL) == [("bottas", "hamilton", "max_verstappen")]


def test_shared_step_yields_both_trios():
    assert has_shared_drive(BELGIUM_1956) is True
    assert [d["driverId"] for d in slot_drivers(BELGIUM_1956, "p3")] == ["perdisa", "moss"]
    assert podium_trios(BELGIUM_1956) == [
        ("collins", "frere", "moss"),
        ("collins", "frere", "perdisa"),
    ]


def test_podium_drivers_lists_everyone_once():
    assert [d["driverId"] for d in podium_drivers(BELGIUM_1956)] == [
        "collins",
        "frere",
        "perdisa",
        "moss",
    ]
    # farina and trintignant sit at two positions but are one driver each
    assert [d["driverId"] for d in podium_drivers(ARGENTINA_1955)] == [
        "fangio",
        "farina",
        "gonzalez",
        "trintignant",
        "maglioli",
    ]


def test_a_driver_never_appears_twice_in_one_trio():
    trios = podium_trios(ARGENTINA_1955)
    for t in trios:
        assert len(set(t)) == 3, f"{t} names a driver twice"
    assert trios == sorted(set(trios)), "trios must be sorted and deduplicated"
    # fangio + (farina|gonzalez|trintignant) + (maglioli|farina|trintignant),
    # minus the two products that name farina or trintignant twice. Six survive
    # — including fangio/farina/gonzalez, which is real: gonzalez drove a share
    # of the second-placed car and farina a share of the third.
    assert trios == [
        ("fangio", "farina", "gonzalez"),
        ("fangio", "farina", "maglioli"),
        ("fangio", "farina", "trintignant"),
        ("fangio", "gonzalez", "maglioli"),
        ("fangio", "gonzalez", "trintignant"),
        ("fangio", "maglioli", "trintignant"),
    ]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `PYTHONPATH=src python -m pytest tests/test_shared_drives.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'compute.shared_drives'`.

- [ ] **Step 3: Write the module**

Create `src/compute/shared_drives.py`:

```python
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
    trios = {
        tuple(sorted(combo)) for combo in itertools.product(*per_slot) if len(set(combo)) == 3
    }
    return sorted(trios)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PYTHONPATH=src python -m pytest tests/test_shared_drives.py -v`

Expected: PASS, 4 tests.

- [ ] **Step 5: Sanity-check against the real dataset**

```bash
PYTHONPATH=src python -c "
import json
from compute.shared_drives import podium_trios, has_shared_drive
p = json.load(open('data/podiums.json'))
print('shared races:', sum(1 for r in p if has_shared_drive(r)))
print('trio instances:', sum(len(podium_trios(r)) for r in p))
print('unique trios:', len({t for r in p for t in podium_trios(r)}))
"
```

Expected exactly:

```
shared races: 18
trio instances: 1185
unique trios: 754
```

- [ ] **Step 6: Lint and commit**

```bash
python -m ruff check . && python -m ruff format .
git add src/compute/shared_drives.py tests/test_shared_drives.py
git commit -m "feat(compute): add the shared-drive podium expansion helper"
```

---

### Task 4: Expand combos

**Files:**
- Modify: `src/compute/count_combos.py:19-62`
- Modify: `tests/test_pipeline_integrity.py:29-37`
- Modify: `tests/test_data_integrity.py:54-70`
- Regenerate: `data/combos.json`

**Interfaces:**
- Consumes: `podium_trios`, `podium_drivers` (Task 3).
- Produces: `data/combos.json` with 754 combos whose counts sum to 1185.

- [ ] **Step 1: Update the pipeline invariant to the new truth**

`tests/test_pipeline_integrity.py:34` currently asserts `sum(c["count"] for c in combos) == len(podiums)`, which is exactly what a shared drive breaks. Replace `test_every_podium_maps_to_one_combo` with:

```python
def test_every_podium_maps_to_its_combos():
    """Each race contributes one combo — or several, when a shared car put more
    than three drivers on the podium (18 pre-1961 races)."""
    from compute.shared_drives import has_shared_drive, podium_trios

    podiums = load_data("podiums.json")
    combos = load_data("combos.json")
    by_key = {trio(c["driverIds"]): c for c in combos}
    assert len(by_key) == len(combos), "combo keys must be unique"

    expected_instances = sum(len(podium_trios(p)) for p in podiums)
    assert sum(c["count"] for c in combos) == expected_instances
    assert expected_instances > len(podiums), "shared drives must add trio instances"
    assert sum(1 for p in podiums if has_shared_drive(p)) == 18

    for p in podiums:
        for k in podium_trios(p):
            assert k in by_key, f"podium trio {k} missing from combos"
```

In `tests/test_data_integrity.py`, `test_combo_drivers_aligned_with_driver_ids` builds its name map from `p1/p2/p3` only, so it will not know Portago, Ayulo or Bettenhausen and will fail with `unknown driverId`. Replace its map-building block:

```python
    name_by_id: dict[str, str] = {}
    for p in load_podiums():
        for slot in ("p1", "p2", "p3"):
            for d in [getattr(p, slot), *((p.coDrivers or {}).get(slot) or [])]:
                name_by_id[d.driverId] = d.name
```

- [ ] **Step 2: Run them to verify they fail**

Run: `PYTHONPATH=src python -m pytest tests/test_pipeline_integrity.py tests/test_data_integrity.py -q`

Expected: FAIL — `assert 1161 == 1185` on the count sum, plus a missing-trio assertion such as `podium trio ('collins', 'frere', 'moss') missing from combos`.

- [ ] **Step 3: Expand the combo builder**

In `src/compute/count_combos.py`, add the import beside the `datalib` one:

```python
from compute.shared_drives import podium_drivers, podium_trios  # noqa: E402
```

Replace the accumulation loop:

```python
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
```

and fix the closing summary, which currently claims the sum should equal the race count:

```python
    total_races = sum(c["count"] for c in out)
    print(f"Wrote {OUT_PATH}")
    print(f"  unique combinations: {len(out)}")
    print(f"  trio appearances: {total_races} across {len(podiums)} races")
```

- [ ] **Step 4: Regenerate and verify**

```bash
python src/compute/count_combos.py
PYTHONPATH=src python -m pytest tests/test_pipeline_integrity.py tests/test_data_integrity.py -q
```

Expected: the script prints `unique combinations: 754` and `trio appearances: 1185 across 1161 races`; tests PASS.

- [ ] **Step 5: Spot-check the headline fix**

```bash
python -c "
import json
c = {tuple(sorted(x['driverIds'])): x for x in json.load(open('data/combos.json'))}
print(c[('collins','frere','moss')])
"
```

Expected: a combo with `count: 1` whose single race is the 1956 Belgian Grand Prix — the trio the site previously said had never happened.

- [ ] **Step 6: Lint and commit**

```bash
python -m ruff check . && python -m ruff format .
git add src/compute/count_combos.py tests/test_pipeline_integrity.py tests/test_data_integrity.py data/combos.json
git commit -m "feat(compute): expand shared-drive podiums into every real trio"
```

---

### Task 5: Credit co-drivers in podigami, soulmates, overdue and unlikeliest

**Files:**
- Modify: `src/compute/compute_podigami.py:395-401`
- Modify: `src/compute/compute_soulmates.py:30-56`
- Modify: `src/compute/compute_overdue.py:87-91`
- Modify: `src/compute/compute_unlikeliest.py:50-55`
- Test: `tests/test_compute_podigami.py`
- Regenerate: `data/podigami.json`, `data/soulmates.json`, `data/overdue.json`, `data/unlikeliest.json`

**Interfaces:**
- Consumes: `podium_drivers`, `podium_trios` (Task 3).

**Why this matters:** `compute_podigami` decides which trios have already happened. If its `seen` set still holds only the primary trios, the site keeps treating `collins / frere / moss` as never-having-happened even after Task 4 records it as history.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_compute_podigami.py`. It reuses that file's existing
`race` and `combos_from` helpers and mirrors `test_single_seen_trio_is_impossible`:

```python
def test_shared_drive_trio_counts_as_already_seen():
    """One car, two drivers: Cas handed his car to Dan mid-race, so alf+bob+dan
    stood on that podium too and must never be offered as a brand-new trio."""
    podiums = [race(2025, 1, "alf", "bob", "cas")]
    podiums[0]["coDrivers"] = {"p3": [{"driverId": "dan", "name": "Dan"}]}
    grid = [{"driverId": d, "name": d.title()} for d in ("alf", "bob", "dan")]
    res = cp.compute(podiums, combos_from(podiums), grid)
    assert res["chanceNextRaceNew"] == pytest.approx(0.0)
    assert res["candidates"] == []
```

The three-driver grid admits exactly one trio, `alf/bob/dan`, and the shared
drive is the only thing that makes it history — so this fails while the `seen`
set is built from the primary slots alone, and passes once it is not.

- [ ] **Step 2: Run it to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_compute_podigami.py -k shared_drive -v`

Expected: FAIL — `assert 100.0 == 0.0 ± 1.0e-06`, because `compute` still treats
`alf/bob/dan` as never-having-happened and reports it as a certain new combo.

- [ ] **Step 3: Expand the `seen` set in `compute_podigami.py`**

Add the import next to the other `compute` imports:

```python
from compute.shared_drives import podium_drivers, podium_trios  # noqa: E402
```

Replace the `name_by_id` / `seen` loop at lines 395-401:

```python
    per_driver = model.index_podiums(races)
    name_by_id: dict[str, str] = {}
    seen: set[tuple[str, str, str]] = set()
    for r in races:
        for d in podium_drivers(r):
            name_by_id[d["driverId"]] = d["name"]
        # A shared car makes one race the origin of several trios; all of them
        # have happened, so none may be reported as new.
        seen.update(podium_trios(r))
```

This also removes a latent bug in the old code, where `seen.add(trio_key(r[s]...))` reused the loop variable `s` leaking from the line above it.

- [ ] **Step 4: Credit co-drivers in the other three scripts**

In `src/compute/compute_soulmates.py`, add `from compute.shared_drives import podium_drivers  # noqa: E402` and replace both podium loops. The totals loop:

```python
    for r in races:
        for d in podium_drivers(r):
            totals[d["name"]] += 1
            podium_years[d["name"]].append(int(r["season"]))
```

and the pair-matrix loop's name extraction:

```python
    for r in races:
        year = int(r["season"])
        names = [d["name"] for d in podium_drivers(r) if d["name"] in top_set]
```

In `src/compute/compute_overdue.py` and `src/compute/compute_unlikeliest.py`, add the same import and replace each script's identical counting loop:

```python
    for r in podiums:
        for d in podium_drivers(r):
            podium_count[d["driverId"]] += 1
            name_by_id[d["driverId"]] = d["name"]
```

- [ ] **Step 5: Regenerate and verify**

```bash
python src/compute/compute_soulmates.py
python src/compute/compute_overdue.py
python src/compute/compute_unlikeliest.py
python src/compute/compute_podigami.py
PYTHONPATH=src python -m datalib.validate
PYTHONPATH=src python -m pytest -q
```

Expected: validation clean, full suite PASS. `compute_podigami.py` rewrites numeric fields it always rewrites (the constructor-overlay churn documented in `CLAUDE.md`) — expected, not a regression.

- [ ] **Step 6: Confirm the newly-credited drivers**

```bash
PYTHONPATH=src python -c "
import json
from collections import Counter
from compute.shared_drives import podium_drivers
c = Counter(d['driverId'] for r in json.load(open('data/podiums.json')) for d in podium_drivers(r))
print({k: c[k] for k in ('portago','ayulo','bettenhausen','moss','trintignant')})
"
```

Expected: `{'portago': 1, 'ayulo': 1, 'bettenhausen': 1, 'moss': 24, 'trintignant': 9}`.
Trintignant is 9, not 10: he held both P2 and P3 in the 1955 Argentine Grand Prix,
and `podium_drivers` dedupes by driver within a race, so that is one podium. The three new drivers legitimately stay out of the top-40 soulmates chart.

- [ ] **Step 7: Lint and commit**

```bash
python -m ruff check . && python -m ruff format .
git add src/compute tests/test_compute_podigami.py data/podigami.json data/soulmates.json data/overdue.json data/unlikeliest.json
git commit -m "feat(compute): credit shared-drive co-drivers across every stage"
```

---

### Task 6: Mark shared drives on the combinations page

**Files:**
- Modify: `src/build/build_combos_html.py:62-135` and `main`
- Modify: `assets/combos.css`
- Test: `tests/test_build_combos.py`

**Interfaces:**
- Consumes: `data/podiums.json` (already loaded in `main` for `total_podiums`).
- Produces: `render_race_pills(races, links=None, shared=None)` and `render_combo(rank, combo, links=None, shared=None)`, where `shared` is `{(season, round): "Stirling Moss"}` — co-driver names joined with `", "`.

**Why derived at render time:** `Combo.races` is `list[RaceRef]`, shared with `firstRace`/`lastRace`. An optional field there would serialise `"shared": null` onto thousands of entries in the 490 KB `combos.json`. The builder already loads `podiums.json`, so the marker costs nothing and keeps one source of truth.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_build_combos.py`:

```python
def test_shared_drive_race_pill_names_the_co_driver():
    from datalib import RaceRef

    from build.build_combos_html import render_race_pills

    races = [RaceRef(season="1956", round="4", raceName="Belgian Grand Prix")]
    out = render_race_pills(races, None, {("1956", "4"): "Stirling Moss"})
    assert "race-pill-shared" in out
    assert "shared car with Stirling Moss" in out


def test_normal_race_pill_has_no_shared_marker():
    from datalib import RaceRef

    from build.build_combos_html import render_race_pills

    races = [RaceRef(season="2021", round="21", raceName="Saudi Arabian Grand Prix")]
    out = render_race_pills(races, None, {})
    assert "race-pill-shared" not in out
    assert "shared car" not in out
```

- [ ] **Step 2: Run it to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_build_combos.py -k shared -v`

Expected: FAIL — `TypeError: render_race_pills() takes from 1 to 2 positional arguments but 3 were given`.

- [ ] **Step 3: Thread the marker through `render_race_pills`**

Replace `render_race_pills` in `src/build/build_combos_html.py`:

```python
def render_race_pills(
    races: list[RaceRef],
    links: dict | None = None,
    shared: dict[tuple[str, str], str] | None = None,
) -> str:
    """Group races by season; each season gets a row with year + race pills.

    ``shared`` maps (season, round) to the co-driver names for the pre-1961
    races where a podium car was shared, so the pill can say whose drive it was.
    """
    import html

    links = links or {}
    shared = shared or {}
    races_sorted = sorted(races, key=lambda r: (int(r.season), int(r.round)))
    parts: list[str] = []
    for season, group in itertools.groupby(races_sorted, key=lambda r: r.season):
        group_list = list(group)
        pill_parts: list[str] = []
        for r in group_list:
            co = shared.get((r.season, r.round))
            cls = "race-pill race-pill-shared" if co else "race-pill"
            title = f"{r.season} {r.raceName} — race report"
            if co:
                title = f"{title} (shared car with {co})"
            mark = '<span class="shared-mark" aria-hidden="true">&#8644;</span>' if co else ""
            pill_parts.append(
                f'<a class="{cls}" href="{html.escape(race_url(links, r.season, r.round, r.raceName), quote=True)}"'
                f' target="_blank" rel="noopener"'
                f' title="{html.escape(title, quote=True)}">'
                f'<span class="round">R{html.escape(r.round)}</span>'
                f"{html.escape(short_race_name(r.raceName))}"
                f"{mark}"
                f"</a>"
            )
        ct = len(group_list)
        ct_html = f'<span class="ct">x{ct}</span>' if ct > 1 else ""
        parts.append(
            f'<div class="season-row">'
            f'<div class="season-label">{html.escape(season)}{ct_html}</div>'
            f'<div class="race-list">{"".join(pill_parts)}</div>'
            f"</div>"
        )
    return "".join(parts)
```

- [ ] **Step 4: Add the badge to `render_combo`**

Change the signature and add the badge:

```python
def render_combo(
    rank: int,
    combo: Combo,
    links: dict | None = None,
    shared: dict[tuple[str, str], str] | None = None,
) -> str:
    import html

    shared = shared or {}
```

After `n = combo.count`, add:

```python
    is_shared = any((r.season, r.round) in shared for r in combo.races)
    badge = (
        '<span class="shared-badge" title="One podium step was a car shared by two drivers">'
        "&#8644;</span>"
        if is_shared
        else ""
    )
```

Then change the drivers cell and the detail row:

```python
        f'<td class="drivers">{drivers_html}{badge}</td>'
```

```python
        f'<div class="detail-inner">{render_race_pills(combo.races, links, shared)}</div>'
```

- [ ] **Step 5: Build the map in `main`**

In `main`, after `podiums` is loaded (near `total_podiums = len(podiums)`), add:

```python
    # Pre-1961 races where a podium car was shared. Derived here rather than
    # stored on Combo: RaceRef is reused for firstRace/lastRace, so an optional
    # field would write "shared": null onto every race entry in combos.json.
    shared = {
        (p.season, p.round): ", ".join(
            d.name for slot in ("p1", "p2", "p3") for d in ((p.coDrivers or {}).get(slot) or [])
        )
        for p in podiums
        if p.coDrivers
    }
```

and pass it through:

```python
    rows_html = "\n".join(render_combo(i, c, links, shared) for i, c in enumerate(combos, 1))
```

- [ ] **Step 6: Run the tests**

Run: `PYTHONPATH=src python -m pytest tests/test_build_combos.py -v`

Expected: PASS, including the pre-existing tests.

- [ ] **Step 7: Style the marker**

Append to `assets/combos.css`:

```css
/* Shared-drive podiums: pre-1961 races where two drivers shared one car, so a
   single podium step belongs to both of them. */
.shared-badge,
.shared-mark {
  margin-left: 0.35em;
  font-size: 0.85em;
  color: var(--muted);
  cursor: help;
}

.race-pill-shared {
  border-style: dashed;
}
```

Check that `--muted` is defined in `assets/style.css`. If the token is named differently there, use the existing name — do not introduce a new one.

- [ ] **Step 8: Build and check the real page**

```bash
python src/build_site.py
grep -o 'shared-badge' dist/combos.html | wc -l
grep -o 'race-pill-shared' dist/combos.html | wc -l
```

Expected exactly **40** badges and **42** shared pills (40 combos touch a shared-drive race; two of them touch two). A different number means the map keys or the trio expansion disagree — investigate rather than adjusting the expectation.

- [ ] **Step 9: Lint, test and commit**

```bash
python -m ruff check . && python -m ruff format .
PYTHONPATH=src python -m pytest -q
git add src/build/build_combos_html.py assets/combos.css tests/test_build_combos.py
git commit -m "feat(combos): mark podiums won by a shared car"
```

---

### Task 7: Stacked podium step and the FAQ entry

**Files:**
- Modify: `src/build/build_podigami_html.py:249-265`
- Modify: `assets/podigami.css`
- Test: `tests/test_build_podigami.py`

**Interfaces:**
- Consumes: `slot_drivers` (Task 3).
- Produces: `render_last_race_drivers(pod: dict, constructor_map: dict, meta: dict) -> str`.

**Note:** the last-race card always shows a current race, so the stacked step is dormant by design — it exists so a future shared drive renders correctly instead of silently dropping a driver. The FAQ entry is the part users see today.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_build_podigami.py`:

```python
def test_last_race_step_renders_both_drivers_of_a_shared_car():
    """Dormant today (the last race is always modern) but must not silently
    drop a driver if a podium step is ever shared again."""
    from build.build_podigami_html import render_last_race_drivers

    pod = {
        "p1": {"driverId": "collins", "name": "Peter Collins"},
        "p2": {"driverId": "frere", "name": "Paul Frère"},
        "p3": {"driverId": "perdisa", "name": "Cesare Perdisa"},
        "coDrivers": {"p3": [{"driverId": "moss", "name": "Stirling Moss"}]},
    }
    out = render_last_race_drivers(pod, {}, {})
    assert out.count("lr-driver") == 4
    assert "lr-shared" in out


def test_last_race_step_is_unchanged_for_a_normal_podium():
    from build.build_podigami_html import render_last_race_drivers

    pod = {
        "p1": {"driverId": "hamilton", "name": "Lewis Hamilton"},
        "p2": {"driverId": "max_verstappen", "name": "Max Verstappen"},
        "p3": {"driverId": "bottas", "name": "Valtteri Bottas"},
    }
    out = render_last_race_drivers(pod, {}, {})
    assert out.count("lr-driver") == 3
    assert "lr-shared" not in out
```

- [ ] **Step 2: Run it to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_build_podigami.py -k last_race_step -v`

Expected: FAIL — `ImportError: cannot import name 'render_last_race_drivers'`.

- [ ] **Step 3: Extract and extend the step renderer**

In `src/build/build_podigami_html.py`, add the import:

```python
from compute.shared_drives import slot_drivers  # noqa: E402
```

Add this function above the builder that currently inlines the loop:

```python
def render_last_race_drivers(pod: dict, constructor_map: dict, meta: dict) -> str:
    """The three podium steps of the last race.

    A step held by a car two drivers shared renders both of them inside that one
    step, marked as shared — the podium stays three steps tall. Dormant for
    modern races; the last shared drive was the 1960 Argentine Grand Prix.
    """
    steps: list[str] = []
    for pos in (1, 2, 3):
        spans = []
        for d in slot_drivers(pod, f"p{pos}"):
            entry = {
                "name": d["name"],
                "driverId": d["driverId"],
                "constructorId": constructor_map.get(d["driverId"], ""),
            }
            v = driver_view(entry, meta)
            spans.append(
                f'<span class="lr-driver" style="--team:{v["color"]}">'
                f'<span class="cd-dot"></span>'
                f'<span class="lr-code">{esc(v["code"])}</span>'
                f"</span>"
            )
        if len(spans) > 1:
            steps.append(
                '<span class="lr-step lr-shared" title="One car, shared by both drivers">'
                + "".join(spans)
                + "</span>"
            )
        else:
            steps.append(spans[0])
    return '<span class="lr-sep">/</span>'.join(steps)
```

Replace the inlined `drivers_html` loop and the `trio_html` join at lines 251-265 with a single call:

```python
    trio_html = render_last_race_drivers(pod, constructor_map, meta)
```

`trio_ids` and `trio_names` above it stay exactly as they are — the combo lookup deliberately uses the primary trio.

- [ ] **Step 4: Run the tests**

Run: `PYTHONPATH=src python -m pytest tests/test_build_podigami.py -v`

Expected: PASS, including the existing last-race assertions.

- [ ] **Step 5: Style the shared step**

Append to `assets/podigami.css`:

```css
/* A podium step held by one car that two drivers shared (pre-1961 only). */
.lr-step.lr-shared {
  display: inline-flex;
  flex-direction: column;
  gap: 0.15em;
  padding-left: 0.4em;
  border-left: 2px solid var(--muted);
  cursor: help;
}
```

- [ ] **Step 6: Add the FAQ entry**

Find the FAQ list in `src/build/build_podigami_html.py` (search for an existing question string) and add one entry matching the surrounding structure exactly — including its JSON-LD `FAQPage` counterpart if the existing entries feed one.

- **Question:** `Why do some 1950s podiums list four drivers?`
- **Answer:** `Until 1960 a driver could hand his car to a team-mate mid-race, and both were classified at the finishing position. The 1956 Belgian Grand Prix is the clearest case: Cesare Perdisa and Stirling Moss shared the third-placed Maserati, so that race put two different trios on the podium at once. Eighteen races in history work this way, and every trio they produced counts as having happened.`

- [ ] **Step 7: Build, verify, lint and commit**

```bash
python src/build_site.py
grep -c "four drivers" dist/index.html
python -m ruff check . && python -m ruff format .
PYTHONPATH=src python -m pytest -q
git add src/build/build_podigami_html.py assets/podigami.css tests/test_build_podigami.py
git commit -m "feat(landing): render shared podium steps and explain them in the FAQ"
```

Expected: `grep` returns at least 1; full suite PASS.

---

### Task 8: Full-pipeline verification and documentation

**Files:**
- Modify: `README.md`
- Modify: `RELEASE_NOTES.md`

- [ ] **Step 1: Rebuild everything from committed data and validate**

```bash
python src/build_site.py
PYTHONPATH=src python -m datalib.validate
python -m ruff check .
python -m ruff format --check .
PYTHONPATH=src python -m pytest -q
```

Expected: all clean. Record the final test count — the README quotes it.

- [ ] **Step 2: Confirm the data is a fixed point**

Regenerating must not churn the committed files:

```bash
python src/compute/count_combos.py
python src/compute/compute_soulmates.py
python src/compute/compute_overdue.py
python src/compute/compute_unlikeliest.py
git status --porcelain data/
```

Expected: `combos.json`, `soulmates.json`, `overdue.json` and `unlikeliest.json` show **no** modification. (`podigami.json` is excluded — it rewrites constructor-overlay numbers by design.) A dirty file means the compute output is not a fixed point of its schema, which is the #178 stall class; stop and fix it before shipping.

- [ ] **Step 3: Check the rendered page in a browser**

Run: `python -m http.server 8000 --directory dist`

Open `http://localhost:8000/combos.html`, search for `Collins`, and confirm:
- both `Collins / Frère / Moss` and `Collins / Frère / Perdisa` are listed, each with the `⇄` badge;
- expanding either shows a dashed 1956 Belgian GP pill whose tooltip reads "shared car with Stirling Moss";
- at the 600 px mobile breakpoint the badge does not push the drivers cell into a wrap.

- [ ] **Step 4: Update the README**

Update every place the README states a combination count, a driver-trio total, or a test count. Add a sentence to the data/architecture section noting that a pre-1961 race whose podium included a shared car contributes more than one trio, so combo counts sum to more than the number of races.

- [ ] **Step 5: Update `RELEASE_NOTES.md`**

Add under today's `## YYYY-MM-DD` heading (create it if absent):

```markdown
### Fixes

- Credit both drivers when a podium car was shared — 18 pre-1961 races only counted the first-classified driver, hiding 20 real driver trios and three drivers' only podiums (#PR)
```

Replace `#PR` with the real number once the PR exists.

- [ ] **Step 6: Commit**

```bash
git add README.md RELEASE_NOTES.md
git commit -m "docs: note shared-drive podiums in the README and release notes"
```

- [ ] **Step 7: Open the PR into `develop`**

```bash
gh pr create --base develop --title "Credit both drivers when a podium car was shared" --body "$(cat <<'BODY'
## Summary

Before 1961 two or three drivers routinely shared one car during a Grand Prix and were all classified at that car's finishing position. `fetch_podiums.py` kept only the first driver at each position, so 18 races were recorded with a driver missing from the podium.

## Changes

- `Podium` gains an optional `coDrivers` map; `fetch_podiums.py` records it, and `--backfill-shared` fills history from the committed `race_results.json` (no full re-fetch).
- New `src/compute/shared_drives.py` owns the expansion rule: a shared step means a race produced several distinct trios, never a four-driver combo. Products naming a driver twice are discarded, which is what keeps the 1955 Argentine GP honest.
- Combos, podigami, soulmates, overdue and unlikeliest all credit co-drivers: 734 → 754 unique combos, and Portago, Ayulo and Bettenhausen enter the dataset with their only podium.
- `combos.html` marks affected rows and race pills; the last-race card learns the stacked-step markup; a new FAQ entry explains it.

20 trios the site listed as never-having-happened did in fact happen — `collins / frere / moss` (1956 Belgium) among them.

## Testing

`pytest -q`, `ruff check .`, `ruff format --check .`, `python -m datalib.validate`, and a local `dist/` preview of `combos.html` at desktop and 600 px.

## Checklist

- [x] Lint and format pass
- [x] Tests pass
- [x] `RELEASE_NOTES.md` updated
- [x] `README.md` updated
- [x] No security issues introduced
BODY
)"
```

---

## Rollback

Every task commits independently. The data changes are reproducible from the committed `race_results.json`, so reverting the code commits and re-running `count_combos.py` restores the previous datasets exactly. Nothing here touches `model_eval.json` or the backtest.
