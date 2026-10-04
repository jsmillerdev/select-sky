"""Things drawn over or instead of a view: startup, alerts, toasts, transitions."""

from badgeware import *

import skyui as ui
from skytheme import *

QUERY = "select * from sky;"
TYPE_MS = 70          # per character
WIPE_MS = 170
WIPE_STEPS = 8
TOAST_MS = 1700


def splash(app, t):
    """Startup: the mark, the query typed out, and what the feed is doing."""
    ui.box(0, 0, ui.W, ui.H, BG)
    ui.bolt(160 - 23, 44, 48)
    ui.caps("supabase select badge", 160, 106, TEXT_3, ui.CENTER_X)
    shown = QUERY[:min(len(QUERY), int(t / TYPE_MS))]
    full = ui.sans_width(QUERY, 19)
    x = 160 - full / 2
    w = ui.sans(shown, x, 124, 19, TEXT) if shown else 0
    if (t // 300) % 2 == 0 or len(shown) < len(QUERY):
        ui.box(x + w + 2, 128, 8, 18, GREEN)
    ui.caps(app.feed.note, 160, 172, TEXT_3, ui.CENTER_X)
    ui.caps("open source · micropython · unofficial", 160, 220, TEXT_4, ui.CENTER_X)


def alert(app):
    """Emergency squawk takes over the screen until B acknowledges it."""
    a = app.model.alert
    if badge.pressed(BUTTON_B):
        app.model.acknowledge()
        if a in app.model.order:        # one beyond the range cannot be the selection
            app.model.select(a.hex)
        return
    ui.box(0, 0, ui.W, ui.H, RED_TINT)
    if (app.now // 400) % 2 == 0:
        for x, y, w, h in ((0, 0, ui.W, 4), (0, ui.H - 4, ui.W, 4), (0, 0, 4, ui.H), (ui.W - 4, 0, 4, ui.H)):
            ui.box(x, y, w, h, RED_STRONG)
    ui.pill(160, 26, "squawk alert", RED, BG_DEEP, ui.CENTER_X, RED)
    ui.sans(a.sqk, 160, 44, 52, TEXT, ui.CENTER_X)
    ui.sans(a.emergency, 160, 108, 17, RED, ui.CENTER_X)
    metric = app.settings["metric"]
    d, du = ui.dist_text(a.dist, metric)
    alt, au = ui.alt_text(a.alt, metric)
    ui.sans(ui.sans_fit(a.label, 22, 300), 160, 140, 22, TEXT, ui.CENTER_X)
    ui.text("%s %s %s  ·  %s %s" % (d, du, ui.bearing_text(a.brg), alt, au), 160, 172, TEXT_2, F_BODY, 0, ui.CENTER_X)
    x = 160 - 52
    x += ui.keycap(x, 204, "B", RED) + 5
    ui.caps("acknowledge", x, 205, TEXT_2)


def toast(app):
    """Confirmation of a button press, shown over the key legend so no content is hidden."""
    if app.toast_text and app.now - app.toast_ms < TOAST_MS:
        ui.box(0, ui.BOTTOM, ui.W, ui.H - ui.BOTTOM, GREEN_DIM)
        ui.caps(app.toast_text, 160, ui.BOTTOM + 4, TEXT, ui.CENTER_X)


def wipe(app):
    """Stepped wipe between views, in the direction of travel."""
    t = app.now - app.view_ms
    if t >= WIPE_MS:
        return
    hidden = ui.W - ui.W * (int(t * WIPE_STEPS / WIPE_MS) + 1) // WIPE_STEPS
    if hidden <= 0:
        return
    x = ui.W - hidden if app.view_dir > 0 else 0
    ui.box(x, ui.TOP, hidden, ui.BOTTOM - ui.TOP, BG)
    ui.box(x if app.view_dir > 0 else hidden - 2, ui.TOP, 2, ui.BOTTOM - ui.TOP, GREEN)
