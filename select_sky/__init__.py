"""Select Sky: a flight wall for the SELECT badge.  select * from sky;

Shows the aircraft around you, or one callsign anywhere, across six views.
A and C step through the views; B and the arrows act on the one in front.
"""

from badgeware import *

badge.mode(HIRES | VSYNC)       # first: this replaces the global screen
screen.antialias = image.X2

import config
import skyoverlay
import skytheme
import view_board
import view_radar
import view_setup
import view_stats
import view_track
import view_wall
from skyfeed import Feed
from skyhw import Hardware
from skymodel import Model

badge.default_clear = skytheme.BG

VIEWS = (view_wall, view_radar, view_board, view_track, view_stats, view_setup)
SETTINGS = {"range": 25, "metric": False, "bright": 85, "auto_dim": False, "leds": True,
            "ground": False, "cycle": 7, "track": "", "track_cfg": "", "home": ""}
CYCLE_TOP = 5                 # auto mode steps through this many of the nearest
HOME_SETTLE_MS = 700          # a Home pick applies this long after the last one, so a run of presses is one move
SPLASH_MIN_MS = 2300
SPLASH_MAX_MS = 6000


class App:
    def __init__(self):
        self.settings = dict(SETTINGS)
        State.load("select_sky", self.settings)
        # config.TRACK replaces the saved callsign only when you edit it; a Setup choice wins otherwise.
        if self.settings["track_cfg"] != config.TRACK:
            self.settings["track"] = self.settings["track_cfg"] = config.TRACK
        self.model = Model()
        self.model.range_nm = self.settings["range"]
        self.model.set_track(self.settings["track"])
        self.feed = Feed(self.model, self.settings)
        self.hw = Hardware()
        names = [v.NAME for v in VIEWS]
        self.view = names.index(config.START_VIEW) if config.START_VIEW in names else 0
        self.view_ms = -1000
        self.view_dir = 1
        self.now = 0
        self._raw, self._wrap = 0, 0   # badge.ticks wraps at 2**32 ms; self.now never does
        self.start_ms = None
        self.splash = config.SPLASH
        self.capture = False          # a view is using A and C itself, such as an editor
        self.sweep = None             # radar sweep angle in degrees while the radar is up
        self.sel_ms = 0               # when the selection last changed; the auto-cycle counts from here
        self.since_rows = 100000      # ms since rows last arrived, for the status ping
        self.toast_text = ""
        self.toast_ms = 0
        self.fresh = 0                # aircraft that were new in the latest update
        self.fresh_ms = -100000
        self._quiet = False
        self._sel = None
        self._rows_ms = None
        self.home_pick = None         # airport picked in Setup but not yet applied; "" is AUTO
        self._home_ms = 0
        self._repeat_ms = 0
        self._frame_ms = 16.0

    # ---- helpers the views call ---------------------------------------

    @property
    def battery(self):
        return self.hw.battery

    @property
    def charging(self):
        return self.hw.charging

    def view_name(self, delta):
        return VIEWS[(self.view + delta) % len(VIEWS)].NAME

    def toast(self, message):
        self.toast_text, self.toast_ms = message, self.now

    def save(self):
        """Persist settings. Call on a user change, never per frame."""
        State.save("select_sky", self.settings)

    def step(self, delta):
        self.model.step(delta)

    def repeat(self, button):
        """True when a button is pressed, and again at a steady rate while it stays down."""
        if badge.pressed(button):
            self._repeat_ms = self.now + 380
            return True
        if badge.held(button) and self.now >= self._repeat_ms:
            self._repeat_ms = self.now + 110
            return True
        return False

    def set_range(self, nm):
        self.settings["range"] = nm
        self._quiet = True
        self.model.set_range(nm)
        self.feed.refresh()
        self.save()

    def set_track(self, callsign):
        self.settings["track"] = callsign
        self.model.set_track(callsign)
        self.feed.refresh()
        self.save()

    def set_home(self, code):
        """Pick a listed airport for home, or '' for the automatic position. It applies once the picks stop."""
        self.home_pick, self._home_ms = code, self.now

    def nav(self):
        """UP and DOWN step the selection, and keep stepping while held."""
        if self.repeat(BUTTON_UP):
            self.step(-1)
        if self.repeat(BUTTON_DOWN):
            self.step(1)

    def cycle_fraction(self):
        return min(1.0, (self.now - self.sel_ms) / (self.settings["cycle"] * 1000.0))

    # ---- frame ---------------------------------------------------------

    def frame(self):
        raw = badge.ticks
        if raw < self._raw:            # the 32-bit ms counter wrapped (every 49.7 days)
            self._wrap += 1 << 32
        self._raw = raw
        now = self.now = raw + self._wrap
        if self.start_ms is None:
            self.start_ms = self.sel_ms = now
        # If frames run slow, trade antialiasing for speed and keep it that way.
        self._frame_ms = self._frame_ms * 0.95 + min(badge.ticks_delta, 250) * 0.05
        if self._frame_ms > 90 and screen.antialias != image.OFF:
            screen.antialias = image.OFF
        m = self.model
        self.hw.update(self)
        self.feed.tick(now)
        if self.home_pick is not None and now - self._home_ms >= HOME_SETTLE_MS:
            code, self.home_pick = self.home_pick, None
            if code != (self.settings.get("home") or ""):
                self.settings["home"] = code
                self.feed.relocate()
                self.save()
        m.advance(now)

        if self.feed.rows_ms != self._rows_ms:
            # Arrivals blink the rear lights, except the batch a range change pulls in.
            if self._rows_ms is not None and m.fresh and not self._quiet:
                self.hw.pulse(now)
                self.fresh, self.fresh_ms = m.fresh, now
            self._quiet = False
            self._rows_ms = self.feed.rows_ms
        self.since_rows = now - (self._rows_ms or -100000)

        if self.splash:
            t = now - self.start_ms
            if (t > SPLASH_MIN_MS and self._rows_ms is not None) or t > SPLASH_MAX_MS or badge.pressed():
                self.splash = False         # the press that ended it is not also a view key
                self.view_ms = now
            else:
                skyoverlay.splash(self, t)
            return
        if m.alert:
            skyoverlay.alert(self)
            return

        if not self.capture:
            turn = badge.pressed(BUTTON_C) - badge.pressed(BUTTON_A)
            if turn:
                self.view = (self.view + turn) % len(VIEWS)
                self.view_ms, self.view_dir = now, turn
                self.sweep = None
        if m.auto and len(m.order) > 1 and now - self.sel_ms >= self.settings["cycle"] * 1000:
            top = m.order[:CYCLE_TOP]
            a = m.selected()
            m.sel = top[(top.index(a) + 1) % len(top) if a in top else 0].hex
        if m.sel != self._sel:
            self._sel, self.sel_ms = m.sel, now

        VIEWS[self.view].update(self)
        skyoverlay.wipe(self)
        skyoverlay.toast(self)


app = App()


def update():
    app.frame()


def on_exit():
    app.hw.off()


run(update)
