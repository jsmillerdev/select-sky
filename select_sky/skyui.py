"""Drawing kit shared by every view: type, chips, glyphs and the app chrome."""

import time
from array import array

from badgeware import *

import skygeo
from skytheme import *

W, H = 320, 240
TOP = 22          # height of the status bar
BOTTOM = 222      # top edge of the key-hint bar
FRESH_MS = 1600   # how long the count of newly arrived rows stays up
SLIDE_MS = 260    # how long a new aircraft takes to slide in
LEFT, CENTER_X, RIGHT = 0, 1, 2

_panels, _discs, _rings, _bolts = {}, {}, {}, {}
_planes = [None, None, None]
_fits, _pill_w, _hints = {}, {}, {}      # measured once: fitted text, pill label widths, key legends
_clock = [None, None, "", 0]             # minute and offset last formatted, their text and width


def _at(s, x, y, rot=0, scale=1):
    m = mat3().translate(x, y)
    if rot:
        m = m.rotate(rot)
    if scale != 1:
        m = m.scale(scale)
    s.transform = m
    return s


# ---- text -----------------------------------------------------------------

def width(s, f=F_BODY, size=0):
    screen.font = f
    return screen.measure_text(s, font_size=size)[0] if size else screen.measure_text(s)[0]


def text(s, x, y, col=TEXT, f=F_BODY, size=0, align=LEFT):
    """Draw s and return its width. align anchors x at the left, centre or right."""
    screen.font = f
    screen.pen = col
    if align == LEFT:                   # the rect that screen.text returns already carries the width
        return (screen.text(s, int(x), int(y), size) if size else screen.text(s, int(x), int(y))).w
    w = screen.measure_text(s, font_size=size)[0] if size else screen.measure_text(s)[0]
    x -= w / 2 if align == CENTER_X else w
    if size:
        screen.text(s, int(x), int(y), size)
    else:
        screen.text(s, int(x), int(y))
    return w


def _sans_face(pt):
    if F_SANS:
        return F_SANS, pt
    return (F_HUGE if pt >= 24 else F_BOLD if pt >= 15 else F_BODY), 0


def sans(s, x, y, pt, col=TEXT, align=LEFT):
    """Large antialiased type at pt points; pixel faces stand in without Mona Sans."""
    f, size = _sans_face(pt)
    return text(s, x, y, col, f, size, align)


def sans_width(s, pt):
    f, size = _sans_face(pt)
    return width(s, f, size)


def caps(s, x, y, col=TEXT_3, align=LEFT):
    """Small uppercase label, the Supabase eyebrow style."""
    return text(s.upper(), x, y, col, F_CAPS, 0, align)


def fit(s, max_w, f=F_BODY, size=0):
    """s, shortened with an ellipsis until it fits max_w pixels. A long text costs a
    measure per letter cut, so the answer is remembered."""
    key = (s, max_w, f, size)
    out = _fits.get(key)
    if out is None:
        if len(_fits) > 128:
            _fits.clear()
        out = s
        if width(s, f, size) > max_w:
            while out and width(out + "...", f, size) > max_w:
                out = out[:-1]
            out += "..."
        _fits[key] = out
    return out


def sans_fit(s, pt, max_w):
    """s in the large face, shortened with an ellipsis until it fits max_w pixels."""
    f, size = _sans_face(pt)
    return fit(s, max_w, f, size)


# ---- numbers and units ----------------------------------------------------

def commas(n):
    n = int(n)
    s = str(abs(n))
    out = ""
    while len(s) > 3:
        out = "," + s[-3:] + out
        s = s[:-3]
    return ("-" if n < 0 else "") + s + out


def alt_text(alt, metric=False):
    """(value, unit) for an altitude in feet; 0 is on the ground, below 0 unknown."""
    if alt < 0:
        return "---", ""
    if alt == 0:
        return "GND", ""
    return (commas(alt * 0.3048), "m") if metric else (commas(alt), "ft")


def flight_level(alt, metric=False):
    """Compact altitude for tables: FL350, 4,500 or GND."""
    if alt < 0:
        return "---"
    if alt == 0:
        return "GND"
    if metric:
        return commas(alt * 0.3048)
    return "FL%03d" % (alt // 100) if alt >= 18000 else commas(alt)


def speed_text(gs, metric=False):
    if gs < 0:
        return "---", ""
    return (str(int(gs * 1.852)), "km/h") if metric else (str(int(gs)), "kt")


def dist_text(nm, metric=False):
    v = nm * 1.852 if metric else nm
    return ("%.1f" % v if v < 100 else str(int(v))), ("km" if metric else "nm")


def rate_text(fpm, metric=False):
    if abs(fpm) < 100:
        return "level", ""
    return ("%+.1f" % (fpm * 0.00508), "m/s") if metric else ("%+d" % (int(round(fpm / 100.0)) * 100), "fpm")


def clock_text(unix, tz_s=None):
    """HH:MM in local time when the offset is known, else UTC with a Z."""
    t = time.gmtime(int(unix) + (tz_s or 0))
    return "%02d:%02d%s" % (t[3], t[4], "" if tz_s is not None else "Z")


# ---- primitives -----------------------------------------------------------

def box(x, y, w, h, col):
    screen.pen = col
    screen.rectangle(int(x), int(y), int(w), int(h))


def panel(x, y, w, h, col=PANEL, r=5):
    """Flat rounded card."""
    k = (int(w) << 16) | (int(h) << 8) | int(r)        # h and r stay below 256
    s = _panels.get(k)
    if s is None:
        s = _panels[k] = shape.rounded_rectangle(0, 0, w, h, r)
    screen.pen = col
    screen.shape(_at(s, x, y))


def disc(x, y, r, col):
    k = int(r * 2 + 0.5)            # half-pixel steps keep the shape cache small
    s = _discs.get(k)
    if s is None:
        s = _discs[k] = shape.circle(0, 0, k / 2.0)
    screen.pen = col
    screen.shape(_at(s, x, y))


def ring(x, y, r, col, w=1):
    k = (int(r * 2 + 0.5) << 8) | int(w * 2)
    s = _rings.get(k)
    if s is None:
        s = _rings[k] = shape.circle(0, 0, int(r * 2 + 0.5) / 2.0).stroke(w)
    screen.pen = col
    screen.shape(_at(s, x, y))


def line(x1, y1, x2, y2, col, w=1):
    screen.pen = col
    screen.shape(shape.line(x1, y1, x2, y2, w))


def tri(x, y, size, col, up=True):
    """Small filled triangle centred on (x, y): the fonts have no arrows."""
    s = size if up else -size
    screen.pen = col
    screen.triangle(int(x), int(y - s), int(x - size), int(y + s), int(x + size), int(y + s))


def chevron(x, y, size, col):
    screen.pen = col
    screen.triangle(int(x + size), int(y), int(x - size), int(y - size), int(x - size), int(y + size))


def pill(x, y, label, fg=TEXT_2, bg=RAISED, align=LEFT, dot=None):
    """Rounded status chip with caps text. Returns its width."""
    label = label.upper()
    w = _pill_w.get(label)
    if w is None:
        if len(_pill_w) > 48:
            _pill_w.clear()
        w = _pill_w[label] = int(width(label, F_CAPS))
    w += 12 + (8 if dot else 0)
    if align == RIGHT:
        x -= w
    elif align == CENTER_X:
        x -= w // 2
    panel(x, y, w, 13, bg, 6)
    if dot:
        disc(x + 8, y + 6.5, 2.5, dot)
    text(label, x + (14 if dot else 6), y + 1, fg, F_CAPS)
    return w


def keycap(x, y, label, col=TEXT_2):
    panel(x, y, 13, 13, RAISED, 3)
    text(label, x + 6.5, y + 1, col, F_CAPS, 0, CENTER_X)
    return 13


def bar(x, y, w, h, frac, fg=GREEN, bg=RAISED):
    """Flat progress bar; frac is 0..1."""
    box(x, y, w, h, bg)
    box(x, y, max(0, min(1, frac)) * w, h, fg)


def ping(x, y, phase, col=GREEN):
    """Supabase 'realtime' dot: a solid dot with a ring that expands and fades.

    phase runs 0..1 once per ping; pass 1 or more for the resting dot.
    """
    if 0 <= phase < 1:
        screen.alpha = int(150 * (1 - phase))
        ring(x, y, 3 + 6 * phase, col, 1.5)
        screen.alpha = 255
    disc(x, y, 3, col)


# ---- glyphs ---------------------------------------------------------------

_BOLT_LIGHT = (0.4156, 0.0166, 0.4479, 0.0001, 0.4805, 0.0109, 0.4957, 0.0431, 0.4997, 0.6440,
               0.0900, 0.6440, 0.0279, 0.6199, 0.0004, 0.5644, 0.0196, 0.5021)
_BOLT_DARK = (0.5844, 0.9834, 0.5521, 0.9999, 0.5195, 0.9891, 0.5043, 0.9569, 0.4951, 0.3560,
              0.9100, 0.3560, 0.9721, 0.3801, 0.9996, 0.4356, 0.9804, 0.4979)
_AIRLINER = (0, -8, 1.3, -5.5, 1.3, -1.6, 8, 3, 8, 4.6, 1.3, 2.4, 1.1, 5.6, 3.4, 7.6, 3.4, 8.6,
             0, 7.8, -3.4, 8.6, -3.4, 7.6, -1.1, 5.6, -1.3, 2.4, -8, 4.6, -8, 3, -1.3, -1.6, -1.3, -5.5)
_DART = (0, -7, 4.5, 5.5, 0, 2.8, -4.5, 5.5)
_ROTOR = (0, -6, 1.6, -1.6, 6, 0, 1.6, 1.6, 1, 7, -1, 7, -1.6, 1.6, -6, 0, -1.6, -1.6)


def _poly(points, sx=1, sy=1):
    a = array("f")
    for i in range(0, len(points), 2):
        a.append(points[i] * sx)
        a.append(points[i + 1] * sy)
    return shape.custom(a)


def bolt(x, y, h, lit=GREEN, shade=GREEN_FACE):
    """The Supabase mark, h pixels tall, with its top-left corner at (x, y)."""
    w = h * 0.97356
    pair = _bolts.get(h)
    if pair is None:
        pair = _bolts[h] = (_poly(_BOLT_DARK, w, h), _poly(_BOLT_LIGHT, w, h))
    screen.pen = shade
    screen.shape(_at(pair[0], x, y))
    screen.pen = lit
    screen.shape(_at(pair[1], x, y))


def plane(x, y, heading, col, scale=1.0, kind=0):
    """Aircraft glyph pointing along heading. kind: 0 airliner, 1 dart, 2 rotorcraft."""
    s = _planes[kind]
    if s is None:
        s = _planes[kind] = _poly(_AIRLINER if kind == 0 else _DART if kind == 1 else _ROTOR)
    screen.pen = col
    screen.shape(_at(s, x, y, heading, scale))


def battery(x, y, level, charging, col=TEXT_3):
    """16 x 8 battery outline with a level fill."""
    box(x, y, 14, 8, col)
    box(x + 14, y + 2, 2, 4, col)
    box(x + 1, y + 1, 12, 6, BG_DEEP)
    fill = GREEN if charging else (AMBER if level < 20 else TEXT_2)
    box(x + 2, y + 2, max(1, int(10 * level / 100)), 4, fill)


# ---- app chrome -----------------------------------------------------------

STATUS_STYLE = {
    "LIVE": (GREEN_HI, GREEN_TINT, GREEN),
    "DEMO": (AMBER, AMBER_TINT, AMBER),
    "STALE": (AMBER, AMBER_TINT, AMBER),
    "WAIT": (TEXT_2, RAISED, TEXT_3),
}


def topbar(app, title):
    """Breadcrumb on the left; feed status, clock and battery on the right."""
    box(0, 0, W, TOP, BG_DEEP)
    bolt(6, 4, 14)
    x = 25
    x += text("sky", x, 4, TEXT_3) + 4
    x += text("/", x, 4, TEXT_4) + 4
    text(title.lower(), x, 4, TEXT)

    x = W - 6
    battery(x - 16, 7, app.battery, app.charging)
    x -= 22
    now = app.feed.clock()
    if now is not None:
        tz, c = app.feed.tz_s, _clock
        if c[0] != now // 60 or c[1] != tz:         # the text and its width only change once a minute
            s = clock_text(now, tz)
            c[0], c[1], c[2], c[3] = now // 60, tz, s, width(s)
        x -= c[3]
        text(c[2], x, 4, TEXT_2)
        x -= 7
    status = app.feed.status
    fg, bg, dot = STATUS_STYLE.get(status, STATUS_STYLE["WAIT"])
    pw = pill(x, 4, "SYNC" if app.feed.busy else status, fg, bg, RIGHT)
    # The ping replaces a static dot: it fires once on every fresh batch of rows.
    if status == "LIVE" or status == "DEMO":
        ping(x - pw - 8, 10.5, app.since_rows / 900.0, dot)
        if app.now - app.fresh_ms < FRESH_MS:
            caps("+%d" % app.fresh, x - pw - 18, 5, dot, RIGHT)


def _hint_layout(app, action, updown, left, right):
    """The key legend's labels in caps, the left edge of the C label, and each centred
    part as (key, x, label); the key is "" for the up/down pair."""
    parts = []
    if action:
        parts.append(("B", action.upper()))
    if updown:
        parts.append(("", updown.upper()))
    total = sum((17 if k else 15) + width(v, F_CAPS) for k, v in parts) + 12 * (len(parts) - 1)
    x = (W - total) // 2
    placed = []
    for k, v in parts:
        placed.append((k, x, v))
        x += (17 if k else 15) + width(v, F_CAPS) + 12
    c_label = (right or app.view_name(1)).upper()
    return (left or app.view_name(-1)).upper(), c_label, W - 6 - 13 - 4 - width(c_label, F_CAPS), placed


def hintbar(app, action=None, updown=None, left=None, right=None):
    """Key legend. A and C step through views unless a modal view relabels them."""
    key = (app.view, action, updown, left, right)
    lay = _hints.get(key)
    if lay is None:
        if len(_hints) > 48:
            _hints.clear()
        lay = _hints[key] = _hint_layout(app, action, updown, left, right)
    a_label, c_label, c_x, parts = lay
    box(0, BOTTOM, W, H - BOTTOM, BG_DEEP)
    y = BOTTOM + 3
    keycap(6, y, "A")
    text(a_label, 23, y + 1, TEXT_3, F_CAPS)
    keycap(W - 6 - 13, y, "C")
    text(c_label, c_x, y + 1, TEXT_3, F_CAPS)
    for k, x, v in parts:
        if k:
            keycap(x, y, k, GREEN)
        else:
            tri(x + 4, y + 3.5, 2.5, TEXT_2, True)
            tri(x + 4, y + 9.5, 2.5, TEXT_2, False)
        text(v, x + (17 if k else 15), y + 1, TEXT_2, F_CAPS)


def empty_state(title, hint, y=96):
    """Centred message for a view with nothing to show, in psql's voice."""
    bolt(W / 2 - 12, y - 34, 24, GREEN_MID, GREEN_DIM)
    text(title, W / 2, y, TEXT, F_BODY, 0, CENTER_X)
    text(hint, W / 2, y + 18, TEXT_3, F_BODY, 0, CENTER_X)


def no_rows(app, y=96):
    """The empty sky, or the wait for a first answer, said the way psql would."""
    if app.feed.rows_ms is None:
        empty_state("Running...", app.feed.note, y)
    else:
        r, unit = dist_text(app.model.range_nm, app.settings["metric"])
        r = r[:-2] if r.endswith(".0") else r
        empty_state("Success. No rows returned", "Nothing within %s %s of %s" % (r, unit, app.model.home_label or "home"), y)


def bearing_text(brg):
    return "%s %03d°" % (skygeo.compass(brg), int(brg) % 360)


# ---- shared by several views --------------------------------------------------

def cycle_bar(app):
    """The 2 px bar under the status bar that counts down the auto-cycle, while it is stepping."""
    m = app.model
    if m.auto and len(m.order) > 1:
        box(0, TOP, W * app.cycle_fraction(), 2, GREEN_MID)


def row_tag(m, a):
    """('row N of M' or 'beyond range', colour) for the selection: grey while the app cycles, green once locked."""
    col = TEXT_3 if m.auto else GREEN
    if a in m.order:
        return "row %d of %d" % (m.order.index(a) + 1, len(m.order)), col
    return "beyond range", col


def glide(dt_ms, half_ms):
    """Share of the remaining gap an ease covers in dt_ms when it closes half of it every half_ms."""
    return 1 - 0.5 ** (min(100, dt_ms) / half_ms)


def slide_in(dt_ms):
    """(x offset, alpha) of an aircraft that began sliding in from the right dt_ms ago."""
    t = min(1.0, dt_ms / SLIDE_MS)
    return int((1 - t) * (1 - t) * 26), int(255 * t)


def reach_text(nm, metric):
    """A range in nautical miles, or kilometres when metric, without a needless .0."""
    v = round(nm * 1.852 if metric else nm, 1)
    return "%d" % v if v == int(v) else "%.1f" % v


def phase_pill(x, y, a):
    """The flight phase chip, grey when the altitude is unknown. Returns its width."""
    known = a.alt >= 0
    return pill(x, y, a.phase, GREEN_HI if known else TEXT_2, GREEN_TINT if known else RAISED)
