# Shared-drive podiums

**Date:** 2026-08-27
**Status:** Approved, ready for planning

## Problem

Between 1950 and 1960 it was routine for two (occasionally three) drivers to
share a single car during a Grand Prix. Both are classified at the same
finishing position, so a podium step can be held by more than one driver — the
1956 Belgian Grand Prix was won by Collins ahead of Frère, with Perdisa **and**
Moss third in a shared Maserati.

`src/fetch/fetch_podiums.py` keeps only the first driver the API lists at each
position:

```python
entry[f"p{position}"] = driver_record(results[0])
```

Everything downstream reads those three single-driver slots, so the site
presents an incomplete picture of history.

### Measured scope

`data/race_results.json` already carries the truth (both drivers, identical
`position`), so no historical re-fetch is required. Scanning it for duplicate
positions in the top three:

| | |
|---|---|
| Races with a shared car on the podium | 18 (all 1950–1960) |
| Drivers currently uncredited for a podium | 15 |
| Drivers with **zero** podiums on the site who have one | 3 — Ayulo, Bettenhausen, Portago |
| Trios the site says never happened that did | 20 |
| Real trios that boost an existing combo's count | 3 |

The affected races:

```
1950 R7  Italian        P2 serafini + ascari
1951 R2  Indianapolis   P3 mcgrath + ayulo
1951 R4  French         P1 fangio + fagioli, P2 gonzalez + ascari
1951 R7  Italian        P3 bonetto + farina
1953 R2  Indianapolis   P3 darter + hanks
1953 R3  Dutch          P3 gonzalez + bonetto
1954 R6  German         P2 hawthorn + gonzalez
1954 R8  Italian        P3 gonzalez + maglioli
1955 R1  Argentine      P2 farina + gonzalez + trintignant, P3 maglioli + farina + trintignant
1955 R2  Monaco         P3 perdisa + behra
1955 R3  Indianapolis   P2 paul_russo + bettenhausen
1956 R1  Argentine      P1 fangio + musso
1956 R2  Monaco         P2 fangio + collins
1956 R4  Belgian        P3 perdisa + moss
1956 R6  British        P2 collins + portago
1956 R8  Italian        P2 fangio + collins
1957 R5  British        P1 brooks + moss
1960 R1  Argentine      P3 moss + trintignant
```

**1955 Argentina is the hard case.** Farina and Trintignant each appear at
*both* P2 and P3, having shared two different cars in the same race. Any
expansion must refuse to emit a "trio" that names one driver twice.

## Decisions

1. **Combo identity stays a set of three drivers.** A shared step means the race
   produced several valid trios at once, not a wider podium. If Moss stood on
   the P3 step, `collins / frere / moss` genuinely happened and must not be
   listed as a podigami.
2. **The schema change is additive.** `p1/p2/p3` keep their single `DriverRef`
   (the first-classified driver); an optional `coDrivers` map carries the rest.
3. **The visible change is a marker on `combos.html`,** not a redrawn podium —
   see "Render" for why.
4. **Indianapolis 500 rounds are included.** They are championship rounds the
   site already counts; excluding them would be an inconsistency, not a fix.

## Design

### 1. Data contract

`datalib.schemas.Podium` gains:

```python
coDrivers: dict[str, list[DriverRef]] | None = None
```

keyed by slot (`"p1"`, `"p2"`, `"p3"`), present only on the 18 affected races:

```json
{
  "season": "1956", "round": "4",
  "raceName": "Belgian Grand Prix",
  "p1": {"driverId": "collins", "name": "Peter Collins"},
  "p2": {"driverId": "frere",   "name": "Paul Frère"},
  "p3": {"driverId": "perdisa", "name": "Cesare Perdisa"},
  "coDrivers": {"p3": [{"driverId": "moss", "name": "Stirling Moss"}]}
}
```

`fetch_podiums.py` stops discarding `results[1:]` and populates the map.

The other 1143 entries serialize byte-identically, so the `datalib` round-trip
test and the whole #178 stall class stay safe. Because the field is optional
and `save_*` writes the canonical schema form, an omitted `coDrivers` still
round-trips.

### 2. Compute

`count_combos.py` expands each race into the **set of distinct trios** from the
cartesian product of its three slots (each slot = primary + co-drivers),
discarding any product that names a driver twice and deduplicating the rest.
This is what makes 1955 Argentina work: the 3 × 3 product yields only the legal
trios. Each resulting trio records that race in its `races` list, tagged
`shared: true`.

Results:

- unique combos **734 → 754**
- 3 existing combos gain a count
- 20 trios stop being falsely listed as never-happened

`compute_soulmates.py`, `compute_overdue.py` and `compute_unlikeliest.py`
iterate co-drivers alongside the primary slots the same way, so Portago, Ayulo
and Bettenhausen enter the dataset with one podium each.

**Accepted consequence:** combo counts now sum to **1185 across 1161 races**.
`build_combos_html.py:152` prints that sum as "across N races", which becomes
wrong and must be reworded to use the race count, not the trio-instance count.

### 3. Render

The site never draws a historical race podium. The only place three podium
drivers appear together is the landing page's last-race card
(`build_podigami_html.py:249`), which always shows a current race;
`combos.html` draws the *trio* and lists its races as season-grouped pills
carrying no driver names. So the shared-step treatment has no historical
surface today, and the visible work is on `combos.html`:

- Combo rows whose podium came from a shared car get a `⇄` badge.
- The race pill for a shared-drive race carries a `title` naming the
  co-driver(s) — e.g. "shared car with Stirling Moss".
- The last-race card learns the stacked-step markup (both names inside one
  step, joined by a shared-car marker) so a future shared drive renders
  correctly. This is dormant by design.
- One FAQ entry on the landing page explains why a few 1950s podiums involve
  four drivers.

### 4. Tests

- 1956 Belgium yields both `collins/frere/perdisa` and `collins/frere/moss`.
- 1955 Argentina emits no trio naming a driver twice.
- A `coDrivers`-free podium still round-trips byte-identically through
  `datalib`.
- Data integrity: every `coDrivers` entry matches a duplicate position in
  `data/race_results.json`, and vice versa — no shared drive goes unrecorded.
- Existing `test_build_output` assertions updated for the new combo count.

## Out of scope

`model_v2` sorts race results by `position` and therefore breaks these 18
pre-1961 ties arbitrarily. Real, but negligible in effect, and changing it would
perturb the frozen backtest window for no measurable gain.

No re-fetch of historical seasons. A `--full` podiums fetch is hundreds of API
calls for data that is already committed, so the 18 races are backfilled
**locally from `race_results.json`** (a one-off script, or a `--backfill-shared`
flag on `fetch_podiums.py`) that fills `coDrivers` by matching duplicate
positions. `fetch_podiums.py` is still taught to populate the field from live
API responses so future races — and any `--full` rebuild — stay correct.
