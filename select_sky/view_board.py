"""BOARD: the sky as a Supabase Table Editor grid, part departure board.

UP and DOWN walk the selection through the rows (which also moves it on WALL and
RADAR), B cycles the sort. The table is a sorted copy of model.order.
"""

from badgeware import *

import skygeo
import skylogo
import skyui as ui
from skytheme import *

NAME = "BOARD"

ROWS = 8                          # rows that fit under the header
ROW_H = 21                        # 20 px of row and a 1 px divider
HEAD_Y, HEAD_H = ui.TOP, 15
TABLE_Y = HEAD_Y + HEAD_H
TABLE_H = ROWS * ROW_H
CAPTION_Y = TABLE_Y + TABLE_H + 3
FLASH_MS = 1500                   # how long a new row glows green
RESORT_MS = 250                   # live distances re-sort the table this often, not every frame
GLIDE_MS = 55                     # the scroll closes half the gap to its target in this long
CLIP_TABLE = rect(0, TABLE_Y, ui.W, TABLE_H)      # a row sliding past an edge is cut off cleanly
CLIP_ALL = rect(0, 0, ui.W, ui.H)

# Columns: left edges for text, right edges for numbers. 8 px margins either side.
X_LOGO, X_CS, CS_W = 4, 24, 64     # a 16 px logo, then the callsign
X_TYPE, TYPE_W = 90, 30
R_ALT, R_SPD, R_DIST = 170, 228, 276
X_BRG = 281                       # left edge of the arrow; the compass point follows it

# Header cells: name, unit (imperial, metric) and the x it hangs from. Numbers carry a unit and
# align their right edge to x; text columns align their left edge.
HEAD = (("CALLSIGN", None, X_CS), ("TYPE", None, X_TYPE),
        ("ALT", ("FT", "M"), R_ALT), ("SPD", ("KT", "KM/H"), R_SPD),
        ("DIST", ("NM", "KM"), R_DIST), ("BRG", None, X_BRG))

# Sorts: the name in the query, the header it lights, the key and whether it runs descending.
# Ties fall back to the nearest aircraft first.
SORTS = (("dist", "DIST", lambda a: a.dist, False),
         ("alt desc", "ALT", lambda a: (a.alt, -a.dist), True),
         ("speed desc", "SPD", lambda a: (a.gs, -a.dist), True),
         ("callsign", "CALLSIGN", lambda a: (a.label, a.dist), False))

_st = {"sort": 0, "top": 0, "scroll": 0.0, "ms": None, "src": None, "rows": [], "sorted_ms": 0, "by": -1}
_heads = {}                       # metric -> header cells with their x positions measured once


def update(app):
    m = app.model
    st = _st
    now = app.now
    metric = app.settings["metric"]

    if badge.pressed(BUTTON_B):
        st["sort"] = (st["sort"] + 1) % len(SORTS)
        st["ms"] = None                               # the table re-orders in one cut, so the scroll cuts too
    name, hot = SORTS[st["sort"]][:2]
    rows = _sorted(m, st, now)
    n = len(rows)

    sel = m.selected()
    idx = rows.index(sel) if sel in rows else 0
    step = app.repeat(BUTTON_DOWN) - app.repeat(BUTTON_UP)
    if step and n:
        # A fresh press wraps past either end; holding the key stops at the end.
        idx += step
        if not 0 <= idx < n:
            fresh = badge.pressed(BUTTON_DOWN) or badge.pressed(BUTTON_UP)
            idx = idx % n if fresh else max(0, min(n - 1, idx))
        m.select(rows[idx].hex)

    ui.topbar(app, NAME)
    ui.hintbar(app, "SORT", "ROW")
    _header(hot, metric)
    ui.cycle_bar(app)                                 # the app is stepping the highlight; WALL shows the same bar
    _caption(app, name, n, metric)
    if not n:
        st["ms"] = None
        ui.no_rows(app, TABLE_Y + 80)
        return

    scroll = _window(st, idx, n, now)
    screen.clip = CLIP_TABLE
    first = int(scroll)
    for i in range(first, min(n, first + ROWS + (scroll > first))):
        _row(rows[i], TABLE_Y + int((i - scroll) * ROW_H + 0.5), i == idx, now, metric)
    screen.clip = CLIP_ALL

    if n > ROWS:                                      # slim scroll indicator in the right margin
        track = TABLE_H - 4
        thumb = max(10, track * ROWS // n)
        ui.box(317, TABLE_Y + 2, 2, track, LINE)
        ui.box(317, TABLE_Y + 2 + (track - thumb) * min(scroll, n - ROWS) / (n - ROWS), 2, thumb, TEXT_3)


def _sorted(m, st, now):
    """A sorted copy of model.order. Rebuilt when the feed, the sort or the clock says so."""
    if st["src"] is not m.order or st["by"] != st["sort"] or now - st["sorted_ms"] >= RESORT_MS:
        key, down = SORTS[st["sort"]][2:]
        st["rows"] = rows = list(m.order)             # never sort the model's own list
        rows.sort(key=key, reverse=down)
        st["src"], st["by"], st["sorted_ms"] = m.order, st["sort"], now
    return st["rows"]


def _window(st, idx, n, now):
    """Scroll position, in rows, that keeps row idx on screen. It glides toward its target."""
    top, last = st["top"], st["ms"]
    away = last is None or now - last > 250           # first frame, a new sort, or back from another view
    if away and not top <= idx < top + ROWS:
        top = idx - ROWS // 2
    elif idx < top + 1:                               # keep one row of context past the selection
        top = idx - 1
    elif idx > top + ROWS - 2:
        top = idx - ROWS + 2
    top = st["top"] = max(0, min(top, n - ROWS))
    scroll = st["scroll"]
    if away or abs(top - scroll) > ROWS:              # a wrap across the whole list cuts instead of racing past
        scroll = float(top)
    else:
        scroll += (top - scroll) * ui.glide(now - last, GLIDE_MS)
        if abs(top - scroll) < 0.02:
            scroll = float(top)
    st["scroll"], st["ms"] = scroll, now
    return scroll


def _header(hot, metric):
    """Column names on RAISED; the one the table is sorted by lights up."""
    cells = _heads.get(metric)
    if cells is None:
        cells = _heads[metric] = []
        for label, units, x in HEAD:
            unit = units[metric] if units else ""
            w = ui.width(label, F_CAPS)
            if units:
                x -= w + ui.width(unit, F_CAPS) + 4
            cells.append((label, x, unit, x + w + 4))
    ui.box(0, HEAD_Y, ui.W, HEAD_H, RAISED)
    y = HEAD_Y + 2
    for label, x, unit, ux in cells:
        ui.text(label, x, y, GREEN_HI if label == hot else TEXT_3, F_CAPS)
        if unit:
            ui.text(unit, ux, y, TEXT_3, F_CAPS)


def _caption(app, name, n, metric):
    """The query on the left and psql's row count on the right, in the SQL-editor voice."""
    reach = ui.reach_text(app.model.range_nm, metric)
    ui.caps("where dist < %s order by %s" % (reach, name), 8, CAPTION_Y, TEXT_4)
    if n or app.feed.rows_ms is not None:             # until the first answer there is no count to give
        ui.caps("(%d row%s)" % (n, "" if n == 1 else "s"), 312, CAPTION_Y, TEXT_3, ui.RIGHT)


def _row(a, y, selected, now, metric):
    fill = SELECTED if selected else None
    if a.emergency:
        fill = RED_TINT.mix(SELECTED, 70) if selected else RED_TINT
    age = now - a.first_ms
    if 0 <= age < FLASH_MS:                           # a new row glows green, then fades
        fill = (BG if fill is None else fill).mix(GREEN_TINT, int(255 * min(1.0, 1.5 * (1 - age / FLASH_MS))))
    if fill is not None:
        ui.box(0, y, ui.W, ROW_H - 1, fill)
    ui.box(8, y + ROW_H - 1, 304, 1, LINE)
    if selected:
        ui.box(0, y, 2, ROW_H - 1, GREEN)

    if not (a.airline and skylogo.draw(a.airline[0], X_LOGO, y + 2, 16)):
        ui.plane(X_LOGO + 8, y + 10, 45, VIOLET if a.military else TEXT_4, 0.8, a.glyph)
    ui.text(ui.fit(a.label, CS_W), X_CS, y + 3, RED if a.emergency else TEXT, F_BODY)

    ty = y + 5
    ui.text(ui.fit(a.type or "---", TYPE_W, F_CAPS), X_TYPE, ty, VIOLET if a.military else TEXT_3, F_CAPS)
    w = ui.text(ui.flight_level(a.alt, metric), R_ALT, ty, alt_color(a.alt), F_CAPS, 0, ui.RIGHT)
    if a.vr > 300:
        ui.tri(R_ALT - w - 6, y + 10, 3, GREEN, True)
    elif a.vr < -300:
        ui.tri(R_ALT - w - 6, y + 10, 3, AMBER, False)
    ui.text(ui.speed_text(a.gs, metric)[0], R_SPD, ty, TEXT_2, F_CAPS, 0, ui.RIGHT)
    ui.text(ui.dist_text(a.dist, metric)[0], R_DIST, ty, TEXT_2, F_CAPS, 0, ui.RIGHT)
    ui.plane(X_BRG + 3, y + 10, a.brg, TEXT_2, 0.75, 1)       # points at the aircraft from home
    ui.text(skygeo.compass(a.brg), X_BRG + 10, ty, TEXT_3, F_CAPS)
