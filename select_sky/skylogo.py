"""Airline logos, cut from the sheets in logos/ that scripts/build_logos.py makes.

A sheet loads the first time one of its logos is drawn. One that will not load draws nothing,
so the caller's fallback shows instead.
"""

from badgeware import *

import skylogodata as D
import skyui as ui

PLATE = color.rgb(239, 239, 239)      # behind the dark logos listed in D.LIGHT
BIG, SMALL = D.SIZES
KEEP_BIG = 4                          # big sheets held at once; the small ones are 4 KB and all stay

_at = {}                              # ICAO prefix -> logo number
for _i in range(0, len(D.CODES), 3):
    _at[D.CODES[_i:_i + 3]] = _i // 3
_light = set(D.LIGHT[i:i + 3] for i in range(0, len(D.LIGHT), 3))
_sheets = {}                          # (size, sheet number) -> image, or None when it failed to load
_big = []                             # loaded big sheets, least recently used first


def has(prefix):
    return prefix in _at


def _sheet(size, n):
    k = (size, n)
    if k in _sheets:
        img = _sheets[k]
    else:
        try:
            img = image.load("logos/%d_%d.png" % k)
        except Exception:             # missing file or no memory: no logo, not a crash
            img = None
        _sheets[k] = img
    if img is not None and size == BIG:
        if k in _big:
            _big.remove(k)
        _big.append(k)
        if len(_big) > KEEP_BIG:
            del _sheets[_big.pop(0)]
    return img


def draw(prefix, x, y, size, back=None, pad=0):
    """The logo for an ICAO prefix in a size-px square at x, y. Returns False, drawing nothing, when there is none.

    A dark logo sits on a light plate filling the square; back fills it for the rest. pad insets the logo."""
    n = _at.get(prefix)
    if n is None:
        return False
    light = prefix in _light
    if light and not pad:
        pad = max(1, size // 12)      # let the plate show round the edge
    inner = size - 2 * pad
    base = BIG if inner > SMALL + 4 else SMALL
    img = _sheet(base, n // D.PER_SHEET)
    if img is None:
        return False
    x, y = int(x), int(y)
    if light or back is not None:
        ui.panel(x, y, size, size, PLATE if light else back, max(2, size // 7))
    cell = n % D.PER_SHEET
    screen.blit(img, rect((cell % D.COLS) * base, (cell // D.COLS) * base, base, base),
                rect(x + pad, y + pad, inner, inner), image.NEAREST if inner == base else image.BILINEAR)
    return True
