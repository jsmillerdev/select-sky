"""SETUP: every setting as a list row, plus the callsign editor and the credits page.

UP and DOWN pick a row, B changes it. Changes apply at once and are saved.
Track callsign opens a modal editor that borrows A and C; About opens the credits.
"""

from badgeware import *

import config
import skydata
import skyui as ui
from skymodel import RANGES
from skytheme import *

NAME = "SETUP"

ROW_H = 24
LIST_Y = 42                     # top of the first row
VISIBLE = 6                     # rows on screen at once
STRIP_Y = 190                   # the description strip runs from here to the key hints
LABEL_X, VALUE_R = 20, 304      # label starts here; values end here
SWITCH_W, SWITCH_H = 26, 14
FLIP_MS = 140                   # a switch knob slides this long
EASE_MS = 45.0                  # highlight and scroll close half their gap in this long
SCROLL_MARGIN = 1               # rows kept between the pick and the edge, so the next row peeks in

BRIGHTS = (20, 40, 60, 85, 100)
CYCLES = (5, 7, 10, 15)
HOMES = [""] + sorted(skydata.AIRPORTS)         # "" is AUTO

ROWS = (("range", "Range"), ("units", "Units"), ("home", "Home"), ("track", "Track callsign"),
        ("bright", "Brightness"), ("auto_dim", "Auto dim"), ("leds", "Rear lights"),
        ("ground", "Ground traffic"), ("cycle", "Cycle"), ("alert", "Test alert"),
        ("source", "Data source"), ("about", "About"))
SWITCHES = ("auto_dim", "leds", "ground", "alert")
OPENERS = ("track", "about")                    # rows that open a page instead of changing in place
HELP = {
    "range": "How far out an aircraft counts as nearby",
    "units": "Imperial: ft kt nm. Metric: m km/h km",
    "home": "Auto finds you by IP, or pick an airport",
    "track": "Follow one callsign anywhere. B edits",
    "bright": "Backlight level, applied at once",
    "auto_dim": "Dim the backlight when the room is dark",
    "leds": "Rear lights glow as traffic gets close",
    "ground": "Show aircraft that are on the ground",
    "cycle": "Seconds per aircraft when cycling",
    "alert": "Fake a 7700 squawk on the next update",
    "about": "Credits, license and data sources",
}

CHARS = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
SLOTS = 8
SLOT_W, SLOT_Y, SLOT_H = 34, 60, 56
# Eight slots spread over the 8 px margins; the gaps alternate 5 and 4 px.
SLOT_XS = tuple(8 + (i * (304 - SLOT_W) + 3) // 7 for i in range(SLOTS))


class _State:
    """Everything the view remembers between frames."""

    def __init__(self):
        self.sel = 0
        self.scroll = 0.0       # first visible row, eased
        self.hl = 0.0           # highlighted row, eased
        self.last = -100000     # app.now of the previous frame
        self.about = False
        self.edit = None        # list of SLOTS characters while the callsign editor is open
        self.pos = 0
        self.flip = {}          # switch row -> app.now of its last change


st = _State()


def _next(options, current):
    """The option after current, wrapping; the first when current is not listed."""
    if current in options:
        return options[(options.index(current) + 1) % len(options)]
    return options[0]


def _ease(cur, target, dt):
    d = target - cur
    if abs(d) < 0.01:
        return target
    return cur + d * ui.glide(dt, EASE_MS)


def _demo(app):
    return app.feed.status == "DEMO"


def _home_code(app):
    """The airport code Home shows: the pick still waiting to be applied, else the saved one. "" is AUTO."""
    return (app.settings.get("home") or "") if app.home_pick is None else app.home_pick


def _flag(app, key):
    """On or off for a switch row."""
    if key == "alert":
        return _demo(app) and app.feed.demo_alert
    return bool(app.settings[key])


def _locked(app, key):
    """Rows B cannot change: the feed's name, a HOME pinned in config.py, and the demo-only alert."""
    return key == "source" or (key == "home" and bool(config.HOME)) or (key == "alert" and not _demo(app))


def _helptext(app, key):
    if key == "source":
        return app.feed.note
    if key == "alert":
        if not _demo(app):
            return "Only works with demo traffic, not a live feed"
        if app.feed.demo_alert:
            return "Still squawking 7700. B stops it" if app.model.acked else "Squawk starts on the next update. B cancels"
    if key == "home":
        if config.HOME:
            return "Pinned by HOME in config.py"
        if app.home_pick is not None:
            return "Moves home when you stop pressing B"
    return HELP[key]


def _home_text(app):
    if config.HOME:
        return "Fixed · " + (config.HOME[2] if len(config.HOME) > 2 else "HOME")
    code = _home_code(app)
    if code in skydata.AIRPORTS:
        return "%s · %s" % (code, skydata.AIRPORTS[code][0])
    label = app.model.home_label if app.home_pick is None else ""     # AUTO is not resolved until it is applied
    return "Auto · " + label if label else "Auto"


def _value_text(app, key):
    """The right-hand text of a row."""
    s = app.settings
    if key == "range":
        if s["metric"]:
            d, u = ui.dist_text(s["range"], True)
            return "%d nm · %s %s" % (s["range"], d, u)
        return "%d nm" % s["range"]
    if key == "units":
        return "m km/h km" if s["metric"] else "ft kt nm"
    if key == "home":
        return _home_text(app)
    if key == "track":
        return s["track"] or "None"
    if key == "bright":
        return "%d%%" % s["bright"]
    if key == "auto_dim":
        if not s["auto_dim"]:
            return "Off"
        amb = app.hw.ambient
        return "On" if amb is None else "Light %d%%" % int(amb * 100)
    if key == "leds":
        return "On" if s["leds"] else "Off"
    if key == "ground":
        return "Shown" if s["ground"] else "Hidden"
    if key == "cycle":
        return "%d s" % s["cycle"]
    if key == "alert":
        if not _demo(app):
            return "Demo only"
        if not app.feed.demo_alert:
            return "Off"
        return "Squawking" if app.model.acked else "Armed"
    if key == "source":
        src = app.feed.source
        return "Demo" if src == "demo" else src or "Waiting"
    return ""


def _b_label(app, key):
    if key == "about":
        return "OPEN"
    if key == "track":
        return "EDIT"
    if _locked(app, key):
        return None
    return "TOGGLE" if key in SWITCHES else "CYCLE"


# ---- changing settings ----------------------------------------------------

def _change(app, key):
    s = app.settings
    if _locked(app, key):
        return
    if key == "range":
        app.set_range(_next(RANGES, s["range"]))
    elif key == "home":
        app.set_home(_next(HOMES, _home_code(app)))
    elif key == "track":
        cs = (s["track"] or "").upper()[:SLOTS]
        st.edit = list(cs + " " * (SLOTS - len(cs)))
        st.pos = 0
    elif key == "about":
        st.about = True
    elif key == "alert":
        feed = app.feed
        feed.demo_alert = not feed.demo_alert
        if feed.demo_alert:
            app.model.acked.clear()         # an alert already acknowledged would stay silent
        st.flip[key] = app.now
        feed.refresh()
    else:
        if key == "units":
            s["metric"] = not s["metric"]
        elif key == "bright":
            s["bright"] = _next(BRIGHTS, s["bright"])
        elif key == "cycle":
            s["cycle"] = _next(CYCLES, s["cycle"])
        else:
            s[key] = not s[key]             # auto_dim, leds and ground
            st.flip[key] = app.now
        app.save()
        if key == "ground":
            app.feed.refresh()
        elif key in ("bright", "auto_dim"):
            app.hw.refresh()                # it looks at the settings once a second; ask it to look now


def _finish_edit(app):
    cs = "".join(st.edit).replace(" ", "")
    st.edit = None
    old = app.settings["track"] or ""
    if cs != old:
        app.set_track(cs)
    app.toast("Tracking " + cs if cs else "Tracking stopped" if old else "No callsign set")


# ---- input ----------------------------------------------------------------

def _list_input(app):
    n = len(ROWS)
    for button, d in ((BUTTON_UP, -1), (BUTTON_DOWN, 1)):
        first = badge.pressed(button)
        if app.repeat(button):
            to = st.sel + d
            if 0 <= to < n:
                st.sel = to
            elif first:
                st.sel = to % n         # a fresh press wraps; a held key stops at the end
    key = ROWS[st.sel][0]
    # Home has dozens of airports, so holding B keeps stepping; on any other row a hold must not toggle twice.
    pressed = app.repeat(BUTTON_B) if key == "home" else badge.pressed(BUTTON_B)
    if pressed:
        _change(app, key)


def _edit_input(app):
    for button, d in ((BUTTON_UP, 1), (BUTTON_DOWN, -1)):
        if app.repeat(button):
            i = max(0, CHARS.find(st.edit[st.pos]))
            st.edit[st.pos] = CHARS[(i + d) % len(CHARS)]
    if badge.pressed(BUTTON_A):
        if st.pos == 0:
            st.edit = None
        else:
            st.pos -= 1
    elif badge.pressed(BUTTON_C):
        st.pos = min(SLOTS - 1, st.pos + 1)
    elif badge.pressed(BUTTON_B):
        _finish_edit(app)


# ---- drawing: the list ----------------------------------------------------

def _switch(app, key, x, y, picked):
    """On/off switch whose knob slides; the track blends between its two colours while it moves."""
    t = min(1.0, (app.now - st.flip.get(key, -FLIP_MS)) / FLIP_MS)
    pos = t if _flag(app, key) else 1 - t
    off = TEXT_4 if picked else LINE_HI
    track = GREEN if pos >= 1 else off if pos <= 0 else off.mix(GREEN, int(255 * pos))
    ui.panel(x, y + 5, SWITCH_W, SWITCH_H, track, 7)
    ui.disc(x + 7 + 12 * pos, y + 12, 5, TEXT)


def _row(app, i, y, picked):
    key, label = ROWS[i]
    ui.text(label, LABEL_X, y + 5, TEXT if picked else TEXT_2)
    room = VALUE_R - (LABEL_X + ui.width(label) + 14)        # space left for the value
    x = VALUE_R
    if key in OPENERS:
        ui.chevron(x - 4, y + 12, 4, TEXT_2 if picked else TEXT_4)
        x -= 14
        room -= 14
    elif key in SWITCHES and not _locked(app, key):
        _switch(app, key, x - SWITCH_W, y, picked)
        x -= SWITCH_W + 8
        room -= SWITCH_W + 8
    elif key == "bright":
        room -= 48                                           # the level bar sits left of the number
    text = _value_text(app, key)
    w = ui.width(text)
    if w > room:
        text = ui.fit(text, room)
        w = ui.width(text)
    ink = TEXT if picked else TEXT_3
    if key == "alert":
        ink = TEXT_3 if _locked(app, key) else AMBER if app.feed.demo_alert else ink
    if key == "bright":
        ui.bar(x - w - 48, y + 10, 40, 4, app.settings["bright"] / 100.0, GREEN, LINE_HI if picked else LINE)
    elif key == "track" and app.model.tracked:
        ui.disc(x - w - 9, y + 12, 2.5, GREEN)               # the flight is airborne and found
    ui.text(text, x, y + 5, ink, F_BODY, 0, ui.RIGHT)


def _draw_list(app, dt):
    n = len(ROWS)
    st.hl = _ease(st.hl, st.sel, dt)
    target = min(max(st.scroll, st.sel + SCROLL_MARGIN - VISIBLE + 1), st.sel - SCROLL_MARGIN)
    st.scroll = _ease(st.scroll, max(0, min(n - VISIBLE, target)), dt)

    hy = int(LIST_Y + (st.hl - st.scroll) * ROW_H + 0.5)
    ui.panel(8, hy + 1, 304, ROW_H - 2, SELECTED, 4)
    ui.box(8, hy + 5, 2, ROW_H - 10, GREEN)
    first = int(st.scroll)
    lit = int(st.hl + 0.5)              # the row under the highlight, so text and fill change together
    for i in range(first, min(n, first + VISIBLE + 2)):
        y = int(LIST_Y + (i - st.scroll) * ROW_H + 0.5)
        # Rows that scroll past the edges are painted over by the bands below.
        _row(app, i, y, i == lit)
    ui.box(0, ui.TOP, ui.W, LIST_Y - ui.TOP, BG)
    ui.box(0, LIST_Y + VISIBLE * ROW_H, ui.W, ui.BOTTOM - LIST_Y - VISIBLE * ROW_H, BG)
    ui.caps("select * from settings", 8, 28, TEXT_4)
    ui.caps("(%d rows)" % n, 312, 28, TEXT_3, ui.RIGHT)

    track = VISIBLE * ROW_H                                         # scroll thumb
    h = max(12, track * VISIBLE // n)
    ui.box(316, LIST_Y + (track - h) * st.scroll / (n - VISIBLE), 2, h, LINE_HI)
    _strip(_helptext(app, ROWS[st.sel][0]))


def _strip(message):
    """Description strip: an SQL comment in caps."""
    ui.box(0, STRIP_Y, ui.W, ui.BOTTOM - STRIP_Y, PANEL)
    w = ui.caps("--", 8, STRIP_Y + 12, TEXT_4) + 6
    ui.caps(ui.fit(message.upper(), 304 - w, F_CAPS), 8 + w, STRIP_Y + 12, TEXT_2)


# ---- drawing: the callsign editor ----------------------------------------

def _updown_cap(x, y):
    ui.panel(x, y, 13, 13, RAISED, 3)
    ui.tri(x + 6.5, y + 4, 2.5, TEXT_2, True)
    ui.tri(x + 6.5, y + 9.5, 2.5, TEXT_2, False)


def _legend(x, y, cap, label):
    if cap is None:
        _updown_cap(x, y)
    else:
        ui.keycap(x, y, cap, GREEN if cap == "B" else TEXT_2)
    ui.caps(label, x + 18, y + 1, TEXT_2)


def _draw_edit():
    ui.caps("select * from sky where callsign =", 8, 28, TEXT_4)
    ui.caps("slot %d of %d" % (st.pos + 1, SLOTS), 312, 28, TEXT_3, ui.RIGHT)
    for i in range(SLOTS):
        x = SLOT_XS[i]
        ch = st.edit[i]
        active = i == st.pos
        ui.panel(x, SLOT_Y, SLOT_W, SLOT_H, GREEN if active else RAISED, 6)
        cx = x + SLOT_W / 2
        if ch != " ":
            ui.sans(ch, cx, SLOT_Y + 11, 30, BG_DEEP if active else TEXT, ui.CENTER_X)
        else:
            ui.box(cx - 5, SLOT_Y + SLOT_H - 14, 10, 2, GREEN_DIM if active else TEXT_4)
        if active:
            ui.tri(cx, SLOT_Y - 9, 5, GREEN, True)
            ui.tri(cx, SLOT_Y + SLOT_H + 9, 5, GREEN, False)
    _legend(8, 148, None, "Change character")
    _legend(168, 148, "B", "Save")
    _legend(8, 170, "A", "Left, cancel at start")
    _legend(168, 170, "C", "Right")
    cs = "".join(st.edit).replace(" ", "")
    _strip("Tracking " + cs + " anywhere" if cs else "Blank saves as none and stops tracking")


# ---- drawing: credits -----------------------------------------------------

CREDITS = (("License", "Open source (MIT)", TEXT),
           ("Status", "Unofficial. Not for navigation", AMBER),
           ("Aircraft", "adsb.fi and adsb.lol (ODbL)", TEXT),
           ("Routes", "VRS standing data project", TEXT),
           ("Built for", "The Supabase SELECT badge", TEXT))


def _draw_about():
    ui.caps("select * from about", 8, 28, TEXT_4)
    ui.caps("(1 row)", 312, 28, TEXT_3, ui.RIGHT)
    ui.bolt(8, 44, 28)
    ui.sans("Select Sky", 46, 38, 22, TEXT)
    ui.caps("Live flight wall", 46, 66, TEXT_3)
    for i, (label, value, col) in enumerate(CREDITS):
        y = 88 + i * 20
        ui.caps(label, 8, y + 3, TEXT_3)
        ui.text(ui.fit(value, 312 - 88), 88, y, col)
    _strip("B or any arrow goes back")


# ---- frame ----------------------------------------------------------------

def update(app):
    dt = min(100, max(1, app.now - st.last))
    if app.now - st.last > 300:
        st.about = False                # the view was left and is back
    st.last = app.now

    if st.about:
        if badge.pressed(BUTTON_B) or badge.pressed(BUTTON_UP) or badge.pressed(BUTTON_DOWN):
            st.about = False
    elif st.edit is not None:
        _edit_input(app)
    else:
        _list_input(app)
    app.capture = st.edit is not None   # A and C belong to the editor only while it is open

    # Chrome goes last: rows scrolling past the edges would otherwise draw over it.
    if st.about:
        _draw_about()
        hints = ("BACK", None)
    elif st.edit is not None:
        _draw_edit()
        hints = ("SAVE", "CHAR", "cancel" if st.pos == 0 else "left", "right")     # A and C move the slot
    else:
        _draw_list(app, dt)
        hints = (_b_label(app, ROWS[st.sel][0]), "ROW")
    ui.topbar(app, NAME)
    ui.hintbar(app, *hints)
