"""RADAR: the sky around home as a scope. A sweep lights each aircraft it passes.

Left, a round scope: range rings, compass marks, a rotating beam and every
aircraft at its true position. Traffic beyond the range sits on the bezel at its
bearing, so you can see what is coming. Right, the selected aircraft.

B cycles the range, and held it zooms the scope in on the selection. UP and DOWN move the selection;
zoomed, A, C, UP and DOWN pan.
"""

import math

from badgeware import *

import skygeo
import skyui as ui
import skyview
from skymodel import RANGES
from skytheme import *

NAME = "RADAR"

CX, CY = 100, 122            # scope centre: 8 px from the left edge and from both bars
BEZEL_R = 92                 # outer edge of the compass band
R = 78                       # the range circle
MARK_R = 85                  # middle of the band: compass marks and rim markers sit here
INFO_X, INFO_R = 208, 312    # info column, left and right edges
VALUE_R, UNIT_X = 283, 287   # readout numbers end here and their units start here (KM/H ends at the margin)

SWEEP_MS = 4000              # one turn of the beam
ZOOM_HALF_MS = 70            # the scope closes half the gap to its goal every 70 ms
LOCK_MS = 260                # reticle closes on a newly selected aircraft
TAG_H = 15                   # selection tag height
TRAIL_PTS = 5
FULL_BLIPS = 40              # a crowded sky draws only the nearest this many as aircraft
FULL_RIM = 32                # and this many beyond the range; the rest are dots
GLYPH_SCALE = (0.66, 0.88, 0.82)          # airliner, light aircraft, rotorcraft
CARDINALS = (("N", 0, -1), ("E", 1, 0), ("S", 0, 1), ("W", -1, 0))

_shapes = {}
_trails = {}                 # hex -> (signature, [(east, north) nm]) so trig runs once per report
_zoom = {"view": None, "ms": 0}     # the scope as drawn, (radius nm, east nm, north nm of home), gliding toward its goal
_view = {"on": False, "x": 0.0, "y": 0.0, "follow": False, "aim": None, "down": None}      # the zoom: where the scope is headed, and B going down
_rim = {}                    # hex -> bezel facts that only change with the bearing, so trig runs once per move
_GLOW = [int(255 * (1.0 - s / 360.0) ** 2) for s in range(360)]       # 0..255 per degree since the beam passed


class _Frame:
    """What drawing an aircraft needs to know about this frame."""
    turn = 0                 # whole degrees the beam has turned
    now = 0
    k = 1.0                  # pixels per nautical mile
    vx = vy = 0.0            # nm east and north of home at the scope centre
    off = False              # the centre is away from home, so a bearing from home is not one from the centre
    home = (0.0, 0.0)
    keep = TRAIL_PTS         # trail points to draw


_f = _Frame()


def _cached(key, make):
    s = _shapes.get(key)
    if s is None:
        s = _shapes[key] = make()
    return s


def _place(s, x, y, rot=0):
    s.transform = mat3().translate(x, y).rotate(rot)
    return s


# ---- frame ----------------------------------------------------------------

def update(app):
    m = app.model
    metric = app.settings["metric"]
    v = _view

    gap = app.now - _zoom["ms"] > 250             # an alert, another view or a blocked frame came between
    v["down"], key = skyview.b_event(v["down"], app.now, badge.pressed(BUTTON_B), badge.held(BUTTON_B), gap)
    if key == "tap":                              # on release, so a hold is not also a tap
        app.set_range(next((r for r in RANGES if r > m.range_nm), RANGES[0]))
    elif key == "hold":
        _zoom_toggle(m)
    if v["on"]:
        _pan(app, m)
    else:
        app.nav()
    app.capture = v["on"]                         # zoomed, A and C pan instead of changing view

    sweep = app.sweep = (app.now % SWEEP_MS) * 360.0 / SWEEP_MS
    sel = m.selected()
    goal = _target(m, sel)
    rng, vx, vy = _glide(app.now, goal)

    ui.topbar(app, NAME)
    if v["on"]:
        ui.hintbar(app, "RANGE", "PAN", "LEFT", "RIGHT", hold="FULL")
    else:
        ui.hintbar(app, "RANGE", "FLIGHT", hold="ZOOM")
    screen.alpha = 255
    ui.cycle_bar(app)                                                      # as on WALL

    f = _f
    f.vx, f.vy, f.off = vx, vy, vx != 0.0 or vy != 0.0
    r2 = rng * rng
    # Everything reported is drawn from one scale, so a range change slides
    # aircraft across the rim instead of popping them in and out.
    inside, rim = [], []
    for a in m.order + m.outer:                   # nearest first
        ex, ey = a.dx - vx, a.dy - vy
        (inside if ex * ex + ey * ey <= r2 else rim).append(a)

    f.turn, f.now, f.k, f.home = int(sweep), app.now, R / rng, m.home
    f.keep = TRAIL_PTS if len(inside) <= 16 else 3            # a crowded sky gets shorter trails
    sel_xy = tag = None
    sel_in = False
    if sel:
        ex, ey = sel.dx - vx, sel.dy - vy
        sel_in = ex * ex + ey * ey <= r2
        sel_xy = _xy(sel) if sel_in else _rim_xy(sel)
        tag = _tag(sel, sel_xy[0], sel_xy[1], metric)

    _face(goal[0], metric, tag)
    hidden = _home_mark(tag)
    _wedge(sweep)
    for i in range(len(inside) - 1, -1, -1):      # the nearest draws last, on top
        a = inside[i]
        if a is not sel:
            x, y = _xy(a)
            _blip(a, x, y, False, i < FULL_BLIPS)
    if sel and sel_in:
        _blip(sel, sel_xy[0], sel_xy[1], True, True)
    if f.off:                                     # the bezel shows bearings from home: panned away, it keeps only the selection
        if sel and not sel_in:
            _rim_marker(sel, sel_xy[0], sel_xy[1], 0, False, True, True)
            hidden |= skyview.compass_bit(_bearing(sel, sel_xy[0], sel_xy[1]))
    else:
        for i in range(len(rim)):
            a = rim[i]
            e = _rim_pos(a)
            _rim_marker(a, e[2], e[3], (f.turn - e[6]) % 360, e[4], i < FULL_RIM, a is sel)
            hidden |= e[5]                        # a compass mark next to a marker is left out
    _compass(hidden, tag)
    screen.alpha = 255

    if tag:
        _lock(app, sel, sel_xy[0], sel_xy[1], tag)
    _info(app, sel, len(m.order), metric)
    if v["on"]:                                   # last, so the tag cannot cover them
        if not v["follow"]:
            _crosshair()
        ui.pill(8, 28, "zoom", GREEN_HI, GREEN_TINT)


def _zoom_toggle(m):
    """Hold B: zoom in on the selection, or back out to the whole scope."""
    v = _view
    v["on"] = not v["on"]
    v["x"] = v["y"] = 0.0
    v["follow"], v["aim"] = v["on"] and m.selected() is not None, None
    if v["on"]:
        m.auto = False                            # as UP and DOWN: the selection is yours now


def _pan(app, m):
    """A, C, UP and DOWN move the view. Once it rests, a flight at the crosshair is selected and followed."""
    v = _view
    sx = app.repeat(BUTTON_C) - app.repeat(BUTTON_A)
    sy = app.repeat(BUTTON_UP) - app.repeat(BUTTON_DOWN)
    radius = m.range_nm / skyview.ZOOM
    if sx or sy:
        step = radius * skyview.PAN_PX / R
        v["x"] += sx * step
        v["y"] += sy * step
        v["follow"], v["aim"] = False, app.now
    elif v["aim"] is not None and app.now - v["aim"] >= skyview.AIM_MS:
        v["aim"] = None
        a = skyview.nearest(m.order, v["x"], v["y"], radius * skyview.AIM_PX / R)
        if a:
            m.select(a.hex)
            v["follow"] = True


def _target(m, sel):
    """Where the scope is headed: (radius nm, east nm, north nm of home). The close-up stays inside the range circle."""
    v = _view
    if not v["on"]:
        return float(m.range_nm), 0.0, 0.0
    if v["follow"]:
        if sel:
            v["x"], v["y"] = sel.dx, sel.dy
        else:
            v["follow"] = False                   # nothing left to follow
    v["x"], v["y"] = skyview.clamp(v["x"], v["y"], skyview.reach(m.range_nm))
    return m.range_nm / skyview.ZOOM, v["x"], v["y"]


def _glide(now, goal):
    """The scope as drawn this frame: (radius nm, east nm, north nm). It glides toward the goal, the radius in log steps."""
    z = _zoom
    cur = z["view"]
    if cur is None or now - z["ms"] > 250:
        cur = goal
    else:
        cur = skyview.ease(cur, goal, ui.glide(now - z["ms"], ZOOM_HALF_MS))
    z["view"], z["ms"] = cur, now
    return cur


# ---- the scope ------------------------------------------------------------

def _overlaps(x1, y1, w1, h1, x2, y2, w2, h2):
    return x1 < x2 + w2 + 2 and x1 + w1 > x2 - 2 and y1 < y2 + h2 + 2 and y1 + h1 > y2 - 2


def _face(radius_nm, metric, tag):
    ui.disc(CX, CY, BEZEL_R, PANEL)
    ui.disc(CX, CY, R, BG_DEEP)
    ui.ring(CX, CY, R // 4, LINE)
    ui.ring(CX, CY, R // 2, LINE)
    ui.ring(CX, CY, R, GREEN_MID if _view["on"] else LINE_HI)
    unit = " KM" if metric else " NM"
    for nm, r, suffix in ((radius_nm / 2.0, R // 2, ""), (radius_nm, R, unit)):
        words = ui.reach_text(nm, metric) + suffix
        w = ui.width(words, F_CAPS)
        x, y = CX - w / 2, CY + r - 15
        if not (tag and _overlaps(x, y, w, 9, tag[0], tag[1], tag[2], TAG_H)):
            ui.caps(words, CX, y, TEXT_3, ui.CENTER_X)       # a label the tag would cover is left out
    ui.box(CX - 1, CY - R, 2, 6, GREEN)                       # north tick
    ui.box(CX + R - 4, CY, 4, 1, LINE_HI)
    ui.box(CX - R, CY, 4, 1, LINE_HI)
    ui.box(CX, CY + R - 4, 1, 4, LINE_HI)


def _home_mark(tag):
    """Home: the grey dot where it lies, or once the scope is panned away a ring on the bezel toward it.
    Returns the compass mark the ring covers, as a bit."""
    f = _f
    hx, hy = -f.vx * f.k, f.vy * f.k
    if hx * hx + hy * hy < (R - 3) * (R - 3):
        ui.disc(CX + hx, CY + hy, 2, TEXT_4)
        return 0
    x, y = _edge(-f.vx, -f.vy)
    if tag and _overlaps(x - 4, y - 4, 8, 8, tag[0], tag[1], tag[2], TAG_H):
        return 0                                  # a ring the tag would half cover is left out, as a compass mark is
    ui.ring(x, y, 4, TEXT_2)
    return skyview.compass_bit(math.degrees(math.atan2(hx, -hy)) % 360)


def _crosshair():
    """Panned off the selection: a cross marks where the scope is aimed."""
    for x, y, w, h in ((CX - 6, CY, 4, 1), (CX + 3, CY, 4, 1), (CX, CY - 6, 1, 4), (CX, CY + 3, 1, 4)):
        ui.box(x, y, w, h, TEXT_3)


def _compass(hidden, tag):
    for i, (letter, dx, dy) in enumerate(CARDINALS):
        x, y = CX + dx * MARK_R, CY + dy * MARK_R - 6
        if not hidden & (1 << i) and not (tag and _overlaps(x - 4, y, 8, 9, tag[0], tag[1], tag[2], TAG_H)):
            ui.caps(letter, x, y, TEXT if i == 0 else TEXT_3, ui.CENTER_X)


def _wedge(angle):
    """The sweep: a conical gradient that fades behind the beam, and the beam itself."""
    g = _cached("wedge", lambda: brush.gradient(brush.CONICAL, CX, CY, CX, CY - 40, (
        (0.0, color.rgb(62, 207, 142, 0)), (0.5, color.rgb(62, 207, 142, 0)),
        (0.88, color.rgb(62, 207, 142, 26)), (1.0, color.rgb(62, 207, 142, 105)))))
    a = math.radians(angle)
    g.geometry(CX, CY, CX + 40 * math.sin(a), CY - 40 * math.cos(a))
    screen.pen = g
    # No transform here: a gradient is laid out through the shape's own transform.
    screen.shape(_cached("disc", lambda: shape.circle(CX, CY, R)))
    screen.pen = GREEN_HI
    screen.alpha = 190
    screen.shape(_place(_cached("beam", lambda: shape.line(0, 0, 0, -R, 1.5)), CX, CY, angle))
    screen.alpha = 255


# ---- aircraft -------------------------------------------------------------

def _xy(a):
    return CX + (a.dx - _f.vx) * _f.k, CY - (a.dy - _f.vy) * _f.k


def _edge(ex, ey):
    """The bezel point in the direction of an offset, in nm east and north of the scope centre."""
    d = math.sqrt(ex * ex + ey * ey)
    return CX + MARK_R * ex / d, CY - MARK_R * ey / d


def _bearing(a, x, y):
    """Whole degrees of a's bearing from the scope centre: home's own figure while the scope is centred there."""
    if _f.off:
        return int(math.degrees(math.atan2(x - CX, CY - y))) % 360
    return int(a.brg)


def _rim_pos(a):
    """(brg, trk, x, y, inbound, compass bit hidden, whole-degree bearing), redone only when the bearing or track moves."""
    e = _rim.get(a.hex)
    if e is None or e[0] != a.brg or e[1] != a.trk:
        if len(_rim) > 511:
            _rim.clear()
        b = math.radians(a.brg)
        e = _rim[a.hex] = (a.brg, a.trk, CX + MARK_R * math.sin(b), CY - MARK_R * math.cos(b),
                           a.trk >= 0 and abs(skygeo.turn(a.trk, a.brg + 180)) < 90,
                           skyview.compass_bit(a.brg), int(a.brg))
    return e


def _rim_xy(a):
    if _f.off:                                    # panned away: the bearing from the scope centre, not from home
        return _edge(a.dx - _f.vx, a.dy - _f.vy)
    e = _rim_pos(a)
    return e[2], e[3]


def _trail(a, x, y, col, alpha):
    f = _f
    key = (len(a.trail), a.trail[-1], f.home, f.keep)
    hit = _trails.get(a.hex)
    if hit is None or hit[0] != key:
        if len(_trails) > 200:
            _trails.clear()
        hit = _trails[a.hex] = (key, [skygeo.offset_nm(f.home[0], f.home[1], la, lo) for la, lo, _ in a.trail[-f.keep:]])
    pts = hit[1]
    n = len(pts)
    screen.pen = col
    px = py = None
    for i in range(n + 1):
        qx, qy = (CX + (pts[i][0] - f.vx) * f.k, CY - (pts[i][1] - f.vy) * f.k) if i < n else (x, y)
        if px is not None and (px - CX) ** 2 + (py - CY) ** 2 < R * R and (qx - CX) ** 2 + (qy - CY) ** 2 < R * R:
            screen.alpha = alpha * i // (n + 1)             # older segments fade out
            screen.line(int(px), int(py), int(qx), int(qy))
        px, py = qx, qy
    screen.alpha = 255


def _pulse(x, y):
    """Emergency: a red glow and a ring that spreads and fades."""
    phase = (_f.now % 900) / 900.0
    screen.alpha = 70 + int(70 * (1 - phase))
    ui.disc(x, y, 8, RED)
    screen.alpha = int(210 * (1 - phase))
    ui.ring(x, y, 5 + int(18 * phase) / 2.0, RED, 1.5)           # half-pixel steps keep the ring cache small
    screen.alpha = 255


def _blip(a, x, y, selected, full):
    col = alt_color(a.alt)
    since = (_f.turn - _bearing(a, x, y)) % 360            # degrees the beam has turned since it passed
    alpha = 255 if selected else 95 + _GLOW[since] * 160 // 255
    emergency = a.emergency
    if not full and not emergency:                         # a crowded sky: just a dot
        screen.alpha = alpha
        ui.box(x - 1, y - 1, 3, 3, col)
        screen.alpha = 255
        return
    if a.trail:
        _trail(a, x, y, col, alpha * 7 // 10)
    if emergency:
        _pulse(x, y)
    elif since < 40:                                       # the beam just passed: a brief flare
        screen.alpha = 75 * (40 - since) // 40
        ui.disc(x, y, 7, col)
    screen.alpha = alpha
    if a.military:
        ui.ring(x, y, 7.5, VIOLET, 1.5)
    if a.trk >= 0:
        ui.plane(x, y, a.trk, col, GLYPH_SCALE[a.glyph] * (1.3 if selected else 1), a.glyph)
    else:
        ui.disc(x, y, 3, col)
    screen.alpha = 255


def _rim_marker(a, x, y, since, inbound, full, selected):
    """A small dart pointing along the track: bright when it is heading for home."""
    emergency = a.emergency
    if emergency:
        _pulse(x, y)
    if selected or emergency:
        screen.alpha = 255
    else:
        screen.alpha = 170 + _GLOW[since] * 85 // 255 if inbound else 115 + _GLOW[since] * 80 // 255
    col = alt_color(a.alt)
    if not full and not emergency:
        ui.box(x - 1, y - 1, 2, 2, col)
    elif a.trk >= 0:
        ui.plane(x, y, a.trk, col, 0.75, 1)
    else:
        ui.disc(x, y, 2.5, col)
    screen.alpha = 255


# ---- selection ------------------------------------------------------------

def _tag(a, x, y, metric):
    """Where the selection tag sits and what it says: (left, top, width, name, altitude)."""
    name = ui.fit(a.label, 64)
    alt = ui.flight_level(a.alt, metric).upper()
    if metric and a.alt > 0:
        alt += " M"
    w = int(ui.width(name) + ui.width(alt, F_CAPS) + 19)
    tx, ty = _tag_spot(x, y, w, TAG_H)
    return tx, ty, w, name, alt


def _lock(app, a, x, y, tag):
    """The green reticle, a one-minute vector from the nose, and the tag."""
    t = min(1.0, (app.now - app.sel_ms) / LOCK_MS)
    h = 11 + int(10 * (1 - t) * (1 - t))
    L = 4
    for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        cx, cy = int(x) + sx * h, int(y) + sy * h
        ui.box(cx if sx < 0 else cx - L, cy if sy < 0 else cy - 2, L, 2, GREEN)
        ui.box(cx if sx < 0 else cx - 2, cy if sy < 0 else cy - L, 2, L, GREEN)

    _vector(a, x, y)
    tx, ty, w, name, alt = tag
    ui.box(tx, ty, w, TAG_H, RAISED)
    ui.box(tx, ty, 2, TAG_H, GREEN)
    ui.text(name, tx + 7, ty + 1, TEXT)
    ui.caps(alt, tx + w - 5, ty + 3, TEXT_3, ui.RIGHT)


def _vector(a, x, y):
    """From the nose to where the aircraft will be in one minute, or to the edge of the scope."""
    if a.trk < 0 or a.gs <= 0:
        return
    qx, qy = x - CX, y - CY
    if qx * qx + qy * qy >= R * R:                          # a rim marker is not at its true position
        return
    r = math.radians(a.trk)
    s, c = math.sin(r), -math.cos(r)
    b = qx * s + qy * c
    edge = -b + math.sqrt(max(0.0, b * b - qx * qx - qy * qy + R * R))      # distance along the track to the rim
    end = min(a.gs / 60.0 * _f.k, edge)
    if end > 13:                                            # shorter would hide behind the reticle
        screen.alpha = 170
        ui.line(x + s * 9, y + c * 9, x + s * end, y + c * end, GREEN, 1.5)
        screen.alpha = 255


def _tag_spot(x, y, w, h):
    """Top-left of the tag: beside the aircraft if it fits, else below or above."""
    left, right = CX - BEZEL_R, INFO_X - 8
    top, bottom = CY - BEZEL_R, CY + BEZEL_R
    spots = ((x + 15, y - 7), (x - 15 - w, y - 7), (x - w // 2, y + 15), (x - w // 2, y - 15 - h))
    aim = _view["on"] and not _view["follow"]     # the crosshair is up: the tag keeps off the box a pick looks in
    p = skyview.AIM_PX
    for tx, ty in spots:
        if tx >= left and tx + w <= right and ty >= top and ty + h <= bottom and not (aim and _overlaps(tx, ty, w, h, CX - p, CY - p, 2 * p, 2 * p)):
            break
    return int(max(left, min(right - w, tx))), int(max(top, min(bottom - h, ty)))


# ---- info column ----------------------------------------------------------

def _wrap(s, max_w, f=F_BODY):
    lines, cur = [], ""
    for word in s.split(" "):
        t = cur + " " + word if cur else word
        if cur and ui.width(t, f) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = t
    return lines + [cur] if cur else lines


def _lines(s, y, step, col, f=F_BODY):
    """Wrapped text in the info column, one line per step, and the y below it. Stops above the count."""
    for line in _wrap(s, INFO_R - INFO_X, f):
        if y > 160:
            break
        ui.text(ui.fit(line, INFO_R - INFO_X, f), INFO_X, y, col, f)
        y += step
    return y


def _info(app, a, n, metric):
    m = app.model
    wide = INFO_R - INFO_X
    waiting = app.feed.rows_ms is None
    if a is None:
        if waiting:                                        # nothing has answered yet, so say so
            ui.sans("Running...", INFO_X, 40, 20, TEXT)
            _lines(app.feed.note, 66, 15, TEXT_2)
        else:
            ui.caps("(0 rows)", INFO_X, 28, TEXT_3)
            ui.sans("Success.", INFO_X, 40, 20, TEXT)
            y = _lines("No rows returned", 66, 15, TEXT_2)
            where = ("%d in range, filtered out" % m.hidden if m.hidden else
                     "nothing within %s %s of %s" % (ui.reach_text(m.range_nm, metric), "km" if metric else "nm", m.home_label or "home"))
            _lines(where.upper(), y + 6, 11, TEXT_3, F_CAPS)
    else:
        row, col = ui.row_tag(m, a)
        ui.caps(row, INFO_X, 28, col)
        ui.sans(ui.sans_fit(a.label, 20, wide), INFO_X, 40, 20, TEXT)
        ui.text(ui.fit(a.kind, wide), INFO_X, 66, TEXT_2)
        if a.emergency:
            w = ui.pill(INFO_X, 84, "SQK " + a.sqk, RED, RED_TINT, ui.LEFT, RED)
        else:
            w = ui.phase_pill(INFO_X, 84, a)
        if a.military and w + 4 + ui.width("MIL", F_CAPS) + 12 <= wide:
            ui.pill(INFO_X + w + 4, 84, "MIL", VIOLET, VIOLET_TINT)
        _readouts(a, 108, metric)

    big = ui.sans("--" if waiting else "%d" % n, INFO_X, 176, 20, TEXT)
    ui.caps("matching" if m.active else "in range", INFO_X + big + 6, 186, TEXT_3)
    ui.caps("dist < %s %s" % (ui.reach_text(m.range_nm, metric), "km" if metric else "nm"), INFO_X, 205, TEXT_3)


def _readouts(a, y, metric):
    """ALT, SPD, DIST and BRG as a table: label, number, unit."""
    alt, alt_u = ui.alt_text(a.alt, metric)
    spd, spd_u = ui.speed_text(a.gs, metric)
    dist, dist_u = ui.dist_text(a.dist, metric)
    rows = (("ALT", alt, alt_u, alt_color(a.alt) if a.alt > 0 else TEXT),
            ("SPD", spd, spd_u, TEXT),
            ("DIST", dist, dist_u, TEXT),
            ("BRG", "%03d°" % (int(a.brg) % 360), skygeo.compass(a.brg), TEXT))
    for label, value, unit, col in rows:
        ui.caps(label, INFO_X, y + 3, TEXT_3)
        ui.text(value, VALUE_R, y, col, F_BODY, 0, ui.RIGHT)
        if unit:
            uw = ui.caps(unit, UNIT_X, y + 3, TEXT_3)
            if label == "ALT" and abs(a.vr) >= 100:                # climbing or descending
                ui.tri(UNIT_X + uw + 7, y + 7, 3, GREEN if a.vr > 0 else AMBER, a.vr > 0)
        y += 16
