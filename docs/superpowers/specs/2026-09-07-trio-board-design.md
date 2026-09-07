# Trio board: show already-happened trios alongside new ones

**Date:** 2026-09-07
**Status:** Approved

## Problem

The landing page's `Most likely new trios` panel lists only trios that have
*never* happened. A visitor looking at it cannot tell whether a trio they have
in mind is missing because it already happened or because the model rates it as
too unlikely to make the top twelve. Those are opposite facts and the page
gives no way to distinguish them.

nflscorigami.com solves the same problem by showing the whole board — every
plausible score — and marking which cells are new. This spec brings that
treatment to the podium trios.

## Solution

The panel becomes **`Most likely trios`**: one merged, ranked board of every
trio the model rates as a live chance at the next race, with the
never-happened ones highlighted and the already-happened ones carrying their
history.

- Already-happened rows are **muted** — dimmed TLA codes, grey bar.
- Never-happened rows stay full contrast: accent bar plus a small `NEW` pill.
- Hovering (desktop) or tapping (mobile) a done row opens a floating bubble:
  *"Happened 3 times · Last: 2026 Austrian Grand Prix · See all →"*, linking to
  that trio's filtered view on `combos.html`.
- New rows are **not** interactive. They have no history to reveal, so
  hoverability itself becomes the signal that a row has one.
- The card shows **12 rows at a time** and scrolls, with a fade at the bottom
  edge while more rows remain below.

Untouched: the hero, the `chance the next race delivers a brand-new trio`
figure, the driver-form tower, and every other panel.

## Where the data comes from

**No model change.** `model_v2.predict_race()` already computes exact
probabilities for every already-happened trio reachable with the current grid
(`trio_probs`, which tracks all of `seen_here`) and discards them when it
returns only `ranked_new`. This feature stops discarding them.

Same deterministic simulation, same seed, same `candidates`, same
`chanceNextRaceNew`. **Zero backtest impact** — `backtest.py` does not read the
board.

### Board membership rule

Include every trio at **≥ 1.00%**, ordered by probability descending.

The rule is self-adjusting in a way a fixed row count is not: after qualifying,
the grid sharpens the odds and the tail genuinely stops mattering, so the board
shortens on its own. Measured against committed data at the Dutch GP `asOf`:

| board | rows at ≥1% | new | done | last row | first excluded |
|---|---|---|---|---|---|
| pre-quali | 27 | 11 | 16 | 1.09% | 0.99% |
| post-quali (Italian GP) | 21 | 9 | 12 | 1.09% | 0.93% |

Two guards keep a data-driven length predictable:

- **Floor: 12 rows.** In a dominant era the probability mass can concentrate
  hard enough that fewer than a dozen trios clear 1%. Showing eight rows would
  be correct but would leave the card looking half-built and would show less
  than the panel does today.
- **Cap: 40 rows.** Probabilities sum to 1, so at most 100 trios can ever clear
  1%; the cap can only bind if the top trio falls below ~2.5%, which no
  plausible grid produces. It exists to bound the dataset, not because it is
  expected to fire.

### Known approximation (pre-existing, not introduced here)

`predict_race` tracks every already-happened trio exactly, but screens *unseen*
trios to the top 250 ranked at the mean. A trio could in principle clear 1% in
simulation while sitting outside that screen and so be missed from the board.

Today's top-12 new list is built from the very same screened set, so the board
inherits this approximation rather than adding one. Recorded here so it is not
rediscovered as a bug.

## Data contract

`podigami.json` gains **`trioBoard`** at the top level and inside `postQuali`:

```json
"trioBoard": [
  {"driverIds": ["antonelli", "leclerc", "russell"], "prob": 6.295, "happened": true},
  {"driverIds": ["antonelli", "piastri", "russell"], "prob": 3.815, "happened": false}
]
```

Deliberately light — roughly 2 KB per block against a 316 KB file — because the
heavy per-driver data already exists in `driverForm`, and the history already
exists in `combos.json`. The builder joins to both.

`candidates` is **unchanged** (12 entries, new-only, full `perDriver`) and keeps
driving the hero.

Two properties this shape buys:

- **Correct by construction.** Merging a capped new-list with a capped seen-list
  inside the builder would be subtly wrong whenever more than 12 new trios land
  above the 1% line — which happens today (11 new, and the pre-quali board has
  reached 11 of 12 already). Compute merges where the full ordering is known.
- **No duplicated history.** Count and last race come from `combos.json` via the
  builder's existing `_lookup_combo()`.

### `trioBoard` must be optional, defaulting to `[]`

This is a deployment constraint, not defensive habit.

`deploy.yml` builds `main` from *committed* data, and per `CLAUDE.md` a
promotion's three-way merge keeps `main`'s newer `data/`. A regenerated
`podigami.json` shipped from `develop` will therefore most likely be discarded
at promotion. The live site runs on a `trioBoard`-less file from the moment of
promotion until the next automated data update lands.

So: the schema field is optional with an empty default, and
`render_candidates()` falls back to today's new-only list when the board is
empty. A required field, or a builder that assumes the key, means a broken or
empty panel during that window.

## Components

### `src/compute/compute_podigami.py`

New module-level constants and one pure function:

```python
BOARD_MIN_PROB = 0.01   # include every trio at >= 1%
BOARD_MIN_ROWS = 12     # floor, so the card is never half-built
BOARD_MAX_ROWS = 40     # bound the dataset; not expected to bind

def build_trio_board(trio_probs, seen, entrants) -> list[dict]
```

`build_trio_board` takes the raw `trio_probs` map, the global `seen` set and the
entrant list; derives `seen_here`; ranks; applies the rule and guards; and
returns board rows. It is called from three places, all of which already hold a
`trio_probs` map:

1. the pre-quali v2 path,
2. `_post_quali_block` (grid-aware, from its own `predict_race` output),
3. the v1 fallback path, whose `model.all_set_probs()` result is a complete
   trio→probability map and needs no special casing.

### `src/datalib/schemas.py`

```python
class TrioBoardEntry(_Base):
    driverIds: list[str]
    prob: float
    happened: bool
```

Added to `Podigami` and `PodigamiPostQuali` as `trioBoard: list[TrioBoardEntry] = []`,
declared after `candidates` so the canonical serialization stays readable.

### `src/build/build_podigami_html.py`

`render_candidates()` gains `board`, `driver_form` and `combos` parameters. When
`board` is empty it renders exactly what it renders today, so the signature
change is backwards compatible and the deployment-window fallback is the same
code path as the pre-feature behaviour.

Per-driver display for a board row resolves by `driverId` against
`driver_form` (which carries `name`, `constructorId`, `constructor` and, post
qualifying, `gridPosition` for every entrant), falling back to `meta` and then
to the id itself. History resolves through the existing `_lookup_combo()`, and
the bubble's link through the existing `combos_link()`.

A done row whose combos lookup misses renders as done with no bubble rather
than failing the build — the two datasets are derived from the same podiums
file, so a miss means an upstream inconsistency, not a page that should break.

### `assets/podigami.css`

`.cand` grows `.cand-done` / `.cand-new` variants rather than becoming a new
component. New: `.cand-scroll` (the `max-height` window, driven by a
`--board-rows` custom property so the visible count is one number to tune),
its bottom fade, `.cand-pill` for the `NEW` badge, and `.trio-tip` /
`.trio-bubble`.

### `assets/podigami.js`

A self-contained module for `.trio-tip`. It does **not** reuse the `.info-tip`
class: a floating popover is clipped by an `overflow-y: auto` ancestor, so row
bubbles are `position: fixed` with coordinates set from the row's
`getBoundingClientRect()` and clamped into the viewport. Because visibility is
JS-driven, hover, focus, tap, outside-click, Escape and close-on-scroll all live
in one module instead of being split across two handlers with different
positioning assumptions.

Screen readers get the history through an `aria-label` on the row, so no
sr-only markup is needed. Without JS the bubble does not open; rows still read
correctly as done or new, which is acceptable degradation for an enhancement.

## Testing

- `tests/test_compute_podigami.py` — board ordered by probability descending;
  `happened` agrees with `seen`; the 1% rule, the floor and the cap; the
  post-quali board is grid-aware; the v1 fallback path produces a board.
- `tests/test_datalib.py` — `trioBoard` round-trips byte-identically, and a
  payload omitting it still loads and re-serializes.
- `tests/test_build_podigami.py` — done vs. new row markup; the bubble carries
  count, last race and a `combos.html` link; new rows carry no bubble; an empty
  board falls back to today's new-only list; a done row with no combos match
  degrades instead of raising.
- `tests/test_build_output.py` — update the two assertions that reference the
  string `"Most likely new trios"`.
- `tests/test_mobile_css.py` — the scroll window and fade survive the mobile
  breakpoint.

## Out of scope

- Any change to the model, its parameters, the backtest or the acceptance gate.
- Any change to `combos.html`, `overdue.html`, `unlikeliest.html` or
  `soulmates.html`.
- Exhaustive trio lookup. The board covers the likely region; `combos.html`
  remains the place to answer "has *this* trio ever happened" in general.
