"""Unit tests for the shared ranked-table renderer."""

from build._rows import render_row, render_stat, render_table


def test_render_row_structure():
    out = render_row("<span>A &middot; B &middot; C</span>", "1 in 440", "<div>stats</div>")
    assert out.startswith('<li class="rankrow">')
    assert out.endswith("</li>")
    assert "<details>" in out
    assert '<summary class="rr-face">' in out
    assert 'class="rr-rank"' not in out  # ordered <ol>; no ordinal column
    assert '<span class="rr-drivers"><span>A &middot; B &middot; C</span></span>' in out
    assert '<span class="rr-num">1 in 440</span>' in out
    assert '<span class="rr-chev" aria-hidden="true">&#9662;</span>' in out
    assert '<div class="rr-stats"><div>stats</div></div>' in out


def test_render_row_race_optional():
    assert 'class="rr-race"' not in render_row("d", "n", "s")
    out = render_row("d", "n", "s", race_html='<a href="x">1990 Japanese GP</a>')
    assert '<span class="rr-race"><a href="x">1990 Japanese GP</a></span>' in out


def test_render_row_hero_is_open_and_flagged():
    """#1 stays a table row — just opened and accented — so its stats are
    visible without a click."""
    out = render_row("d", "n", "s", hero=True)
    assert out.startswith('<li class="rankrow rankrow-hero">')
    assert "<details open>" in out


def test_render_row_default_is_closed():
    out = render_row("d", "n", "s")
    assert "<details open>" not in out
    assert "rankrow-hero" not in out


# ── render_stat ──────────────────────────────────────────────────────────────


def test_render_stat_cell():
    out = render_stat("Raced together", "82&times;")
    assert out == (
        '<div class="rr-stat">'
        '<span class="rr-stat-label">Raced together</span>'
        '<span class="rr-stat-val">82&times;</span>'
        "</div>"
    )


def test_render_stat_extra_class():
    assert '<div class="rr-stat rr-stat-race">' in render_stat(
        "Race", "x", extra_class="rr-stat-race"
    )


# ── render_table ─────────────────────────────────────────────────────────────


def test_render_table_wraps_rows_with_label_strip():
    out = render_table("<li>row</li>", value_label="Shared podiums", value_width=140)
    assert '<div class="rank-wrap" style="--rank-num-w:140px">' in out
    assert '<div class="rank-head">' in out
    assert 'class="rh-rank"' not in out  # no "#" label above a column that's gone
    assert '<span class="rh-drivers">Trio</span>' in out
    assert '<span class="rh-num">Shared podiums</span>' in out
    assert '<ol class="rank-list"><li>row</li></ol>' in out
    assert out.endswith("</div>")


def test_render_table_group_label_overridable():
    out = render_table("", value_label="v", value_width=10, group_label="Duo")
    assert '<span class="rh-drivers">Duo</span>' in out


def test_render_table_race_column_optional():
    assert 'class="rh-race"' not in render_table("", value_label="v", value_width=10)
    out = render_table("", value_label="v", value_width=10, race_label="Race", race_width=210)
    assert '<span class="rh-race">Race</span>' in out
    # both column widths reach CSS so the strip and the row faces line up
    assert 'style="--rank-num-w:10px;--rank-race-w:210px"' in out
