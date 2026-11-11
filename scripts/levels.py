"""Purdue levels, band-header colours and scope colours for the meaning-based spec (spec_version 2). Standard library only.

A diagram is drawn as horizontal bands, one per Purdue level that contains at least one item (decision L6), highest level at the top.
Every band has the same header (same height, font, placement and border); the only thing that may differ is the header fill, and only when
the client supplied colours (decisions L11, L17). Inside a band, items are grouped into scope boxes: grey = Avanceon scope, pink =
Client / Other scope (decision L12). The scope colours live here so the footer legend and the drawing use the same values.
"""
import re

LEVELS = [  # top to bottom on the page; the names are a judgement for L3-L5 (the document names only L0-L2): rename here
    ("L5",   "Level 5 - Enterprise Network"),
    ("L4",   "Level 4 - Site Business Planning"),
    ("L3.5", "Level 3.5 - DMZ"),
    ("L3",   "Level 3 - Site Operations"),
    ("L2",   "Level 2 - Supervisory (SCADA)"),
    ("L1",   "Level 1 - Control (PLC / RTU / RIO)"),
    ("L0",   "Level 0 - Field (Instruments / Actuators)"),
]
LEVEL_IDS = tuple(k for k, _ in LEVELS)
DEFAULT_HEADER_FILL, DEFAULT_HEADER_LINE = "#1F5FA6", "#1F5FA6"      # dark blue title strip (decision D56); the same for every band unless the client gives colours
HEADER_H = 0.10             # inches of padding above the scope boxes (the title is now a vertical strip, not a bar)
STRIP_W = 0.45              # inches: width of the vertical title strip on the left of every band
HEADER_SIZE = 8             # pt, bold, white, rotated; the same for every band
BAND_FILL, BAND_LINE = "#E2EEFB", "#8FB4DC"                         # band body: sky blue, the scope boxes sit inside it

SCOPE_FILL = {"avanceon": "#E7E6E6", "other": "#F2DCDB"}            # decision D: light grey / light pink
SCOPE_CAPTION = {"avanceon": "Avanceon scope", "other": "Client / Other scope"}
SCOPE_LINE = "#A6A6A6"

_HEX = re.compile(r"#[0-9A-Fa-f]{6}$")


class ScopeQuestion(ValueError):
    """The scope of an item is missing, unknown or dual. The user must be asked; it is never guessed (decision L9)."""

    def __init__(self, label):
        self.question = "Which scope is %s: Avanceon or Client/Other?" % label
        super().__init__(self.question)


def level_title(level):
    for k, title in LEVELS:
        if k == level:
            return title
    raise ValueError("unknown level %r (use %s)" % (level, ", ".join(LEVEL_IDS)))


def order(levels_used):
    """The levels in `levels_used` (any iterable, repeats allowed) that exist, top to bottom. An unknown level raises ValueError."""
    used = set(levels_used)
    for u in used:
        level_title(u)
    return [k for k in LEVEL_IDS if k in used]


def header_colours(spec, warnings=None):
    """{level: '#RRGGBB'} for every level: the client's colour from spec['band_colors'] when valid, else the light-blue default.
    A bad entry is ignored and, when a list is given, a warning is appended to it."""
    out = {k: DEFAULT_HEADER_FILL for k in LEVEL_IDS}
    given = (spec or {}).get("band_colors")
    if given is None:
        return out
    if not isinstance(given, dict):
        if warnings is not None:
            warnings.append("band_colors must be an object like {\"L2\": \"#RRGGBB\"}; ignored")
        return out
    for level, colour in given.items():
        if level not in out:
            if warnings is not None:
                warnings.append("band_colors: %r is not a level (%s); ignored" % (level, ", ".join(LEVEL_IDS)))
        elif not (isinstance(colour, str) and _HEX.match(colour)):
            if warnings is not None:
                warnings.append("band_colors[%s]: %r is not #RRGGBB; default colour used" % (level, colour))
        else:
            out[level] = colour
    return out


def check_scope(item):
    """'avanceon' or 'other' for an item dict. Missing, unknown or dual scope raises ScopeQuestion (a question for the user)."""
    scope = item.get("scope")
    if isinstance(scope, str) and scope.strip().lower() in SCOPE_FILL:
        return scope.strip().lower()
    raise ScopeQuestion(item.get("label") or item.get("id") or "this item")
