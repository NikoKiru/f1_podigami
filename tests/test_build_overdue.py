"""Unit tests for the overdue page's pure render helpers (no IO)."""

import math

from build import build_overdue_html as bo
from datalib import OverduePerDriver, OverdueTrio


def entry(names, ids, races_together, score, rates):
    return OverdueTrio(
        driverIds=ids,
        names=names,
        racesTogether=races_together,
        score=score,
        perDriver=[
            OverduePerDriver(name=n, podiums=1, starts=10, rate=r)
            for n, r in zip(names, rates, strict=False)
        ],
    )


# ── format_score ─────────────────────────────────────────────────────────────


def test_format_score_one_decimal():
    assert bo.format_score(8.24) == "8.2×"


def test_format_score_whole_number():
    assert bo.format_score(8.0) == "8.0×"


def test_format_score_under_one():
    assert bo.format_score(0.65) == "0.7×"


# ── format_probability ────────────────────────────────────────────────────────


def test_format_probability_medium():
    # 1 - e^(-0.5) ≈ 0.3935 → "39%"
    p = (1.0 - math.exp(-0.5)) * 100
    assert bo.format_probability(0.5) == f"{p:.0f}%"


def test_format_probability_high():
    # score=8 → ~99.97% → rounds to "100%"
    assert bo.format_probability(8.0) == "100%"


# ── render_trio ───────────────────────────────────────────────────────────────


def test_render_trio_responsive_names():
    out = bo.render_trio(["Esteban Ocon", "Sergio Pérez", "Lance Stroll"])
    assert 'class="dn-full"' in out
    assert 'class="dn-abbr"' in out
    assert "E. Ocon" in out


def test_render_trio_escapes_and_separates():
    out = bo.render_trio(["A & B", "C Driver", "D Driver"])
    assert "A &amp; B" in out
    assert 'class="sep"' in out


# ── render_row_entry ─────────────────────────────────────────────────────────


def test_render_row_entry_carries_score_and_stats():
    e = entry(["A Driver", "B Driver", "C Driver"], ["a", "b", "c"], 10, 2.0, [0.3, 0.2, 0.1])
    html = bo.render_row_entry(2, e)
    assert 'class="rankrow"' in html
    assert "2.0×" in html  # headline number on the row face
    assert "Chance by now" in html and "86%" in html  # stats in the details body
    assert "10&times;" in html  # raced together
    assert 'class="dn-abbr"' in html  # responsive names still emitted


def test_render_row_entry_hero_is_open():
    e = entry(["A Driver", "B Driver", "C Driver"], ["a", "b", "c"], 10, 2.0, [0.3, 0.2, 0.1])
    assert "rankrow-hero" in bo.render_row_entry(1, e, hero=True)
    assert "rankrow-hero" not in bo.render_row_entry(2, e)


# ── render_cards ─────────────────────────────────────────────────────────────


def test_render_cards_table_with_hero_first_row():
    entries = [
        entry(["A Driver", "B Driver", "C Driver"], ["a", "b", "c"], 50, 8.0, [0.5, 0.4, 0.3]),
        entry(["A Driver", "B Driver", "D Driver"], ["a", "b", "d"], 30, 4.0, [0.5, 0.4, 0.2]),
        entry(["A Driver", "C Driver", "D Driver"], ["a", "c", "d"], 20, 3.0, [0.5, 0.3, 0.2]),
    ]
    html = bo.render_cards(entries)
    # one combos-style container with a column-label strip
    assert 'class="rank-wrap"' in html
    assert '<span class="rh-num">Expected co-podiums</span>' in html
    assert 'class="rank-list"' in html
    # every rank is a row; only #1 is the open hero
    assert html.count('class="rankrow') == 3
    assert html.count("rankrow-hero") == 1
    assert html.count("<details open>") == 1
    assert '<span class="rr-rank">1</span>' in html
    assert '<span class="rr-rank">3</span>' in html


def test_render_cards_empty():
    assert "No candidates." in bo.render_cards([])


# ── panel ─────────────────────────────────────────────────────────────────────


def test_panel_wraps_title_and_sub():
    out = bo.panel("My Title", "the subtitle", [])
    assert "<h2>My Title</h2>" in out
    assert "the subtitle" in out
    # section is now a collapsible <details>, open by default
    assert '<details class="panel od-panel" open>' in out
    assert '<summary class="panel-head">' in out
    assert 'class="panel-chev"' in out
