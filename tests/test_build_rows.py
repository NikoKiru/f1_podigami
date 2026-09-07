"""Unit tests for the shared ranked-table renderer."""

from build._rows import render_row, render_section, render_stat, render_table


def test_render_row_structure():
    out = render_row("<span>A &middot; B &middot; C</span>", "1 in 440", "<div>stats</div>")
    assert out.startswith('<li class="rankrow">')
    assert out.endswith("</li>")
    assert "<details>" in out
    assert '<summary class="rr-face">' in out
    assert 'class="rr-rank"' not in out  # ordered <ol>; no ordinal column
    assert '<span class="rr-drivers"><span>A &middot; B &middot; C</span></span>' in out
    assert '<span class="rr-num">1 in 440</span>' in out
    assert (
        '<span class="rr-chev" aria-hidden="true"><span class="chev">&#9662;</span></span>' in out
    )
    assert '<div class="rr-stats"><div>stats</div></div>' in out


def test_render_row_column_order_matches_combinations_table():
    """Group, then the headline value, then context, then the chevron — the
    same order as the combinations table's Trios / Count / Last seen."""
    out = render_row("d", "7.9&times;", "s", race_html="<a>r</a>")
    assert out.index('class="rr-drivers"') < out.index('class="rr-num"')
    assert out.index('class="rr-num"') < out.index('class="rr-race"')
    assert out.index('class="rr-race"') < out.index('class="rr-chev"')


def test_render_row_race_optional():
    assert 'class="rr-race"' not in render_row("d", "n", "s")
    out = render_row("d", "n", "s", race_html='<a href="x">1990 Japanese GP</a>')
    assert '<span class="rr-race"><a href="x">1990 Japanese GP</a></span>' in out


def test_render_row_hero_is_flagged_but_still_closed():
    """#1 differs by an accent rail only: it stays closed like every other row,
    so the closed face shows the headline stat and the detail needs a click."""
    out = render_row("d", "n", "s", hero=True)
    assert out.startswith('<li class="rankrow rankrow-hero">')
    assert "<details open>" not in out


def test_no_row_is_open_by_default():
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
    out = render_table("<li>row</li>", value_label="Shared podiums", cols="1fr 200px 26px")
    assert '<div class="rank-wrap" style="--rank-cols:1fr 200px 26px">' in out
    assert '<div class="rank-head">' in out
    assert 'class="rh-rank"' not in out  # no "#" label above a column that's gone
    assert '<span class="rh-drivers">Trio</span>' in out
    assert '<span class="rh-num">Shared podiums</span>' in out
    assert '<ol class="rank-list"><li>row</li></ol>' in out
    assert out.endswith("</div>")


def test_render_table_label_strip_matches_row_column_order():
    out = render_table("", value_label="Odds", cols="1fr 110px 240px 26px", race_label="Race")
    assert out.index('class="rh-drivers"') < out.index('class="rh-num"')
    assert out.index('class="rh-num"') < out.index('class="rh-race"')
    assert out.index('class="rh-race"') < out.index('class="rh-chev"')


def test_render_table_group_label_overridable():
    out = render_table("", value_label="v", cols="1fr 10px 26px", group_label="Duo")
    assert '<span class="rh-drivers">Duo</span>' in out


def test_render_table_race_column_optional():
    assert 'class="rh-race"' not in render_table("", value_label="v", cols="1fr 10px 26px")
    out = render_table("", value_label="v", cols="1fr 10px 210px 26px", race_label="Race")
    assert '<span class="rh-race">Race</span>' in out


def test_render_table_column_geometry_reaches_css():
    """One custom property carries the tracks, so the label strip and every row
    face line up without a layout engine."""
    out = render_table("", value_label="v", cols="minmax(0,1fr) 110px 240px 26px")
    assert 'style="--rank-cols:minmax(0,1fr) 110px 240px 26px"' in out


# ── render_section ───────────────────────────────────────────────────────────


def test_render_section_has_no_panel_box():
    """The heading and description sit naked above the table so the table is
    the only framed element (matching the combinations page)."""
    out = render_section("My Title", "the subtitle", "<div>table</div>")
    assert out.startswith('<section class="rank-section">')
    assert "<h2>My Title</h2>" in out
    assert '<p class="rank-sub">the subtitle</p>' in out
    assert "<div>table</div>" in out
    assert "panel" not in out
