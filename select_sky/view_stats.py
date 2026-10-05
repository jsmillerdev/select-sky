"""STATS: the sky as a Reports page. Traffic counts and altitudes, or the state of the feed."""

import math

from badgeware import *

import skydata
import skyui as ui
from skytheme import *

NAME = "STATS"
PAGES = ("TRAFFIC", "FEED")
BANDS = 9                       # altitude bands from the ground up
BAND_FT = 5000                  # 45,000 ft in all
BAND_M = 1500                   # metric bands: 13.5 km in all
AXIS = (("0", "20K", "45K"), ("0", "6K", "13.5K"))
TOP_AIRLINES = 4
EASE_MS = 170.0                 # time constant for bars gliding to their targets
FADE_MS = 200

CAP_Y = 28
TILE_Y, TILE_W, TILE_H = 44, 96, 36
MID_Y = 86                      # histogram and records
HX, PITCH, BAR_W = 8, 18, 15
BASE_Y, BAR_H = 136, 26         # histogram baseline and tallest bar
RX = 184                        # records column
BOT_Y = 156                     # airlines
PANEL_Y = 88                    # feed details

# State that outlives a frame: the page, the bars as drawn, and what the model last told us.
_page = 0
_page_ms = -1000
_last_ms = None
_hist = [0.0] * BANDS
_air = [0.0] * TOP_AIRLINES
_snap_key = None
_counts = [0] * BANDS           # aircraft per altitude band
_records = ()                   # (label, value, unit, callsign) x 3, ready to draw
_top = []                       # (name, count) x up to TOP_AIRLINES
_name_w = 0                     # width of the widest airline count
_note_key = None                # (text, width) of the feed note last wrapped
_note_lines = []


def update(app):
    global _page, _page_ms
    if badge.pressed(BUTTON_B):
        _page = 1 - _page
        _page_ms = app.now
    if _page == 0:
        app.nav()

    ui.topbar(app, NAME)
    ui.hintbar(app, PAGES[1 - _page], "FLIGHT" if _page == 0 else None)

    k = _glide(app.now)
    screen.alpha = 50 + int(205 * min(1.0, (app.now - _page_ms) / FADE_MS))
    if _page == 0:
        _traffic(app, app.model, k)
    else:
        _feed(app, app.model)
    screen.alpha = 255


# ---- helpers ----------------------------------------------------------------

def _glide(now):
    """Share of the remaining distance a bar covers this frame, whatever the frame rate."""
    global _last_ms
    gap = 16 if _last_ms is None else now - _last_ms
    _last_ms = now
    return 1 - math.exp(-(gap if 0 < gap <= 100 else 16) / EASE_MS)


def _toward(values, i, target, k):
    v = values[i]
    v += (target - v) * k
    if abs(target - v) < 0.004:
        v = target
    values[i] = v
    return v


def _band_ft(metric):
    """Height of one histogram band in feet: 5,000 ft, or 1,500 m when units are metric."""
    return BAND_M / 0.3048 if metric else BAND_FT


def _caption(sql):
    ui.caps(sql, 8, CAP_Y, TEXT_4)
    for i in range(len(PAGES)):
        ui.disc(302 + i * 8, CAP_Y + 5.5, 2, GREEN if i == _page else LINE_HI)
    ui.caps(PAGES[_page], 294, CAP_Y, TEXT_3, ui.RIGHT)


def _tile(x, label, value, col=TEXT, sub="", unit=""):
    """Flat card: caps label (with a dimmer qualifier or a unit), big value below."""
    ui.panel(x, TILE_Y, TILE_W, TILE_H)
    w = ui.caps(label, x + 9, TILE_Y + 4, TEXT_3)
    if sub:
        ui.caps(sub, x + 14 + w, TILE_Y + 4, TEXT_4)
    if unit:
        ui.caps(unit, x + TILE_W - 8, TILE_Y + 4, TEXT_3, ui.RIGHT)
    pt = 20 if ui.sans_width(value, 20) <= TILE_W - 18 else 16
    ui.sans(value, x + 9, TILE_Y + 10, pt, col)


def _span(s):
    s = int(s)
    if s < 60:
        return "%ds" % s
    if s < 3600:
        return "%dm %02ds" % (s // 60, s % 60)
    return "%dh %02dm" % (s // 3600, s % 3600 // 60)


def _coords(lat, lon, exact):
    """Home as degrees: to 4 decimals (about 10 m) for an exact position, to 2 for the city-level ones."""
    form = "%.4f° %s   %.4f° %s" if exact else "%.2f° %s   %.2f° %s"
    return form % (abs(lat), "N" if lat >= 0 else "S", abs(lon), "E" if lon >= 0 else "W")


# ---- traffic page -------------------------------------------------------------

def _refresh(app, m, metric):
    """Rebuild what the page draws from the model. Only a new feed batch, a new range or a
    unit change alters it, so the frames in between reuse the strings and lists."""
    global _snap_key, _records, _top, _name_w
    key = (app.feed.rows_ms, m.range_nm, len(m.order), metric, m.stats["seen"], m.want)
    if key == _snap_key:
        return
    _snap_key = key
    st = m.stats

    band = _band_ft(metric)
    for i in range(BANDS):
        _counts[i] = 0
    for a in m.order:
        if a.alt >= 0:
            _counts[min(BANDS - 1, int(a.alt // band))] += 1

    alt, alt_u = ui.alt_text(st["high"], metric)
    spd, spd_u = ui.speed_text(st["fast"], metric)
    near, near_u = ui.dist_text(st["near"], metric)
    rows = (("HIGHEST", alt if st["high"] > 0 else "", alt_u, st["high_cs"]),
            ("FASTEST", spd if st["fast"] > 0 else "", spd_u, st["fast_cs"]),
            ("CLOSEST", near if st["near"] < 9999 else "", near_u, st["near_cs"]))
    _records = tuple((label, v or "---", u if v else "", ui.fit(who.upper(), 64, F_CAPS) if v else "")
                     for label, v, u, who in rows)

    named = [(skydata.carrier_name(code).upper(), n) for code, n in m.airlines.items()]
    named.sort(key=lambda kv: (-kv[1], kv[0]))
    _top = [(ui.fit(name, 96, F_CAPS), n) for name, n in named[:TOP_AIRLINES]]
    _name_w = int(ui.width(str(_top[0][1]), F_CAPS)) if _top else 0


def _traffic(app, m, k):
    metric = app.settings["metric"]
    waiting = app.feed.rows_ms is None          # no answer yet: say so rather than show zeros
    _refresh(app, m, metric)
    _caption("select count(*) from sky")
    st = m.stats
    for x, label, sub, n in ((8, "MATCHING" if m.active else "IN RANGE", "NOW", len(m.order)), (112, "SEEN", "SESSION", st["seen"]),
                             (216, "PEAK", "AT ONCE", st["peak"])):
        _tile(x, label, "---" if waiting else ui.commas(n), TEXT_4 if waiting else TEXT, sub)
    _histogram(m, metric, k, waiting)
    _records_column()
    _airlines(k, waiting)


def _histogram(m, metric, k, waiting):
    peak = max(_counts)
    band = _band_ft(metric)
    sel = m.selected()
    sel_band = min(BANDS - 1, int(sel.alt // band)) if sel and sel.alt >= 0 else -1

    ui.caps("altitude (%s)" % ("m" if metric else "ft"), HX, MID_Y, TEXT_3)
    if sel:
        ui.caps(ui.fit(sel.label.upper(), 64, F_CAPS), HX + BANDS * PITCH - 3, MID_Y, ui.row_tag(m, sel)[1], ui.RIGHT)

    if sel_band >= 0:                                       # the selected aircraft's band
        ui.panel(HX + sel_band * PITCH - 1, BASE_Y - BAR_H - 12, BAR_W + 2, BAR_H + 16, SELECTED, 3)
        ui.box(HX + sel_band * PITCH, BASE_Y + 1, BAR_W, 2, GREEN)
    for i in range(BANDS):
        x = HX + i * PITCH
        n = _counts[i]
        h = int(_toward(_hist, i, n / peak if peak else 0.0, k) * BAR_H + 0.5)
        if not n:
            ui.box(x, BASE_Y - 2, BAR_W, 2, RAISED)
            continue
        h = max(h, 2)
        ui.box(x, BASE_Y - h, BAR_W, h, alt_color(i * band + band / 2))
        ui.caps(str(n), x + BAR_W / 2, BASE_Y - h - 11, GREEN if i == sel_band else TEXT_3, ui.CENTER_X)
    ui.box(HX, BASE_Y, BANDS * PITCH - 3, 1, LINE)

    ends = AXIS[1 if metric else 0]
    ui.caps(ends[0], HX, BASE_Y + 6, TEXT_3)
    ui.caps(ends[1], HX + 4 * PITCH - 2, BASE_Y + 6, TEXT_3, ui.CENTER_X)
    ui.caps(ends[2], HX + BANDS * PITCH - 3, BASE_Y + 6, TEXT_3, ui.RIGHT)
    if not peak:
        ui.text("Running..." if waiting else ("No matching aircraft" if m.active else "No aircraft in range") if not m.order else "Altitude unknown",
                HX + (BANDS * PITCH - 3) / 2, BASE_Y - 25, TEXT_4, F_BODY, 0, ui.CENTER_X)


def _records_column():
    for i, (label, value, unit, who) in enumerate(_records):
        y = MID_Y + i * 22
        ui.caps(label, RX, y, TEXT_3)
        if who:
            ui.caps(who, 312, y, TEXT_2, ui.RIGHT)
        w = ui.text(value, RX, y + 9, TEXT if unit else TEXT_4)
        if unit:
            ui.caps(unit, RX + w + 4, y + 11, TEXT_3)


def _airlines(k, waiting):
    ui.caps("top airlines", 8, BOT_Y, TEXT_3)
    ui.caps("(%d row%s)" % (len(_top), "" if len(_top) == 1 else "s"), 312, BOT_Y, TEXT_4, ui.RIGHT)
    bar_w = 312 - 112 - _name_w - 10        # leave room for the widest count
    for i in range(TOP_AIRLINES):
        if i >= len(_top):
            _air[i] = 0.0
            continue
        name, n = _top[i]
        y = BOT_Y + 12 + i * 12
        ui.caps(name, 8, y, TEXT_2)
        ui.bar(112, y + 3, bar_w, 6, _toward(_air, i, n / _top[0][1], k), GREEN, RAISED)
        ui.caps(str(n), 312, y, TEXT, ui.RIGHT)
    if not _top:
        ui.text("Running..." if waiting else "No airlines yet", 160, BOT_Y + 28, TEXT_4, F_BODY, 0, ui.CENTER_X)


# ---- feed page ----------------------------------------------------------------

def _wrap2(text, w):
    """text on at most two lines of w pixels, the second ending in an ellipsis if cut."""
    global _note_key, _note_lines
    if _note_key == (text, w):
        return _note_lines
    line, rest = "", text
    while rest:
        i = rest.find(" ")
        word, tail = (rest, "") if i < 0 else (rest[:i], rest[i + 1:])
        trial = word if not line else line + " " + word
        if ui.width(trial) > w:
            break
        line, rest = trial, tail
    lines = [ui.fit(text, w)] if not line else [line, ui.fit(rest, w)] if rest else [line]
    _note_key, _note_lines = (text, w), lines
    return lines


def _feed(app, m):
    f = app.feed
    metric = app.settings["metric"]
    _caption("select * from feed")
    age = f.age_s(app.now)
    late = AMBER if f.status == "STALE" else TEXT
    _tile(8, "LAST UPDATE", "---" if age is None else _span(max(0, age)), TEXT_4 if age is None else late)
    _tile(112, "UPTIME", _span(0 if app.start_ms is None else (app.now - app.start_ms) / 1000.0))
    _tile(216, "RANGE", str(int(round(m.range_nm * 1.852)) if metric else m.range_nm), unit="KM" if metric else "NM")

    note = _wrap2(f.note, 208)
    pitch, y0 = 20, PANEL_Y + 9
    ui.panel(8, PANEL_Y, 304, 112 + 14 * (len(note) - 1))        # as tall as its rows
    for i, label in enumerate(("SOURCE", "STATUS", "HOME", "POSITION", "NOTE")):
        ui.caps(label, 20, y0 + 2 + i * pitch, TEXT_3)
    ui.text(f.source or "---", 92, y0, TEXT if f.source else TEXT_4)
    fg, bg, dot = ui.STATUS_STYLE.get(f.status, ui.STATUS_STYLE["WAIT"])
    ui.pill(92, y0 + pitch, "SYNC" if f.busy else f.status, fg, bg, ui.LEFT, dot)
    ui.text(ui.fit(m.home_label or "---", 208), 92, y0 + 2 * pitch)
    ui.text(_coords(m.home[0], m.home[1], f.exact), 92, y0 + 3 * pitch, TEXT_2)
    for j, line in enumerate(note):
        ui.text(line, 92, y0 + 4 * pitch + j * 14, TEXT_2)
