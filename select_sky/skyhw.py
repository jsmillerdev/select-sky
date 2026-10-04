"""The badge's own hardware: rear lights, light sensor, backlight and battery."""

import math

from badgeware import *

CHASE = (0, 1, 3, 2)      # order the four rear lights are stepped in a sweep


class Hardware:
    def __init__(self):
        self.battery = 100
        self.charging = False
        self.usb = True
        self.ambient = None       # 0 dark .. 1 bright, None without a light sensor
        self._lo, self._hi, self._ema = 65535.0, 0.0, None
        self._lamps = [0.0] * 4
        self._next_slow = 0
        self._pulse_ms = None
        self._backlight = None
        self._full = False
        self._sleep = False

    def refresh(self):
        """Re-read the sensors and settings on the next frame."""
        self._next_slow = 0

    def full_light(self, on):
        """Full backlight while a phone scans the screen; False gives the wearer's level back."""
        self._full = on
        self.refresh()

    def sleep(self, on):
        """Lowest backlight and dark rear lights while the app is paused."""
        self._sleep = on
        self.refresh()

    def pulse(self, now):
        """Double blink for a new arrival."""
        self._pulse_ms = now

    def update(self, app):
        now = app.now
        if now >= self._next_slow:
            self._next_slow = now + 1000
            self._read_slow()
            self._set_backlight(app)
        if self._sleep:
            self.off()
            self._lamps = [0.0] * 4
        else:
            self._set_lamps(app, now)

    def off(self):
        try:
            badge.caselights(0)
        except Exception:
            pass

    def _read_slow(self):
        try:
            self.battery = badge.battery_level()
            self.usb = badge.usb_connected()
            self.charging = badge.is_charging()
        except Exception:
            pass
        try:
            raw = badge.light_level()
        except Exception:
            return
        # The sensor's range is uncalibrated, so learn it from what has been seen.
        self._ema = raw if self._ema is None else self._ema * 0.8 + raw * 0.2
        self._lo, self._hi = min(self._lo, self._ema), max(self._hi, self._ema)
        span = self._hi - self._lo
        self.ambient = 0.5 if span < 2000 else (self._ema - self._lo) / span

    def _set_backlight(self, app):
        level = app.settings["bright"] / 100.0
        if app.settings["auto_dim"] and self.ambient is not None:
            level *= 0.4 + 0.6 * self.ambient
        level = 0.15 if self._sleep else 1.0 if self._full else max(0.15, min(1.0, level))
        if level != self._backlight:
            self._backlight = level
            try:
                display.backlight(level)
            except Exception:
                pass

    def _set_lamps(self, app, now):
        m = app.model
        on = app.settings["leds"] and not (self.battery < 15 and not self.usb)
        pulse = self._pulse_ms is not None and now - self._pulse_ms < 520
        # Glow with proximity: the closer the nearest aircraft, the brighter.
        near = m.order[0] if m.order and not m.order[0].on_ground and m.order[0].dist < 8 else None
        if not (on and (m.alert or pulse or near or app.sweep is not None)) and max(self._lamps) <= 0.01:
            return                  # nothing can light a lamp and none is lit
        v = [0.0] * 4
        if on:
            if m.alert:
                lit = (now // 180) % 2
                v = [1.0 * lit, 1.0 - lit, 1.0 - lit, 1.0 * lit]
            elif pulse:
                v = [0.7 if (now - self._pulse_ms) % 260 < 130 else 0.0] * 4
            else:
                glow = 0.0
                if near:
                    closeness = 1 - near.dist / 8
                    glow = closeness * closeness * (0.25 + 0.15 * math.sin(now / 500.0))
                v = [glow] * 4
                if app.sweep is not None:
                    v[CHASE[int(app.sweep / 90) % 4]] += 0.22
        v = [0.0 if a < 0 else 1.0 if a > 1 else a for a in v]
        if max(abs(a - b) for a, b in zip(v, self._lamps)) > 0.01:
            self._lamps = v
            try:
                badge.caselights(*v)
            except Exception:
                pass
