"""Where the rows come from: Supabase Edge Function, a direct feed, or the demo.

The browser allows one short blocking GET per frame and only to hosts that send
CORS headers, so every request here is a queued job. A job is armed on one
frame, which lets the screen show SYNC, and runs on the next.
"""

import time

import config
import skydata
import skydemo
import skygeo
from skymodel import ALT, CAT, CS, DIR, DST, FLAGS, GS, HEX, LAT, LON, REG, SEEN, SQK, TRK, TYPE, VR

try:
    import requests
except ImportError:
    requests = None
try:
    import secrets
except ImportError:
    secrets = None
try:
    import tls                # firmware only (requests needs it for https); the browser has none
    ON_BADGE = True
except ImportError:
    ON_BADGE = False

NET_ERRORS = (OSError, ValueError, NotImplementedError, MemoryError, KeyError, TypeError,
              AttributeError, IndexError, OverflowError)
GEO_URL = "https://ipwho.is/?fields=success,latitude,longitude,city,timezone"
ROUTE_URL = "https://vrs-standing-data.adsb.lol/routes/%s/%s.json"
# name, nearby URL (lat, lon, nm), callsign URL
DIRECT = (
    ("adsb.fi", "https://opendata.adsb.fi/api/v3/lat/%.4f/lon/%.4f/dist/%d", "https://opendata.adsb.fi/api/v2/callsign/%s"),
    ("adsb.lol", "https://api.adsb.lol/v2/point/%.4f/%.4f/%d", "https://api.adsb.lol/v2/callsign/%s"),
)
TIMEOUT_S = 8 if ON_BADGE else 3     # the browser allows 3 seconds at most
RETRY_MS = 3000            # second try after a failed update
RETRY_LIVE_MS = 60000      # how often the demo checks whether a live source is back
JOIN_MS = 30000            # a Wi-Fi join may take this long before it counts as a failed update
JOIN_RETRY_MS = 30000      # a join not finished by then is started again
GEO_RETRY_MS = 15000       # the IP lookup can try again after this long
GEO_TRIES = 4              # requests to ipwho.is per Auto lookup
TRACK_EVERY_MS = 30000
FEED_GAP_MS = 2500         # least time between a poll and a callsign lookup
ROUTE_RETRY_MS = 30000     # wait before asking again after a route lookup failed in transit
LOCATE_EVERY_MS = 2500     # between asks for the position a phone is sending
LOCATE_LIFE_MS = 300000    # a locate code is asked for this long, then it expires
VALID_CLOCK = 1735689600      # 2025-01-01: an RTC before this was never set


class HttpError(ValueError):
    """An answer other than 200. status is the HTTP code."""

    def __init__(self, status):
        super().__init__("HTTP %d" % status)
        self.status = status


def get_json(url):
    """GET and decode JSON. Raises one of NET_ERRORS on any failure."""
    # The browser owns User-Agent and rejects the header; adsb.lol needs one from a badge.
    r = requests.get(url, headers={"User-Agent": config.CONTACT} if ON_BADGE else None, timeout=TIMEOUT_S)
    try:
        if r.status_code != 200:
            raise HttpError(r.status_code)
        return r.json()
    finally:
        r.close()


def _row(r):
    """One feed row as a clean 16-tuple, or None when it cannot be trusted."""
    try:
        lat, lon = float(r[LAT]), float(r[LON])
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):      # also rejects inf
            return None
        seen = float(r[SEEN] or 0)
        if not 0 <= seen < 86400:                               # inf would overflow int(seen * 1000)
            seen = 0.0
        return (str(r[HEX]), str(r[CS] or ""), str(r[TYPE] or ""), int(r[ALT]), int(r[GS]), int(r[TRK]), int(r[VR]),
                lat, lon, str(r[SQK] or ""), int(r[FLAGS] or 0), r[DST], r[DIR], str(r[CAT] or ""), str(r[REG] or ""), seen)
    except (TypeError, ValueError, IndexError, KeyError, OverflowError):
        return None


def normalise(payload):
    """(rows, unix seconds) from the Edge Function's compact form or a raw readsb feed.

    Raises ValueError for an answer with no aircraft list. Rows that cannot be trusted are left out.
    """
    if not isinstance(payload, dict) or not ("a" in payload or "ac" in payload or "aircraft" in payload):
        raise ValueError("no aircraft list")
    now = payload.get("now")
    if not isinstance(now, (int, float)):
        now = 0
    elif now > 100000000000:
        now //= 1000                # milliseconds, in whole seconds: a float32 holds Unix time to 128 s only
    if not VALID_CLOCK <= now < 4000000000:                     # also rejects NaN; gmtime takes a uint32
        now = 0
    now = int(now)
    if "a" in payload:
        return [r for r in map(_row, payload["a"] or ()) if r], now
    rows = []
    for x in payload.get("ac") or payload.get("aircraft") or ():
        if not isinstance(x, dict) or x.get("lat") is None or x.get("lon") is None:
            continue
        alt = x.get("alt_baro")
        trk = x.get("track")
        if trk is None:
            trk = x.get("true_heading")
        gs = x.get("gs")
        # Pressure altitude goes below zero on a high-pressure day: -1 means unknown, 0 means ground.
        rows.append((x.get("hex", ""), (x.get("flight") or "").strip(), x.get("t") or "",
                     0 if alt == "ground" else max(1, int(alt)) if isinstance(alt, (int, float)) else -1,
                     -1 if gs is None else int(gs), -1 if trk is None else int(trk),
                     int(x.get("baro_rate") or x.get("geom_rate") or 0), x["lat"], x["lon"],
                     x.get("squawk") or "", x.get("dbFlags") or 0, x.get("dst") or 0, x.get("dir") or 0,
                     x.get("category") or "", x.get("r") or "", x.get("seen_pos") or 0))
    return [r for r in map(_row, rows) if r], now


class Feed:
    def __init__(self, model, settings):
        self.model = model
        self.settings = settings
        self.status = "WAIT"        # WAIT, LIVE, DEMO or STALE
        self.source = ""            # short name of what is answering
        self.note = "Starting"      # one line for the Setup view
        self.tz_s = None            # home's offset from UTC in seconds, when known
        self.exact = False          # home is the position saved in Setup
        self.demo_alert = False
        self.rows_ms = None         # when rows last arrived
        self._anchor = None         # (unix seconds, ticks) from the newest payload
        self._job = None
        self._next_poll = 0
        self._next_track = 0
        self._next_route = 0
        self._route_fails = 0
        self._retry_live = 0
        self._fails = 0
        self._real = False          # a live source has answered this session
        self._join_ms = None        # when the current spell without Wi-Fi began
        self._join_at = None        # when Wi-Fi was last asked to join
        self._located = False
        self._geo_at = None         # when to try the IP lookup again, None when it is settled
        self._geo_left = 0
        self._chain = []            # live sources still worth trying, best first
        self.code = ""              # the locate code a phone sends a position under; "" when there is none
        self.code_end = 0           # when it expires
        self._pos = None            # (lat, lon, accuracy) a phone sent, until take_pos() hands it over
        self._next_here = 0
        self._here_url = ""
        if config.PROXY_URL:
            base = config.PROXY_URL.replace("%", "%%")      # these strings are used as % templates
            sep = "&" if "?" in base else "?"
            self._chain.append(("edge fn", base + sep + "lat=%.4f&lon=%.4f&r=%d", base + sep + "cs=%s"))
            self._here_url = base + sep + "here=%s"
        if ON_BADGE:
            self._chain.extend(DIRECT)
        self._live = 0 if self._chain and requests else None    # index into _chain, None for demo
        if self._live is None:
            self.note = "Demo traffic. Set PROXY_URL in config.py"

    # ---- public --------------------------------------------------------

    @property
    def busy(self):
        """A blocking request runs on the next frame."""
        return self._job is not None

    def clock(self):
        """Unix time now in whole seconds, or None when nothing trustworthy has set it."""
        if self._anchor:
            return self._anchor[0] + time.ticks_diff(time.ticks_ms(), self._anchor[1]) // 1000
        if ON_BADGE and time.time() > VALID_CLOCK:
            return time.time()
        return None

    def age_s(self, now):
        return None if self.rows_ms is None else (now - self.rows_ms) / 1000.0

    def refresh(self):
        """Ask for rows on the next frame, such as after the range changed."""
        self._next_poll = 0

    def relocate(self):
        """Look the home position up again, such as after Setup changed it."""
        self._located = False
        self._next_poll = 0

    def locate(self, code, now):
        """Ask the relay for the position a phone sends under code, until it arrives or LOCATE_LIFE_MS pass."""
        self.code, self.code_end, self._pos = code, now + LOCATE_LIFE_MS, None
        self._next_here = now + LOCATE_EVERY_MS

    def locate_stop(self):
        self.code, self._pos = "", None

    def locate_left(self, now):
        """Milliseconds the code still has, 0 once it expired or was answered."""
        return max(0, self.code_end - now) if self.code else 0

    def take_pos(self):
        """(lat, lon, accuracy in metres or None) from the phone, once; None until then."""
        pos, self._pos = self._pos, None
        return pos

    def fetch_radius(self):
        # Half as far again as the range, so the radar can show what is inbound.
        return min(100, int(self.settings["range"] * 1.5))

    def tick(self, now):
        """Run the armed job, or arm the next one. `now` is the app's clock: it never wraps."""
        if self._job:
            job, self._job = self._job, None
            job(now)
            return
        age = self.age_s(now)
        if self._live is not None and age is not None and age > 3 * config.POLL_S:
            self.status = "STALE"
        job = self._due(now)
        if job and self._live is None and self._located:
            job(now)                # the demo never blocks, so it needs no SYNC frame
        elif job:
            self._job = job

    # ---- scheduling ----------------------------------------------------

    def _due(self, now):
        if not self._located:
            return self._locate
        if self._live is None and self._chain and now >= self._retry_live:
            self._live = 0          # a probe: _live is set while the source is still "demo"
            self._next_poll = 0
        geo = self._live is not None and self._geo_at is not None and now >= self._geo_at
        if self._live is not None and (geo or now >= self._next_poll) and self._online(now) is False:
            # Wi-Fi is still joining. That is not a source failing, and it needs no SYNC frame.
            self._next_poll = now + 1000
            if geo:
                self._geo_at = now + 1000
            return None
        if geo:
            return self._locate_ip  # a live source is up, so a lookup is worth a blocking frame
        if now >= self._next_poll:
            return self._poll
        if self._live is None:
            self._demo_extras()
            return None
        if self.code and self._here_url and self._next_here <= now < self.code_end:
            return self._ask_phone
        m = self.model
        # The feeds and the relay allow one request a second, so keep clear of the polls.
        gap = min(FEED_GAP_MS, config.POLL_S * 333)
        clear = gap <= self._next_poll - now <= config.POLL_S * 1000 - gap
        if clear and m.track and (m.tracked is None or m.tracked.hex not in m.rows) and now >= self._next_track:
            return self._track
        if now >= self._next_route and self._route_target():
            return self._route
        return None

    def _route_target(self):
        """The followed flight first, then the selected one, if its route is still unknown."""
        m = self.model
        for a in (m.tracked, m.selected()):
            if a and a.airline and a.cs not in m.routes:
                return a
        return None

    def _online(self, now):
        """True when a request may go out, False while Wi-Fi is still joining, None when it is not coming up.

        It starts the join itself, not through wifi.connect(): that has one five-try
        budget per boot, and resets the badge when the budget runs out.
        """
        if not ON_BADGE:
            return True
        try:
            import network
            w = network.WLAN(network.STA_IF)
            if w.active() and w.isconnected():
                self._join_ms = self._join_at = None
                return True
            ssid = getattr(secrets, "WIFI_SSID", "")
            if not ssid:
                self.note = "Add Wi-Fi to secrets.py"
                return None
            self.note = "Joining Wi-Fi"
            if self._join_ms is None:
                self._join_ms = now
            if self._join_at is None or now - self._join_at >= JOIN_RETRY_MS:
                self._join_at = now
                w.active(True)
                w.connect(ssid, getattr(secrets, "WIFI_PASSWORD", ""))
        except Exception:
            return None
        return False if now - self._join_ms < JOIN_MS else None

    # ---- jobs ----------------------------------------------------------

    def _locate(self, now):
        self._located = True
        self.tz_s = None            # an IP lookup sets it; an airport or a pinned HOME has no offset
        self.exact = False
        self._geo_at = None         # a Setup pick cancels a pending lookup
        m, s = self.model, self.settings
        if config.HOME:
            m.set_home(config.HOME[0], config.HOME[1], config.HOME[2] if len(config.HOME) > 2 else "HOME")
            return
        code = s.get("home")
        if code in skydata.AIRPORTS:        # a code this build no longer lists falls back to AUTO
            city = skydata.AIRPORTS[code]
            m.set_home(city[1], city[2], code)
            return
        pos = skygeo.exact_pos(s) if code == skygeo.EXACT else None      # no usable position falls back to AUTO
        if pos:
            m.set_home(pos[0], pos[1], "HERE")      # the lookup below names the city and finds the time zone
            self.exact = True
        else:
            d = config.DEFAULT_HOME
            m.set_home(d[0], d[1], d[2])
        self._geo_left = GEO_TRIES
        self._locate_ip(now)

    def _locate_ip(self, now):
        """Ask the IP address where home is. A miss (Wi-Fi still joining, timeout, 429) tries again later.

        With an exact position the answer only names the city and sets the time zone: home stays where it is.
        """
        self._geo_at = None
        if not requests or not self._located:       # a Setup pick since this job was armed has the last word
            return
        online = self._online(now)
        if online:
            self._geo_left -= 1
            try:
                j = get_json(GEO_URL)
                if j.get("success"):
                    city = (j.get("city") or "HERE").upper()
                    if self.exact:
                        self.model.home_label = city
                    else:
                        self.model.set_home(float(j["latitude"]), float(j["longitude"]), city)
                        self._next_poll = 0     # the rows so far were for the default home
                    self._geo_left = 0
                    self.tz_s = int((j.get("timezone") or {}).get("offset"))
            except NET_ERRORS:
                pass
        if self._geo_left > 0:
            self._geo_at = now + (GEO_RETRY_MS if online else RETRY_MS)

    def _poll(self, now):
        self._next_poll = now + config.POLL_S * 1000
        m = self.model
        if self._live is None:
            if self.source != "demo":
                m.clear()
            self._rows(skydemo.rows(m.home, now / 1000.0, self.fetch_radius(), self.demo_alert), None, now, not self._real)
            self.status, self.source = "DEMO", "demo"
            return
        if not self._online(now):
            self._failed(now, self.note)
            return
        name, url, _ = self._chain[self._live]
        began = time.ticks_ms()
        try:
            rows, unix = normalise(get_json(url % (m.home[0], m.home[1], self.fetch_radius())))
        except NET_ERRORS as e:
            # badge.ticks was latched before the request blocked: count the back-off from its end.
            self._failed(now + time.ticks_diff(time.ticks_ms(), began),
                         "%s: %s" % (name, "no answer" if isinstance(e, OSError) else str(e)[:40]))
            return
        self._fails = 0
        if self.source == "demo":
            m.clear()
            if not self._real:
                m.reset_records()       # so far they hold the demo fleet
        self._real = True
        self.status, self.source, self.note = "LIVE", name, "%d rows from %s" % (len(rows), name)
        self._rows(rows, unix, now)

    def _rows(self, rows, unix, now, record=True):
        if unix:
            self._anchor = (unix, time.ticks_ms())
        self.rows_ms = now
        self.model.ingest(rows, now, self.settings["ground"], record)

    def _failed(self, now, why):
        """Two misses in a row move down the chain (one while probing it from the demo); past its end, fly the demo."""
        self.note = why
        self._fails += 1
        if self._fails < 2 and self.source != "demo":
            self.status = "STALE" if self.rows_ms is not None else "WAIT"
            self._next_poll = now + RETRY_MS
            return
        self._fails = 0
        self._next_poll = 0
        self._live += 1
        if self._live >= len(self._chain):
            self._live = None
            self._retry_live = now + RETRY_LIVE_MS
            self.note = "Demo traffic. " + why

    def _ask_phone(self, now):
        """One ask for the phone's position. A 404 means it has not arrived yet, which is the normal answer.

        No miss counts against the aircraft source: the next ask comes LOCATE_EVERY_MS after this one ends.
        """
        began = time.ticks_ms()
        if self.code and self._online(now):         # a cancel since this job was armed has the last word
            try:
                j = get_json(self._here_url % self.code)
                lat, lon, acc = float(j["lat"]), float(j["lon"]), j.get("acc")
                if -90 <= lat <= 90 and -180 <= lon <= 180:         # also rejects NaN
                    self._pos = (lat, lon, None if acc is None else float(acc))
                    self.code = ""                  # the relay deleted the row as it answered
            except NET_ERRORS:
                pass
        self._next_here = now + time.ticks_diff(time.ticks_ms(), began) + LOCATE_EVERY_MS

    def _track(self, now):
        self._next_track = now + TRACK_EVERY_MS
        try:
            rows, _ = normalise(get_json(self._chain[self._live][2] % self.model.track))
            airborne = [r for r in rows if r[ALT] != 0] or rows
            self.model.ingest_tracked(airborne[0] if airborne else None, now)
        except NET_ERRORS:
            pass

    def _route(self, now):
        m = self.model
        a = self._route_target()
        if not a:
            return
        if len(m.routes) >= 60:
            m.routes.clear()        # a MicroPython dict has no oldest entry; start the memo over
        m.routes[a.cs] = False
        try:
            j = get_json(ROUTE_URL % (a.cs[:2], a.cs))
            ports = j.get("_airports") or ()
            if len(ports) >= 2:
                o, d = _leg([_airport(x) for x in ports], a)
                m.routes[a.cs] = {"o": o, "d": d}
            self._route_fails = 0
        except NET_ERRORS as e:
            self._route_fails += 1
            final = isinstance(e, HttpError) and e.status == 404        # a 404 is final; a timeout or 429 gets two more tries
            if not final and self._route_fails < 3:
                m.routes.pop(a.cs, None)
                self._next_route = now + ROUTE_RETRY_MS
            else:
                self._route_fails = 0

    def _demo_extras(self):
        """Routes and the tracked flight come from the bundled fleet in the demo."""
        m = self.model
        for a in (m.selected(), m.tracked):
            if a and a.cs not in m.routes:
                m.routes[a.cs] = skydemo.route(a.cs, m.home)


def _leg(ports, a):
    """The leg of a route that the aircraft is on. A callsign can cover several stops, or go out and back."""
    best = None
    for o, d in zip(ports, ports[1:]):
        # How far off the straight line between the two airports the aircraft is ...
        off = (skygeo.great_circle_nm(o[2], o[3], a.lat, a.lon) + skygeo.great_circle_nm(a.lat, a.lon, d[2], d[3])
               - skygeo.great_circle_nm(o[2], o[3], d[2], d[3]))
        if a.trk >= 0:
            # ... and whether it is heading for the far end, which settles an out-and-back route.
            off += abs(skygeo.turn(a.trk, skygeo.dist_brg(a.lat, a.lon, d[2], d[3])[1])) * 0.5
        if best is None or off < best[0]:
            best = (off, o, d)
    return best[1], best[2]


def _airport(p):
    return (p.get("iata") or p.get("icao") or "?", p.get("location") or p.get("name") or "",
            float(p.get("lat") or 0), float(p.get("lon") or 0))
