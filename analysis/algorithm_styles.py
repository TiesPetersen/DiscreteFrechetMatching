"""
Order and line style per algorithm, shared by the report scripts.

Related versions of one algorithm get the same colour and marker shape, so a
graph reads as pairs: "BBMSDppStepwise (current)" and "BBMSDppStepwiseLean",
or "BBMSCore (old)" and "BBMSCore (new)". The older version is drawn dotted
with an open marker, the newer one solid with a filled marker. Names that
belong to no known algorithm get the next colour of the fallback palette.
"""

# One entry per algorithm family, in legend order
FAMILIES = [
    ("BBMSCore", "#4E9BFF", "circle"),
    ("BBMSInter", "#FF8C42", "square"),
    ("BBMSDppInstant", "#5FD068", "diamond"),
    ("BBMSDppStepwise", "#F25F5C", "triangle-up"),
    ("DijkstraPrims", "#70E0F0", "triangle-down"),
]

FALLBACK = [
    ("#B4A0FF", "x"),
    ("#FFD23F", "star"),
    ("#FF6FA5", "pentagon"),
]

# Suffixes that mark the older of two versions
OLDER_TAGS = {"old", "current"}


def split_name(name):
    """(family, is_older) for an algorithm name such as "BBMSDppStepwiseLean"
    or "BBMSCore (old)"; family is None for an unknown algorithm."""
    base, _, tag = name.partition(" (")
    tag = tag.rstrip(")")
    if base.endswith("Lean"):
        base = base[: -len("Lean")]
    family = base if base in {f for f, _, _ in FAMILIES} else None
    return family, tag in OLDER_TAGS


def sort_key(name):
    """Family order first, then the older version before the newer one."""
    family, is_older = split_name(name)
    names = [f for f, _, _ in FAMILIES]
    position = names.index(family) if family else len(names)
    return (position, not is_older, name)


def styles(names):
    """{name: {color, dash, symbol}} for every algorithm name."""
    result, fallback_index = {}, 0
    for name in names:
        family, is_older = split_name(name)
        if family:
            _, color, symbol = next(entry for entry in FAMILIES if entry[0] == family)
        else:
            color, symbol = FALLBACK[fallback_index % len(FALLBACK)]
            fallback_index += 1
        result[name] = {
            "color": color,
            "dash": "dot" if is_older else "solid",
            "symbol": symbol + "-open" if is_older else symbol,
        }
    return result
