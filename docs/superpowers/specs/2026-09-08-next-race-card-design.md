# Next-race card redesign — circuit plate + quiet countdown

**Date:** 2026-09-08
**Status:** approved (design), ready to implement
**Scope:** landing page only — `index.html`'s `.next-race` + `.last-race` block

## Problem

The block is informative but poorly proportioned, and nothing in it is wrong enough
to notice one thing at a time. Measured against the shipped render at 1280px and
390px:

1. **Desktop dead space.** The card is a `1fr minmax(120px, 200px)` grid; the track
   outline renders small and vertically centred inside that right column, leaving
   roughly 200px of empty card.
2. **No focal point.** Five stacked lines (tag, round, name, circuit, when) at five
   sizes. The live countdown — the only thing on the card that changes — renders at
   14px, the same size as the static date beside it.
3. **Orphaned status.** `.lr-status` carries `margin-left: auto`, so on a 1136px card
   the "Happened 4 times · last time …" text sits ~600px from the trio it describes.
4. **Mobile doodle.** At ≤600px the card collapses to one column and the track drops
   below the text as a small off-centre outline, costing ~90px of scroll before the
   prediction hero without conveying anything.
5. **Two clocks.** The race time is converted to the visitor's timezone by
   `podigami.js`; the qualifying line is server-rendered UTC and never converted.

## Decision

Keep every piece of information currently shown. Redistribute it so each column
earns its width, and promote the countdown without letting it fight the hero.

Three directions were mocked against the real stylesheets (see
`.superpowers/brainstorm/`): a countdown-led card with the track as a bleeding
watermark, a circuit-plate card, and a two-up shell pairing next race with last
race. The circuit plate was chosen as the smallest structural change that fixes
the proportion problem. A second pass on the countdown treatment settled on a
quiet number under a red label, because a 23px red countdown sits ~40px above the
hero's 60px red `43%` and the two compete.

## Design

### Layout

**Right column — circuit plate.** `.nr-art` becomes a framed surface (`--bg-2`
background, `--border` hairline, `--radius-sm`) containing the track at
`max-height: 106px` and a caption beneath it. Circuit name and length move out of
`.nr-circuit` and into that caption (`MADRING · 5.474 KM`, 10px, uppercase,
`--muted`). `.nr-circuit` keeps the locality and country only.

**Left column — countdown promoted.** `.nr-when` becomes a block containing, in
order:

- `.nr-cd-label` — 10px/700 uppercase, `--accent-bright`, text "Lights out in".
- `.nr-countdown` — 23px/800, `--text`, tabular numerals.
- `.nr-date` — 12.5px `--muted`, one line merging race and qualifying.

`.nr-quali` is retired; its content lives in `.nr-date`.

**Strip.** `.lr-status` loses `margin-left: auto` and follows the trio directly; a
flex spacer (`.lr-sp`, `flex: 1 1 auto`) absorbs the remaining width so the status
cannot drift. The wording tightens from `Happened 4 times · last time …` to
`4th time · last 2026 R8 · Austrian Grand Prix`.

### Behaviour (`assets/podigami.js`)

The existing block already reads `data-datetime` and rewrites `.nr-date` to local
time. Two additions:

- **Qualifying is converted too.** The section gains `data-quali-datetime`. The
  merged line is server-rendered in UTC; JS rewrites both halves to the visitor's
  timezone and ends the line with `(your time)`. When the race has no qualifying
  entry, only the race half is rendered.
- **The label must not contradict the slot.** Once the race starts, the countdown
  slot becomes `Lights out — race underway`, then `Awaiting results`. In that
  branch JS hides `.nr-cd-label` and adds a modifier that drops the countdown to a
  15px text style, since 23px/800 wraps badly.

### Edge cases

| Case | Behaviour |
|---|---|
| `trackPath` empty | `.nr-art` is omitted entirely; the card renders single-column and circuit name + length stay on `.nr-circuit` so they are never lost with the caption. |
| No `qualifyingDate` | Merged line renders the race half only. |
| Season complete | `.nr-empty` is untouched. |
| ≤600px | Card goes single-column; the plate flips to a row — 54px track plus a left-aligned caption, ~50px tall, replacing the ~90px outline. |

### Contrast

`--accent-bright` on this card's gradient measures 4.65:1 (dark) and 5.37:1
(light) at the darker end of the gradient, clearing 4.5:1 for the small bold
label in both themes. No new tokens; this is the same usage as the existing
`.nr-tag`.

## Discovered during implementation

The trio board's bubbles are `position: fixed`, which makes any transformed
ancestor their containing block — and `.reveal.reveal-in` transitions `transform`
for 0.5s as a panel scrolls into view. Hovering a row inside that window put the
bubble ~375px from its row. The card's new height moved the board past the point
where the e2e suite's travel test triggered it, so a pre-existing latent bug
surfaced as a failing test. Fixed in `place()` by measuring where the bubble
landed and correcting by the delta, which also covers the mask-image and filter
variants of the same trap.

## Files

- `src/build/build_podigami_html.py` — `render_next_race`, `render_last_race`
- `assets/podigami.css` — base rules plus the `max-width: 600px` block
- `assets/podigami.js` — local-time conversion and countdown label states
- `tests/test_next_race.py`, `tests/test_build_output.py`, `tests/test_mobile_css.py`
- `RELEASE_NOTES.md`

## Out of scope

- Adding new statistics to the card (podigami drought counters, per-circuit
  new-trio rates). The block's information stays exactly as it is.
- The two-up shell that pairs next race with last race — mocked, not chosen.
- Any change to `data/` or the fetch/compute stages.
