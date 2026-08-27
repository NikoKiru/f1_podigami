"""Shared ranked-table renderer for the Overdue, Unlikeliest and Soulmates pages.

The three pages present the same shape of content — a ranked list of driver
groupings, each with one headline number and a handful of supporting stats — so
they render through one component that deliberately mirrors the Combinations
table: a single bordered container, an uppercase column-label strip, hairline
row dividers and zebra striping. No floating per-row cards, no bespoke hero
card per page.

Every rank is one native ``<details>`` row: the ``<summary>`` is the row face
(rank, drivers, headline number, optional race link) and the body holds the
stat cells. Rank #1 is the same row rendered ``hero=True`` — open by default,
accented, and slightly larger — so the entry readers care about most shows its
stats without a click while still sitting in the table.

Callers pass pre-escaped HTML fragments (driver spans, stat cells, race link);
this module only assembles structure.
"""

from __future__ import annotations


def render_row(
    rank: int,
    drivers_html: str,
    num: str,
    stats_html: str,
    race_html: str = "",
    hero: bool = False,
) -> str:
    """One expandable row. ``race_html`` (Unlikeliest only) sits on the row face
    on desktop; CSS moves it into the stats panel on phones. ``hero`` marks the
    #1 rank: rendered open and accented."""
    race = f'<span class="rr-race">{race_html}</span>' if race_html else ""
    cls = "rankrow rankrow-hero" if hero else "rankrow"
    return (
        f'<li class="{cls}">'
        f"<details{' open' if hero else ''}>"
        '<summary class="rr-face">'
        f'<span class="rr-rank">{rank}</span>'
        f'<span class="rr-drivers">{drivers_html}</span>'
        f"{race}"
        f'<span class="rr-num">{num}</span>'
        '<span class="rr-chev" aria-hidden="true">&#9662;</span>'
        "</summary>"
        f'<div class="rr-stats">{stats_html}</div>'
        "</details>"
        "</li>"
    )


def render_stat(label: str, value: str, extra_class: str = "") -> str:
    """One labelled stat cell for a row's expanded panel. All three pages use
    the same cell so the styling lives in one place."""
    cls = f"rr-stat {extra_class}".strip()
    return (
        f'<div class="{cls}">'
        f'<span class="rr-stat-label">{label}</span>'
        f'<span class="rr-stat-val">{value}</span>'
        f"</div>"
    )


def render_table(
    rows_html: str,
    *,
    value_label: str,
    value_width: int,
    group_label: str = "Trio",
    race_label: str = "",
    race_width: int = 0,
) -> str:
    """Wrap rendered rows in the container + column-label strip.

    ``value_width``/``race_width`` (px) are handed to CSS as custom properties
    so the label strip and every row face share the same column geometry —
    labels sit directly above their values without a layout engine. The strip
    is hidden on phones, where rows stack instead.
    """
    style = f"--rank-num-w:{value_width}px"
    race_head = ""
    if race_label:
        style += f";--rank-race-w:{race_width}px"
        race_head = f'<span class="rh-race">{race_label}</span>'
    return (
        f'<div class="rank-wrap" style="{style}">'
        '<div class="rank-head">'
        '<span class="rh-rank">#</span>'
        f'<span class="rh-drivers">{group_label}</span>'
        f"{race_head}"
        f'<span class="rh-num">{value_label}</span>'
        '<span class="rh-chev" aria-hidden="true"></span>'
        "</div>"
        f'<ol class="rank-list">{rows_html}</ol>'
        "</div>"
    )
