"""Constructor → colour mapping for the broadcast-style driver presentation.

The Jolpica/Ergast API doesn't carry team colours, so this is a small curated
map keyed by the constructorId the API uses (see data/constructor_standings.json).
Colours follow the verified 2026 palette. ``text_on`` picks a legible ink for
text placed *on* a team colour (e.g. the number chip), so light teams like Haas
stay readable in both light and dark themes.
"""

from __future__ import annotations

# constructorId -> primary hex (2026 palette).
TEAM_COLORS: dict[str, str] = {
    "mercedes": "#00D7B6",
    "ferrari": "#ED1131",
    "mclaren": "#F47600",
    "red_bull": "#4781D7",
    "alpine": "#00A1E8",
    "aston_martin": "#229971",
    "williams": "#00A0DE",
    "haas": "#B6BABD",
    "rb": "#2647D8",  # Racing Bulls
    "sauber": "#F50537",  # Audi-branded works team in 2026
    "audi": "#F50537",  # alias, in case the id flips to "audi"
    "cadillac": "#909090",  # new 2026 entrant
}

# Used when a constructorId is unknown or missing.
FALLBACK = "#9aa3af"

# The only two inks text on a team colour is ever set in: the page's near-black
# and pure white. Both are fixed values, not theme tokens — the chip's ground is
# the team colour in either theme, so its ink must not follow the theme.
DARK_INK = "#0b0d12"
WHITE_INK = "#ffffff"


def team_color(constructor_id: str) -> str:
    """Return the team's hex colour, or a neutral fallback if unknown."""
    return TEAM_COLORS.get(constructor_id or "", FALLBACK)


def _luminance(hex_color: str) -> float:
    """Relative luminance (WCAG) of a #rrggbb colour, 0 (black) to 1 (white)."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))

    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def _contrast(a: str, b: str) -> float:
    """WCAG contrast ratio between two #rrggbb colours (1.0 to 21.0)."""
    la, lb = _luminance(a), _luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def text_on(hex_color: str) -> str:
    """Dark or white ink for text sitting on ``hex_color``, whichever is legible.

    Decided by comparing the two contrast ratios, not by a luminance threshold.
    The two are not the same question: white and DARK_INK cross over at ~0.19
    relative luminance, so any threshold above that hands white text to the
    mid-brightness team colours where dark ink reads far better — McLaren orange
    at 2.8:1 instead of 6.9:1, Williams blue at 3.0:1 instead of 6.6:1. Every
    current team colour clears WCAG AA (4.5:1) under the comparison.
    """
    return max((DARK_INK, WHITE_INK), key=lambda ink: _contrast(ink, hex_color))
