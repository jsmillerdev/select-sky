"""TRACK: follow one flight and tell the wearer where to look.

The subject is the tracked callsign, wherever it is in the world, or else the
selected aircraft. A sky dome says where to look, two sparklines show the climb
and the speed, and the bottom card shows the route, or the closest approach to
home when no route is known.
"""

import math

from badgeware import *

import skygeo
import skyui as ui
from skyfeed import TRACK_EVERY_MS
from skytheme import *

NAME = "TRACK"
PULSE_MS = 1800
SEE_NM = 60             # farther than this is too far to spot
HORIZON_DEG = 1.0       # lower than this is behind the horizon
CPA_NM = 300            # past this a straight-line closest approach means nothing
STALE_S = 75            # a tracked flight not heard from for this long is flagged

# Layout: 8 px side margins, 4 px between cards.
HEAD_Y, SUB_Y = 21, 49
MID_Y, MID_H = 66, 104
BOT_Y, BOT_H = 174, 40
LEFT_X, LEFT_W = 8, 150
RIGHT_X, RIGHT_W = 162, 150
DOME_R = 30

_shown = [None, 0]      # hex of the aircraft on screen, and when it arrived
_memo = {}


def _cached(slot, key, make, *args):
    """make(*args) once per key in each slot, so per-frame work only draws."""
    hit = _memo.get(slot)
    if hit is None or hit[0] != key:
        hit = _memo[slot] = (key, make(*args))
    return hit[1]


def update(app):
    m = app.model
    if badge.pressed(BUTTON_B):
        _toggle(app, m.tracked if m.track else m.selected())
    tracking = bool(m.track)
    if not tracking:
        app.nav()

    a = m.tracked if tracking else m.selected()
    ui.topbar(app, NAME)
    ui.hintbar(app, "STOP" if tracking else "TRACK" if a and a.cs else None, "FLIGHT" if a and not tracking else None)
    if a is None:
        if tracking:
            _searching(app)
        else:
            ui.no_rows(app)
        return

    metric = app.settings["metric"]
    if a.hex != _shown[0]:
        _shown[0], _shown[1] = a.hex, app.now
    ox, fade = ui.slide_in(app.now - _shown[1])
    screen.alpha = fade

    dist, brg = a.dist, a.brg
    elev = skygeo.elevation(a.alt, dist)
    _header(app, a, tracking, ox)
    _sky(app, a, dist, brg, elev, ox, fade, metric)
    _flight(a, ox, metric)
    r = m.route(a)
    ui.panel(8 + ox, BOT_Y, 304, BOT_H)
    if r:
        _route(m, a, r, 8 + ox, BOT_Y, metric)
    else:
        _closest(m, a, dist, brg, 8 + ox, BOT_Y, metric)
    screen.alpha = 255

    if not tracking:
        ui.cycle_bar(app)


def _toggle(app, a):
    """B follows the shown callsign worldwide, or lets it go."""
    m = app.model
    if m.track:
        name = m.track
        app.set_track("")
        if a is not None and a in m.order:
            m.select(a.hex)             # keep showing it, now as the selection
        app.toast("Stopped tracking " + name)
    elif a is not None and a.cs:
        m.select(a.hex)                 # stop the auto cycle moving the selection
        app.set_track(a.cs)
        m.tracked = a                   # the feed would find it next update; skip the blank frame
        app.toast("Tracking " + a.cs)
    elif a is not None:
        app.toast("No callsign to track")


# ---- geometry ---------------------------------------------------------------

def _visible(a, dist, elev):
    return a.alt > 0 and dist <= SEE_NM and elev >= HORIZON_DEG


def _plot(brg, elev, cx, cy):
    """Dome position: zenith at the centre, the horizon on the rim."""
    r = DOME_R * (90.0 - min(90.0, max(0.0, elev))) / 90.0
    t = math.radians(brg)
    return cx + r * math.sin(t), cy - r * math.cos(t)


def _look(a, dist, brg, elev):
    """The one sentence the wearer needs, and a shorter form for when it will not fit."""
    c = skygeo.compass(brg)
    if a.alt == 0:
        return "On the ground, " + c, "On the ground"
    if a.alt < 0:
        return "Height unknown, " + c, "Height unknown"
    if dist > SEE_NM:
        return "Too far to see, " + c, "Too far to see"
    if elev < HORIZON_DEG:
        return "Below horizon, " + c, "Below horizon"
    if elev >= 80:
        return "Look straight up", "Look up"
    return "Look %s, %d° up" % (c, int(elev + 0.5)), "Look " + c


def _fit_look(forms):
    """The long sentence at the largest size that fits the card, else the short one."""
    long_form, short = forms
    for s, pt in ((long_form, 15), (long_form, 12), (short, 12)):
        if ui.sans_width(s, pt) <= LEFT_W - 16:
            break
    return s, pt


def _closest_pass(m, a):
    """Straight-line closest approach to home: ('ok', nm, minutes, bearing), or a reason."""
    if a.trk < 0 or a.gs < 0:
        return "unknown", 0, 0, 0
    if a.gs < 15:
        return "still", 0, 0, 0
    ex, ny = skygeo.offset_nm(m.home[0], m.home[1], a.lat, a.lon)
    t = math.radians(a.trk)
    vx, vy = a.gs * math.sin(t), a.gs * math.cos(t)
    h = -(ex * vx + ny * vy) / (vx * vx + vy * vy)
    if h <= 0:
        return "away", 0, 0, 0
    px, py = ex + vx * h, ny + vy * h
    return "ok", math.sqrt(px * px + py * py), h * 60.0, math.degrees(math.atan2(px, py)) % 360


def _span(minutes):
    n = max(1, int(minutes + 0.5))
    return "%d min" % n if n < 60 else "%dh %02dm" % (n // 60, n % 60)


def _miles(nm, metric):
    v, u = ui.dist_text(nm, metric)
    return (ui.commas(int(v)) if v.isdigit() else v), u


# ---- header -----------------------------------------------------------------

def _name(label):
    """(text, pt, width) for the big callsign: the largest size that fits, else cut short."""
    for pt in (24, 20, 17):
        if ui.sans_width(label, pt) <= 150:
            return label, pt, ui.sans_width(label, pt)
    while len(label) > 1 and ui.sans_width(label + "..", 17) > 150:
        label = label[:-1]
    return label + "..", 17, ui.sans_width(label + "..", 17)


def _sub(a, tag):
    """Operator and type, fitted beside the tag at the right."""
    return ui.fit("%s · %s" % (a.operator, a.kind), 292 - (ui.width(tag.upper(), F_CAPS) if tag else 0))


def _header(app, a, tracking, ox):
    label, pt, w = _cached("name", a.label, _name, a.label)
    ui.sans(label, 8 + ox, HEAD_Y + (24 - pt) // 3, pt, TEXT)
    x = 8 + ox + w + 10
    if tracking:
        x += ui.pill(x, HEAD_Y + 11, "tracking", GREEN_HI, GREEN_TINT, dot=GREEN) + 4
    else:
        x += ui.pill(x, HEAD_Y + 11, "selected", TEXT_2, RAISED) + 4
    if a.military and x + 40 < 312:
        x += ui.pill(x, HEAD_Y + 11, "mil", VIOLET, VIOLET_TINT) + 4
    if a.emergency and x + 90 < 312:
        x += ui.pill(x, HEAD_Y + 11, "squawk " + a.sqk, RED, RED_TINT) + 4

    m = app.model
    if tracking:
        age = int((app.now - a.seen_ms) / 1000)
        note = "seen %s ago" % ("%d s" % age if age < 100 else "%d min" % (age // 60))
        col = AMBER if age > STALE_S else TEXT_3
    else:
        note, col = ui.row_tag(m, a)
    tag, tag_col = (a.reg, TEXT_4) if a.reg and a.reg != a.label else ("", TEXT_4)
    if note and x + ui.width(note.upper(), F_CAPS) + 8 <= 312 + ox:
        ui.caps(note, 312 + ox, HEAD_Y + 12, col, ui.RIGHT)
    elif note and tracking:                     # a long name leaves no room up here, and the age matters most
        tag, tag_col = note, col

    ui.text(_sub(a, tag), 8 + ox, SUB_Y, TEXT_2)
    if tag:
        ui.caps(tag, 312 + ox, SUB_Y + 1, tag_col, ui.RIGHT)


# ---- left card: where to look -----------------------------------------------

def _dome(cx, cy):
    """The empty sky: zenith at the centre, elevation rings at 30 and 60 degrees."""
    R = DOME_R
    ui.disc(cx, cy, R, BG_DEEP)
    ui.box(cx - R, cy, 2 * R, 1, LINE)
    ui.box(cx, cy - R, 1, 2 * R, LINE)
    ui.ring(cx, cy, R * 2 // 3, LINE)
    ui.ring(cx, cy, R // 3, LINE)
    ui.ring(cx, cy, R, LINE_HI)
    for r, label in ((R * 2 // 3, "30"), (R // 3, "60")):    # elevation, read down the south spoke
        ui.box(cx + 2, cy + r - 4, 13, 9, BG_DEEP)
        ui.caps(label, cx + 4, cy + r - 3, TEXT_4)
    # Each letter sits on the rim and interrupts it: card colour outside, dome colour inside.
    for bx, by, bw, bh in ((cx - 6, cy - R - 6, 12, 6), (cx - 6, cy + R, 12, 6),
                           (cx + R, cy - 5, 6, 10), (cx - R - 6, cy - 5, 6, 10)):
        ui.box(bx, by, bw, bh, PANEL)
    for bx, by, bw, bh in ((cx - 6, cy - R, 12, 6), (cx - 6, cy + R - 6, 12, 6),
                           (cx + R - 6, cy - 5, 6, 10), (cx - R, cy - 5, 6, 10)):
        ui.box(bx, by, bw, bh, BG_DEEP)
    for s, dx, dy in (("N", 0, -R), ("E", R, 0), ("S", 0, R), ("W", -R, 0)):
        ui.caps(s, cx + dx + 0.5, cy + dy - 4, TEXT if s == "N" else TEXT_3, ui.CENTER_X)


def _trail_pts(m, a):
    """Recent path as dome offsets from the centre, oldest first."""
    out = []
    for lat, lon, alt in a.trail:
        d, b = skygeo.dist_brg(m.home[0], m.home[1], lat, lon)
        out.append(_plot(b, skygeo.elevation(alt, d), 0, 0))
    return out


def _sky(app, a, dist, brg, elev, ox, fade, metric):
    m = app.model
    x, y = LEFT_X + ox, MID_Y
    ui.panel(x, y, LEFT_W, MID_H)
    cx, cy = x + 44, y + 40
    _dome(cx, cy)

    seen = _visible(a, dist, elev)
    col = alt_color(a.alt) if seen else TEXT_4
    # Recent path, fading in towards the aircraft, which sits at its dead-reckoned position now.
    key = (a.hex, len(a.trail), a.trail[-1] if a.trail else 0, m.home)
    pts = [(cx + px, cy + py) for px, py in _cached("trail", key, _trail_pts, m, a)]
    here = _plot(brg, elev if seen else 0, cx, cy)
    pts.append(here)
    screen.pen = col
    for i in range(len(pts) - 1):
        screen.alpha = (50 + 150 * (i + 1) // (len(pts) - 1)) * fade // 255
        screen.line(int(pts[i][0]), int(pts[i][1]), int(pts[i + 1][0]), int(pts[i + 1][1]))
        ui.disc(pts[i][0], pts[i][1], 1.5, col)
    screen.alpha = fade

    if seen:                                    # a ring that opens out from the aircraft
        ph = (app.now % PULSE_MS) / float(PULSE_MS)
        screen.alpha = int(160 * (1 - ph)) * fade // 255
        ui.ring(here[0], here[1], 5 + int(ph * 8), col, 1)
        screen.alpha = fade
    if a.trk >= 0:
        ui.plane(here[0], here[1], a.trk, col, 0.8, a.glyph)
    else:
        ui.disc(here[0], here[1], 3, col)

    # Numbers beside the dome.
    sx = x + 88
    d, du = _miles(dist, metric)
    el = "---" if a.alt <= 0 or elev < 0 else "%.1f°" % elev if elev < 10 else "%d°" % int(elev + 0.5)
    for i, (label, value, unit) in enumerate((("BRG", "%03d°" % (int(brg) % 360), ""),
                                              ("ELEV", el, ""),
                                              ("DIST", d, du.upper()))):
        sy = y + 5 + i * 25
        ui.caps(label, sx, sy, TEXT_3)
        if unit:
            ui.caps(unit, x + LEFT_W - 8, sy, TEXT_3, ui.RIGHT)
        ui.sans(value, sx, sy + 6, 15 if len(value) <= 5 else 12, TEXT)

    # The sentence is the point of the view, so it gets the biggest type on the card.
    forms = _look(a, dist, brg, elev)
    sentence, pt = _cached("look", forms, _fit_look, forms)
    ui.sans(sentence, x + 8, y + MID_H - 24 + (15 - pt) // 2, pt, TEXT)


# ---- right card: altitude and speed history ------------------------------------

def _flight(a, ox, metric):
    x, y = RIGHT_X + ox + 8, MID_Y
    ui.panel(RIGHT_X + ox, y, RIGHT_W, MID_H)
    w = RIGHT_W - 16
    alt, alt_u = ui.alt_text(a.alt, metric)
    spd, spd_u = ui.speed_text(a.gs, metric)
    vs, vs_u = ui.rate_text(a.vr, metric)
    _metric("ALT", alt, alt_u, x, y + 8, w)
    _spark("alt", a, a.alts, x, y + 27, w, 12, alt_color, 2000, "building history" if a.alt >= 0 else "no altitude")
    _metric("SPD", spd, spd_u, x, y + 44, w)
    _spark("spd", a, a.speeds, x, y + 63, w, 12, SKY, 40)
    _metric("V/S", vs, vs_u, x, y + 80, w, None if abs(a.vr) < 100 else a.vr > 0)


def _metric(label, value, unit, x, y, w, arrow=None):
    """Caps label on the left, value and unit flush right, an optional arrow before the value."""
    ui.caps(label, x, y + 5, TEXT_3)
    right = x + w
    if unit:
        right -= ui.caps(unit, right, y + 5, TEXT_3, ui.RIGHT) + 3
    vw = ui.sans(value, right, y, 15, TEXT, ui.RIGHT)
    if arrow is not None:
        ui.tri(right - vw - 8, y + 9, 4, GREEN if arrow else AMBER, arrow)


def _bars(vals, cols, h, tone, min_span):
    """(offset, height, colour) for each bar over the history, interpolated to cols bars."""
    n = len(vals)
    lo, hi = min(vals), max(vals)
    if hi - lo < min_span:                      # a level flight stays a flat line
        lo = max(0, (hi + lo - min_span) / 2.0)
        hi = lo + min_span
    k = float(h) / (hi - lo)
    out = []
    for j in range(cols):
        pos = j * (n - 1) / float(cols - 1)
        i = int(pos)
        v = vals[i] + (vals[min(i + 1, n - 1)] - vals[i]) * (pos - i)
        out.append((j * 4, max(1, int((v - lo) * k + 0.5)), tone(int(v)) if callable(tone) else tone))
    return out


def _spark(slot, a, vals, x, y, w, h, tone, min_span, empty=""):
    """Bars over the history, 2 px wide and 2 px apart, the newest on the right in white."""
    n = len(vals)
    if n < 2:
        ui.box(x, y + h - 1, w, 1, LINE)
        if empty:
            ui.caps(empty, x, y + 1, TEXT_3)
        return
    cols = (w + 2) // 4
    bars = _cached(slot, (a.hex, n, vals[0], vals[-1], w), _bars, vals, cols, h, tone, min_span)
    x, base = int(x), int(y + h)
    for dx, bh, col in bars:
        screen.pen = col
        screen.rectangle(x + dx, base - bh, 2, bh)
    dx, bh, _ = bars[-1]
    screen.pen = TEXT
    screen.rectangle(x + dx, base - bh, 2, bh)


# ---- bottom card: route, or closest approach ----------------------------------

def _route(m, a, r, x, y, metric):
    o, d = r["o"], r["d"]
    wo = ui.sans(o[0], x + 8, y + 1, 15, TEXT)
    wd = ui.sans(d[0], x + 296, y + 1, 15, TEXT, ui.RIGHT)
    x0, x1 = x + 8 + wo + 10, x + 296 - wd - 10
    p = m.progress(a)                           # None until both ends are placed
    ly = y + 11
    ui.box(x0, ly, x1 - x0, 2, LINE_HI)
    ui.disc(x1, ly + 1, 2.5, LINE_HI)
    if p is None:
        ui.disc(x0, ly + 1, 2.5, LINE_HI)
    else:
        xp = x0 + (x1 - x0) * p
        ui.box(x0, ly, xp - x0, 2, GREEN)
        ui.disc(x0, ly + 1, 2.5, GREEN)
        ui.plane(xp, ly + 1, 90, GREEN_HI, 1.0)

    ty = y + 27
    flown = "%d%% flown" % int(p * 100) if p is not None else ""
    togo = eta = ""
    if d[2] or d[3]:
        left = skygeo.great_circle_nm(a.lat, a.lon, d[2], d[3])
        togo = "%s %s to go" % _miles(left, metric)
        if a.alt != 0 and a.gs >= 60:
            eta = _span(left / a.gs * 60.0)
    lw = ui.caps(flown, x + 8, ty, GREEN_HI) if flown else 0
    rw = 0
    if eta:                                     # the longest wording that leaves room for the rest
        room = 288 - lw - ui.width(togo.upper(), F_CAPS) - 24
        for lead in ("arrives in ", "in ", ""):
            if ui.width((lead + eta).upper(), F_CAPS) <= room:
                break
        rw = ui.caps(lead + eta, x + 296, ty, TEXT_2, ui.RIGHT)
    if togo:
        ui.caps(togo, (x + 8 + lw + x + 296 - rw) / 2, ty, TEXT_2, ui.CENTER_X)


def _closest(m, a, dist, brg, x, y, metric):
    state, nm, mins, at = _closest_pass(m, a) if dist <= CPA_NM else ("far", 0, 0, 0)
    home = m.home_label or "home"
    d, du = _miles(nm if state == "ok" else dist, metric)
    c = skygeo.compass(at if state == "ok" else brg)
    ui.caps(ui.fit(("closest to " + home if state == "ok" else "now from " + home).upper(), 140, F_CAPS), x + 8, y + 6, TEXT_3)
    if state == "ok" and nm < 0.3:
        ui.sans("overhead", x + 8, y + 16, 15, TEXT)           # no bearing means anything this close
    else:
        w = ui.sans(d, x + 8, y + 16, 15, TEXT)
        ui.caps(du, x + 8 + w + 3, y + 21, TEXT_3)
        ui.caps(c, x + 8 + w + 3 + ui.width(du.upper(), F_CAPS) + 6, y + 21, TEXT_2)

    ui.caps("passes in" if state == "ok" else "closest approach", x + 162, y + 6, TEXT_3)
    if state == "ok":
        ui.sans(_span(mins) if mins < 6000 else "> 99 h", x + 162, y + 16, 15, TEXT)
    else:
        note = {"away": "moving away", "still": "stationary", "unknown": "no heading", "far": "too far out"}[state]
        ui.sans(note, x + 162, y + 16, 15, TEXT_2)


# ---- nothing to show yet -------------------------------------------------------

def _searching(app):
    """A callsign is tracked but no live position has come back for it."""
    cs = app.model.track
    ph = (app.now % 1600) / 1600.0
    ui.bolt(148, 40, 24, GREEN_MID, GREEN_DIM)
    for k in range(2):
        q = (ph + k * 0.5) % 1.0
        screen.alpha = int(120 * (1 - q))
        ui.ring(160, 52, 14 + int(q * 22), GREEN, 1)
    screen.alpha = 255
    pt = 24 if ui.sans_width(cs, 24) <= 280 else 17
    ui.sans(cs, 160, 84, pt, TEXT, ui.CENTER_X)
    ui.pill(160, 118, "searching", AMBER, AMBER_TINT, ui.CENTER_X, AMBER if (app.now // 500) % 2 == 0 else AMBER_TINT)
    status = app.feed.status
    if status == "DEMO":
        hint = "The demo feed only carries its own fleet"
    elif status == "WAIT":
        hint = "Waiting for a live feed"
    else:
        hint = "Not airborne, or out of ADS-B range"
    ui.text(hint, 160, 142, TEXT_2, F_BODY, 0, ui.CENTER_X)
    if status in ("LIVE", "STALE", "WAIT"):
        ui.caps("checking again every %d s" % (TRACK_EVERY_MS // 1000), 160, 162, TEXT_3, ui.CENTER_X)
    ui.caps(ui.fit("select * from sky where cs = '%s';" % cs, 296, F_CAPS), 160, 184, TEXT_4, ui.CENTER_X)
    ui.caps("(0 rows)", 160, 198, TEXT_4, ui.CENTER_X)
