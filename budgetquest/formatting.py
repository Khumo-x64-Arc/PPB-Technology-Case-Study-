"""Display helpers.

Kept in one module so every view formats money the same way (DRY).
"""


def rand(value: float, decimals: int = 2) -> str:
    """Format a number as South African Rand: R 1 234.56 (space thousands)."""
    text = f"{abs(value):,.{decimals}f}".replace(",", " ")
    sign = "-" if value < 0 else ""
    return f"{sign}R {text}"


def rand_short(value: float) -> str:
    """Compact Rand, no cents. Used on chart axes and small chips."""
    return rand(value, 0)


def pct(fraction: float, decimals: int = 1) -> str:
    """0.1532 -> '15.3%'."""
    return f"{fraction * 100:.{decimals}f}%"


#: Words that stay upper case when a narrative is prettified.
ACRONYMS = {"ATM", "EFT", "TXN", "SMS", "POS", "VAT", "ID", "PIN"}


def _capitalise(word: str) -> str:
    """Capitalise the first letter, keeping brackets and hyphens sensible."""
    parts = word.lower().split("-")
    fixed = []
    for index, part in enumerate(parts):
        # 'E-TOLL' keeps the second capital; '(once-off)' does not.
        if index and len(parts[index - 1].strip("(")) != 1:
            fixed.append(part)
            continue
        for position, character in enumerate(part):
            if character.isalpha():
                fixed.append(part[:position] + character.upper() + part[position + 1:])
                break
        else:
            fixed.append(part)
    return "-".join(fixed)


def title(text: str) -> str:
    """Turn a SCREAMING narrative fragment into readable text."""
    words = []
    for word in text.split():
        words.append(word.upper() if word.strip("()/-.,").upper() in ACRONYMS
                     else _capitalise(word))
    return " ".join(words)


def shorten(text: str, limit: int) -> str:
    """Trim to `limit` characters, with an ellipsis when it had to cut."""
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "\u2026"


def hours(value: float) -> str:
    """Settlement lag as a short human string."""
    if value < 1:
        return f"{int(round(value * 60))} min"
    if value < 48:
        return f"{value:.1f} hrs"
    return f"{value / 24:.1f} days"
