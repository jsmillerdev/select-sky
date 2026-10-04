"""WALL: one aircraft as a name plate, the way a flight wall shows it."""

from badgeware import *

import skyui as ui
from skytheme import *

NAME = "WALL"


def update(app):
    m = app.model
    if badge.pressed(BUTTON_B):
        m.auto = not m.auto
        app.toast("Cycling nearest" if m.auto else "Locked on " + (m.selected().label if m.selected() else "nothing"))
    if badge.pressed(BUTTON_UP):
        app.step(-1)
    if badge.pressed(BUTTON_DOWN):
        app.step(1)

    a = m.selected()
    ui.topbar(app, NAME)
    ui.hintbar(app, "LOCK" if m.auto else "CYCLE", "FLIGHT")
    if a is None:
        ui.no_rows(app)
        return

    metric = app.settings["metric"]
    # New aircraft slide in from the right and settle.
    dx, screen.alpha = ui.slide_in(app.now - app.sel_ms)

    ui.caps("select * from sky order by dist", 8, 28, TEXT_4)
    row, col = ui.row_tag(m, a)
    ui.caps(row, 312, 28, col, ui.RIGHT)

    _tile(a, 8 + dx, 44)
    x = 72 + dx
    ui.sans(ui.sans_fit(a.label, 29, 150), x, 38, 29, TEXT)
    ui.text(ui.fit("%s · %s" % (a.operator, a.kind), 150), x, 76, TEXT_2)
    px = x + ui.phase_pill(x, 92, a) + 4
    if a.military:
        px += ui.pill(px, 92, "MIL", VIOLET, VIOLET_TINT) + 4
    if a.emergency:
        px += ui.pill(px, 92, "SQUAWK " + a.sqk, RED, RED_TINT) + 4
    elif a.reg and a.reg != a.label:
        ui.caps(a.reg, px + 2, 93, TEXT_4)

    d, unit = ui.dist_text(a.dist, metric)
    w = ui.caps(unit, 312, 51, TEXT_3, ui.RIGHT)
    ui.sans(d, 310 - w, 42, 17, TEXT, ui.RIGHT)
    ui.caps(ui.bearing_text(a.brg), 312, 66, TEXT_3, ui.RIGHT)

    _route(app, a, 116)
    _metrics(a, metric, 160)
    screen.alpha = 255
    ui.cycle_bar(app)


def _tile(a, x, y):
    """Airline tile: brand colour and IATA code, or a glyph for everyone else."""
    brand = a.airline[3] if a.airline else None
    ui.panel(x, y, 56, 56, color.rgb(*brand) if brand else RAISED, 8)
    code = a.airline[2] if a.airline else ""
    if code:
        ui.sans(code, x + 28, y + 14, 21, TEXT, ui.CENTER_X)
    else:
        ui.plane(x + 28, y + 28, 45, VIOLET if a.military else TEXT_2, 2.2, a.glyph)


def _route(app, a, y):
    r = app.model.route(a)
    if not r:
        ui.box(8, y + 12, 304, 1, LINE)
        note = "Route lookup" if a.airline and a.cs not in app.model.routes else "No route on file"
        w = ui.width(note.upper(), F_CAPS) + 16
        ui.box(160 - w / 2, y + 6, w, 13, BG)
        ui.caps(note, 160, y + 7, TEXT_4, ui.CENTER_X)
        return
    o, d = r["o"], r["d"]
    wo = ui.sans(o[0], 8, y - 4, 20, TEXT)
    wd = ui.sans(d[0], 312, y - 4, 20, TEXT, ui.RIGHT)
    ui.caps(ui.fit(o[1].upper(), 120, F_CAPS), 8, y + 22, TEXT_3)
    ui.caps(ui.fit(d[1].upper(), 120, F_CAPS), 312, y + 22, TEXT_3, ui.RIGHT)
    x0, x1 = 8 + wo + 12, 312 - wd - 12
    xp = x0 + 10 + (x1 - x0 - 20) * (app.model.progress(a) or 0)
    ui.box(x0, y + 9, x1 - x0, 2, LINE_HI)
    ui.box(x0, y + 9, xp - x0, 2, GREEN)
    ui.disc(x0, y + 10, 2.5, GREEN)
    ui.disc(x1, y + 10, 2.5, LINE_HI)
    ui.plane(xp, y + 10, 90, GREEN_HI, 1.25)


def _metrics(a, metric, y):
    alt, alt_u = ui.alt_text(a.alt, metric)
    spd, spd_u = ui.speed_text(a.gs, metric)
    vs, vs_u = ui.rate_text(a.vr, metric)
    cells = (("ALT", alt, alt_u, alt_color(a.alt)),
             ("SPD", spd, spd_u, None),
             ("TRK", "%03d°" % a.trk if a.trk >= 0 else "---", "", None),
             ("V/S", vs, vs_u, GREEN if a.vr >= 100 else AMBER if a.vr <= -100 else None))
    for i, (label, value, unit, accent) in enumerate(cells):
        x = 8 + i * 77
        ui.panel(x, y, 73, 52)
        if accent:
            ui.box(x, y + 8, 2, 36, accent)
        ui.caps(label, x + 9, y + 7)
        if unit:
            ui.caps(unit, x + 65, y + 7, TEXT_3, ui.RIGHT)
        pt = 17 if ui.sans_width(value, 17) <= 58 else 14
        ui.sans(value, x + 9, y + 23, pt, TEXT)
        if i == 2 and a.trk >= 0:
            ui.plane(x + 58, y + 34, a.trk, TEXT_3, 0.9, 1)
        if i == 3 and abs(a.vr) >= 100:
            ui.tri(x + 62, y + 34, 4, accent, a.vr > 0)
