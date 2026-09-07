"""Unit tests for the constructor colour map and on-colour ink helper."""

import pytest

from build.team_colors import DARK_INK, FALLBACK, TEAM_COLORS, WHITE_INK, team_color, text_on
from build.team_colors import _luminance as luminance


def contrast(a: str, b: str) -> float:
    """WCAG contrast ratio between two #rrggbb colours."""
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def test_known_team_returns_its_colour():
    assert team_color("ferrari") == TEAM_COLORS["ferrari"]
    assert team_color("mercedes").startswith("#")


def test_unknown_or_empty_team_falls_back():
    assert team_color("nonsense_team") == FALLBACK
    assert team_color("") == FALLBACK


def test_every_colour_is_a_hex_triplet():
    for cid, hex_color in TEAM_COLORS.items():
        assert hex_color.startswith("#") and len(hex_color) == 7, cid
        int(hex_color[1:], 16)  # parses as hex


def test_text_on_picks_dark_ink_for_light_colours():
    # Haas light grey -> dark ink is the legible choice
    assert text_on("#B6BABD") == "#0b0d12"
    assert text_on("#FFFFFF") == "#0b0d12"


def test_text_on_picks_white_ink_for_dark_colours():
    # Ferrari red is dark enough that white wins the comparison (4.44 vs 4.37)
    assert text_on("#ED1131") == "#ffffff"
    assert text_on("#000000") == "#ffffff"


def test_text_on_is_always_one_of_two_inks():
    for hex_color in TEAM_COLORS.values():
        assert text_on(hex_color) in (DARK_INK, WHITE_INK)


@pytest.mark.parametrize("cid", sorted(TEAM_COLORS))
def test_text_on_picks_the_higher_contrast_ink(cid: str):
    """The ink must be whichever of the two actually reads better on the colour.

    A luminance threshold is not the same question: mid-brightness team colours
    (McLaren orange, Williams blue) sit above the white/dark crossover at
    ~0.19 relative luminance, so a threshold set anywhere higher hands them
    white text at 2.8:1 when dark ink would give 6.9:1.
    """
    colour = TEAM_COLORS[cid]
    best = max((DARK_INK, WHITE_INK), key=lambda ink: contrast(ink, colour))
    assert text_on(colour) == best, (
        f"{cid} {colour}: chose {text_on(colour)} at "
        f"{contrast(text_on(colour), colour):.2f}:1, {best} gives "
        f"{contrast(best, colour):.2f}:1"
    )


# Ferrari red is the one palette entry no ink can carry to AA: white reaches
# 4.44:1 and dark 4.37:1, so 4.44 is the ceiling for a brand colour we keep as
# published. Pinned below so it can't quietly get worse; every other colour is
# held to the full 4.5:1.
_AA_UNREACHABLE = {"ferrari"}


@pytest.mark.parametrize("cid", sorted(set(TEAM_COLORS) - _AA_UNREACHABLE))
def test_every_team_colour_carries_legible_small_text(cid: str):
    """The number chip is small text on the team colour, so it needs WCAG AA."""
    colour = TEAM_COLORS[cid]
    assert contrast(text_on(colour), colour) >= 4.5, (
        f"{cid} {colour}: {contrast(text_on(colour), colour):.2f}:1"
    )


def test_ferrari_red_stays_at_its_known_ceiling():
    """The exception above, pinned: white ink at the best ratio the colour allows."""
    assert text_on(TEAM_COLORS["ferrari"]) == WHITE_INK
    assert contrast(WHITE_INK, TEAM_COLORS["ferrari"]) == pytest.approx(4.44, abs=0.01)
