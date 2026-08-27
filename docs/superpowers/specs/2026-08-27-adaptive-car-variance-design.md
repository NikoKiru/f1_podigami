# Adaptive constructor variance (model v2)

**Date:** 2026-08-27
**Status:** design approved, pending experiment

## Problem

After the 2026 Hungarian and Dutch Grands Prix — Norris on pole and winning both —
the landing page still ranked Leclerc ahead of him (worth 50,131 vs 47,013).
The model reacted in the right direction (Norris +61% and McLaren's car strength
0.545 → 0.619 across R10→R12) but not far enough to reorder the pair.

The obvious lever is `tau_con`, the per-race diffusion of the constructor state:
raise it and the model forgets older races faster. A sweep confirms the lever
works and shows it is the wrong one.

### Diagnostic (measured 2026-08-27, data at 2026 R12)

Current ratings under varying `tau_con`:

| `tau_con` | 3rd | 4th |
|---|---|---|
| 0.08 (current) | Leclerc 0.470 | Norris 0.441 |
| 0.12 | Leclerc 0.469 | Norris 0.464 |
| 0.15 | **Norris 0.488** | Leclerc 0.467 |
| 0.22 | Norris 0.562 | Leclerc 0.454 |
| 0.30 | degenerate — mu explodes to +66, 34 log-units of spread |

Cost on the frozen 2019–2026 test window:

| `tau_con` | logLoss ↓ | brierNew ↓ | top1 ↑ | top3 ↑ |
|---|---|---|---|---|
| 0.04 | 3.9133 | 0.2355 | 0.185 | 0.352 |
| **0.08** | **3.9115** | **0.2384** | 0.179 | 0.352 |
| 0.12 | 3.9167 | 0.2424 | 0.167 | 0.333 |
| 0.15 | 3.9254 | 0.2455 | 0.154 | 0.333 |
| 0.22 | 3.9874 | 0.2569 | 0.148 | 0.327 |

Every metric degrades monotonically above 0.08. The value that flips the
Norris/Leclerc pair costs ~14% relative on top-1 trio accuracy over eight years
of held-out racing. Meanwhile the validation objective is nearly flat
(4.3988–4.4095 across a 5x range), which is why the tuner settled on 0.08
without much conviction.

Note also that the model does not disagree as strongly as the page implies:
0.470 vs 0.441 is a 6% gap against ±0.38 uncertainty on each — a coin flip
rendered as a confident ranking. That presentation issue is real but **out of
scope here** (see Non-goals).

## Approach

`tau_con` is blunt: it forgets everything faster, every race, whether or not
anything changed. The narrower mechanism is **adaptive diffusion** — forget
faster only when a car has demonstrably changed.

The discriminator is *signed* drift. Each race `observe_order` hands every
constructor a summed gradient `g` and Hessian `h`, and `_nudge` moves its mean
by `var*kappa*g/denom`. That per-race mean movement is the innovation:

- **Noise** (a wet race, a safety car, a bad strategy call) pushes the mean one
  way then the other — it cancels in a signed average.
- **A real form change** (a working upgrade package) pushes it the same way
  race after race — it accumulates.

### Mechanism

`RatingEngine` gains one float per constructor: `_con_drift[root]`, an EWMA of
signed mean movement with half-life `con_adapt_hl` races, accumulated in the
constructor loop of `observe_order`.

`advance_race` replaces the flat step:

```
effective_var_step = tau_con**2 * (1 + con_adapt_gain * (s_c / tau_con)**2)
```

clamped to `ADAPT_CEIL = 8.0` x `tau_con**2`, so aggressive drift cannot reach
the runaway regime observed at `tau_con` 0.30.

Worked example: McLaren's flat R1–R10 leave `s_c` near zero and the car
diffuses exactly as today. Hungary and Zandvoort push the mean up twice
consecutively, `s_c` grows, McLaren's variance inflates, and the next race's
evidence moves the belief further than it otherwise would. Ferrari, drifting
gently downward without a consistent shove, keeps its normal diffusion.

### Required properties

1. **`con_adapt_gain = 0` reproduces the current model exactly.** The `s_c`
   term vanishes and the arithmetic is unchanged. This gives a free ablation
   rung, a free acceptance-gate baseline, and a one-knob rollback.
2. **Determinism preserved.** No sampling; one float of state per constructor.
   Same inputs produce byte-identical JSON, which the data-update automation
   depends on.
3. **Conditional, not global.** The intuition "a car is only as good as its last
   race" applied where it is warranted, rather than as a permanent tax.

## Validation

### Tuning — validation window only

Two knobs enter `V2_TUNE_GRID`:

```python
"con_adapt_gain": [0.0, 0.25, 0.5, 1.0, 2.0],
"con_adapt_hl":   [2.0, 4.0, 8.0],
```

Coordinate descent on 2010–2018 against the existing `v2_objective`
(trio logLoss + novelty logLoss). Nothing about 2019+ informs the choice.

### Acceptance gate — frozen test window, examined once

New rung pair in `RUNGS_V2`:

```python
("v2 full",          {"con_adapt_gain": 0.0}),  # today's model - gate baseline
("v2 +adaptive car", {}),                       # tuned knobs
```

The adaptive rung is chosen only if it beats gain-0 on test **logLoss AND
brierNew**, mirroring the existing v1-vs-v2 and ratings-vs-grid gates. Winning
one and losing the other means `con_adapt_gain` stays 0 and the mechanism ships
dormant.

### Pre-registered honesty constraints

- **The validation window may have no opinion.** The `tau_con` sweep moved the
  val objective 0.2% across a 5x range; val barely discriminates recency knobs.
  Coordinate descent selecting `gain = 0.0` is a legitimate outcome and will be
  reported as such, not overridden.
- **Do not tune against the test window, and do not tune against Norris.**
  2026 R11–R12 motivated the work, which makes it exactly the case we must not
  optimise for. The Norris/Leclerc ordering is a **sanity check to report**, not
  a target. If the tuned model still ranks Leclerc ahead, the answer to the
  original question becomes "the model is right and two races is not enough."

## Integration

| File | Change |
|---|---|
| `src/compute/model_v2.py` | `_con_drift` EWMA on `RatingEngine`; accumulate in `observe_order`; consume in `advance_race`; two knobs in `DEFAULT_PARAMS_V2` |
| `src/compute/backtest.py` | `V2_TUNE_GRID` entries; gain-0 / adaptive rung pair; acceptance gate |
| `src/datalib/schemas.py` | Two **optional, defaulted** fields on `PodigamiParamsV2` |
| `tests/test_model.py` | Gain-0 equivalence; noise cancellation; drift accumulation + ceiling |
| `RELEASE_NOTES.md`, `README.md` | Per repo rules |

### Hazard: the #178 silent-stall class

`compute_podigami.py:521` splats params wholesale
(`{"model": "dbpl-v2", **v2["params"], ...}`) and `PodigamiParamsV2` inherits
`_Base` with `extra="forbid"`. The moment a new knob enters `DEFAULT_PARAMS_V2`,
`podigami.json` carries a key the schema rejects: `datalib.validate` fails, the
round-trip test fails, the `auto/update-data` PR goes red, and the site freezes
one race behind until a human reads the alert issue.

Mitigations:

1. **Schema and compute change land in one atomic commit**, never split across PRs.
2. **The new fields are optional with defaults** (`con_adapt_gain: float = 0.0`),
   following the existing `chosenModel: str | None = None` precedent. This is
   load-bearing for the promotion merge: `main` carries a `podigami.json`
   computed under the old params, and a `develop -> main` three-way merge keeps
   `main`'s newer data. Required fields would make that committed file fail
   validation the instant the promotion lands, breaking the deploy.
3. The PR recomputes and commits `data/podigami.json` and `data/model_eval.json`
   so committed data is already a fixed point of the new schema.
4. `PYTHONPATH=src python -m datalib.validate` and full `pytest -q` before the PR opens.

### Tests

1. **Gain-0 equivalence** — a `HistoryFilter` at `con_adapt_gain=0` produces
   bit-identical states to one built from unmodified `DEFAULT_PARAMS_V2`. This
   is the regression net: it fails loudly if the mechanism leaks into the
   default path.
2. **Noise cancels** — alternating symmetric orders leave `s_c` near 0 and the
   variance step at `tau_con**2`.
3. **Drift accumulates and clamps** — a car climbing the order every race gets a
   strictly larger variance step, ceiling-limited at 8x.

## Non-goals

- The driver-side equivalent (`tau_drv`).
- Fixing the page's presentation of a 6% gap as a confident ranking. Real and
  worth doing, but a separate change with a separate rationale; bundling would
  muddy whether this model change earned its place.

## Outcome either way

Pass: the model reacts properly to genuine form changes from here on.
Fail: we have learned that 12 races of 2026 do not outweigh eight years of
held-out racing, and `tau_con` stays at 0.08 with a documented reason.
