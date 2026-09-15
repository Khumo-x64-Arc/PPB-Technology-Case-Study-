"""Visual tokens.

One palette, one type scale, defined once and imported everywhere so the app
cannot drift out of its blue-and-white identity.
"""

from __future__ import annotations

# -- colour -----------------------------------------------------------------
NAVY = "#0A2540"        # sidebar, headings
NAVY_SOFT = "#123A63"    # hover on the navy rail
BLUE = "#0F5BD7"         # primary action, progress fill
BLUE_DARK = "#0A47AC"
SKY = "#4A9BFF"          # secondary fill
WASH = "#EEF4FD"         # app background
WHITE = "#FFFFFF"        # card surface
BORDER = "#D6E4F7"       # hairline
INK = "#12263F"          # body text
MUTED = "#5F7790"        # secondary text
FAINT = "#93A9C4"        # tertiary text on white
PALE_INK = "#B9CDE6"     # tertiary text on navy
FOOTNOTE = "#5D82AD"     # quietest text on navy

GOOD = "#1E9E6A"
WARN = "#E5A400"
BAD = "#D64545"

STATUS_COLOURS = {"under": GOOD, "near": WARN, "over": BAD}
STATUS_WORDS = {"under": "Inside budget", "near": "Close to the limit", "over": "Over budget"}

# -- type -------------------------------------------------------------------
_FAMILY_PREFERENCE = ("Segoe UI", "Inter", "Helvetica Neue", "Nimbus Sans",
                      "DejaVu Sans", "Liberation Sans", "Arial")
_resolved_family: str | None = None


def family() -> str:
    """Pick the best available family once, after the Tk root exists."""
    global _resolved_family
    if _resolved_family is None:
        try:
            from tkinter import font as tkfont
            available = set(tkfont.families())
        except Exception:
            available = set()
        _resolved_family = next(
            (name for name in _FAMILY_PREFERENCE if name in available), "TkDefaultFont")
    return _resolved_family


def font(size: int = 13, weight: str = "normal") -> tuple:
    return (family(), size, weight)


DISPLAY = 30
TITLE = 20
LEAD = 15
BODY = 13
CAPTION = 11
