"""Where the rows come from: Supabase Edge Function, a direct feed, or the demo.

Every request belongs to a job: a generator that yields the URL it wants and is
sent back the decoded JSON, or has the failure thrown in. On a badge whose
firmware has the non-blocking fetch.AsyncFetch, a job's request runs across many
frames, so the screen and the buttons never stop. Elsewhere (the browser, older
firmware) the request blocks: the job is armed on one frame, which lets the
screen show SYNC, and runs on the next, and it waits while the buttons are in use.
"""

import time

import config
import skydata
import skydemo
import skygeo
from skymodel import ALT, CAT, CS, DIR, DST, FLAGS, GS, HEX, LAT, LON, REG, SEEN, SQK, TRK, TYPE, VR

try:
    import gc
except ImportError:
    gc = None
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
AsyncFetch = None
if ON_BADGE and getattr(config, "NONBLOCKING", True):
    try:
        from fetch import AsyncFetch
        if not hasattr(AsyncFetch, "TIMEOUT"):
            AsyncFetch = None     # the first firmware fetch (July 2026) still blocks while it connects
    except ImportError:
        pass

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
ROUTE_SETTLE_MS = 1500     # a selection must rest this long before its route is asked for, so paging the list never blocks
ROUTE_SETTLE_BG_MS = 500   # the same rest when requests run in the background: long enough to skip rows paged past
ROUTE_RETRY_BG_MS = 5000   # and the wait after a lookup failed in transit
PREFETCH = 5               # in the background, routes for this many of the nearest are looked up before they are shown
PREFETCH_GAP_MS = 1000     # one such lookup a second at most
LOCATE_EVERY_MS = 2500     # between asks for the position a phone is sending
INPUT_QUIET_MS = 2500      # a request blocks the buttons, so none starts until they have rested this long
INPUT_MAX_DEFER_MS = 20000  # but nothing is held back longer than this, so steady pressing still gets updates
LOCATE_LIFE_MS = 300000    # a locate code is asked for this long, then it expires
VALID_CLOCK = 1735689600      # 2025-01-01: an RTC before this was never set


class HttpError(ValueError):
    """An answer other than 200. status is the HTTP code."""

    def __init__(self, status):
        super().__init__("HTTP %d" % status)
        self.status = status


def _split(url):
    """(use_tls, host, port, path) of an absolute http or https URL."""
    tls_on = url.startswith("https://")
    rest = url[8:] if tls_on else url[7:]
    i = rest.find("/")
    host, path = (rest, "/") if i < 0 else (rest[:i], rest[i:])
    if ":" in host:
        host, port = host.split(":", 1)
        return tls_on, host, int(port), path
    return tls_on, host, 443 if tls_on else 80, path


def get_json(url):
    """GET and decode JSON, blocking. Raises one of NET_ERRORS on any failure."""
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
        self._route_hex = None      # the aircraft whose route is wanted, and since when
        self._route_since = 0
        self._next_prefetch = 0
        self._net_ms = -100000      # when the last blocking request ran
        self._input_ms = -100000    # when a button was last pressed or held
        self._held_ms = None        # when requests began waiting for the buttons, None while they are not
        self._reqs = {}             # lane -> (job, AsyncFetch) for each non-blocking request in flight
        self._clients = {}          # (host, port) -> AsyncFetch: each keeps its connection open between requests
        self._loc_gen = 0           # bumped by every locate, so a late IP answer cannot undo a Setup pick
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
        self.can_live = bool(self._chain and requests)
        self._live = None           # index into _chain, None for demo
        self.set_live(settings.get("live", True))

    # ---- public --------------------------------------------------------

    @property
    def busy(self):
        """A request is under way: the SYNC chip."""
        return self._job is not None or bool(self._reqs)

    @property
    def blocks(self):
        """A blocking request runs in this frame's tick."""
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

    def set_live(self, on):
        """Live data on or off. Off flies the demo and sends no requests at all."""
        self._on = on and self.can_live
        self._live = 0 if self._on else None
        self._fails = 0
        self._next_poll = self._retry_live = 0
        if not self._on:
            self.note = "Demo traffic. " + ("Live data is off" if self.can_live else "Set PROXY_URL in config.py")

    def touch(self, now):
        """A button is in use. Requests wait for the buttons to rest, so a quick press is never lost in one."""
        self._input_ms = now

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
        """Move a request along, run the armed job, or start the next one. `now` is the app's clock: it never wraps."""
        if self._reqs:
            for lane in list(self._reqs):
                self._pump(lane, now)
        if AsyncFetch and "route" not in self._reqs and self._live is not None and self._located:
            # Routes have their own lane and host, so they never wait for a poll.
            if self._route_ready(now, ROUTE_SETTLE_BG_MS, False):
                self._step("route", self._route(now), now)
            elif self._route_target() is None:     # nothing on screen is waiting: fetch ahead
                a = self._prefetch_target(now)
                if a:
                    self._next_prefetch = now + PREFETCH_GAP_MS
                    self._step("route", self._route(now, a), now)
        if "main" in self._reqs:
            return
        if self._job:
            job, self._job = self._job, None
            if self._defer(now):
                return              # a press came after it was armed: it is armed again once the buttons rest
            began = time.ticks_ms()
            self.run(job, now)
            self._held_ms = None
            self._net_ms = now + time.ticks_diff(time.ticks_ms(), began)     # the end of the block, on the app's clock
            if gc:
                gc.collect()        # this frame has already stalled: collect now, not in the middle of an animation
            return
        age = self.age_s(now)
        if self._live is not None and age is not None and age > 3 * config.POLL_S:
            self.status = "STALE"
        job = self._due(now)
        if job and self._live is None and self._located:
            self.run(job, now)      # the demo never blocks, so it needs no SYNC frame
        elif job and AsyncFetch:
            self._step("main", job(now), now)
        elif job and not self._defer(now):
            self._job = job

    def run(self, job, now):
        """Run a job to its end, blocking on each request it makes."""
        gen, val, err = job(now), None, None
        while True:
            try:
                url = gen.send(val) if err is None else gen.throw(err)
            except StopIteration:
                return
            val = err = None
            try:
                val = get_json(url)
            except NET_ERRORS as e:
                err = e

    def _step(self, lane, gen, now, val=None, err=None):
        """Resume a non-blocking job and start the request it asks for next, if any."""
        try:
            url = gen.send(val) if err is None else gen.throw(err)
        except StopIteration:
            self._reqs.pop(lane, None)
            if lane == "main":
                self._net_ms = now
            return
        try:
            client = self._client(url)
            client.fetch(_split(url)[3], headers={"User-Agent": config.CONTACT})
        except Exception as e:      # noqa: BLE001 - a bad URL or a busy client fails this request, not the app
            self._step(lane, gen, now, None, OSError(str(e)))
            return
        self._reqs[lane] = (gen, client)

    def _client(self, url):
        tls_on, host, port, _ = _split(url)
        c = self._clients.get((host, port))
        if c is None:
            c = self._clients[(host, port)] = AsyncFetch(host, port, use_tls=tls_on, timeout=TIMEOUT_S)
            c.on_error(lambda f: True)          # an HTTP error comes back as ERROR with its status, not an exception
        return c

    def _pump(self, lane, now):
        """One slice of a request in flight. Its job resumes once it has an answer."""
        gen, client = self._reqs[lane]
        val = err = None
        try:
            state = client.update()
            if state == AsyncFetch.DONE:
                val = client.to_json()
            elif state == AsyncFetch.ERROR:
                err = HttpError(client.http_status or 0)
            else:
                return              # still under way
        except NET_ERRORS as e:
            err = e
        except Exception as e:      # noqa: BLE001 - the firmware's own errors, such as a failed TLS handshake
            err = OSError(str(e))
        if err is not None:
            try:
                client.reset()      # a half-read answer leaves the connection out of step
            except Exception:       # noqa: BLE001
                pass
        self._reqs.pop(lane, None)
        self._step(lane, gen, now, val, err)

    def _defer(self, now):
        """Whether a blocking job should wait because the buttons are in use. Nothing waits longer than
        INPUT_MAX_DEFER_MS, so steady pressing can never freeze the sky. A non-blocking request never waits."""
        if AsyncFetch or now - self._input_ms >= INPUT_QUIET_MS:
            self._held_ms = None
            return False
        if self._held_ms is None:
            self._held_ms = now
        return now - self._held_ms < INPUT_MAX_DEFER_MS

    # ---- scheduling ----------------------------------------------------

    def _due(self, now):
        if not self._located:
            return self._locate
        if self._live is None and self._on and now >= self._retry_live:
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
        if not AsyncFetch and self._route_ready(now, ROUTE_SETTLE_MS, True):
            return self._route
        return None

    def _prefetch_target(self, now):
        """The nearest airliner whose route is not looked up yet, among the few the auto-cycle shows next."""
        if now < self._next_prefetch or now < self._next_route:
            return None
        for a in self.model.order[:PREFETCH]:
            if a.airline and a.cs not in self.model.routes:
                return a
        return None

    def _route_ready(self, now, settle, spaced):
        """Whether to look a route up now: the selection has rested for settle ms. A blocking lookup is also spaced,
        so it never lands right beside another request."""
        a = self._route_target()
        if a and a.hex != self._route_hex:
            self._route_hex, self._route_since = a.hex, now
        if not a or now < self._next_route or now - self._route_since < settle:
            return False
        return not spaced or (now - self._net_ms >= FEED_GAP_MS and self._next_poll - now >= FEED_GAP_MS)

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
        self._loc_gen += 1
        self.tz_s = None            # an IP lookup sets it; an airport or a pinned HOME has no offset
        self.exact = False
        self._geo_at = None         # a Setup pick cancels a pending lookup
        m, s = self.model, self.settings
        if config.HOME:
            m.set_home(config.HOME[0], config.HOME[1], config.HOME[2] if len(config.HOME) > 2 else "HOME")
            return
            yield                   # a generator, like every job
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
        yield from self._locate_ip(now)

    def _locate_ip(self, now):
        """Ask the IP address where home is. A miss (Wi-Fi still joining, timeout, 429) tries again later.

        With an exact position the answer only names the city and sets the time zone: home stays where it is.
        """
        self._geo_at = None
        if not requests or not self._located:       # a Setup pick since this job was armed has the last word
            return
        gen = self._loc_gen
        online = self._online(now)
        if online:
            self._geo_left -= 1
            try:
                j = yield GEO_URL
                if gen != self._loc_gen or not self._located:
                    return                          # a Setup pick came while the answer was on its way
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
            yield
        if not self._online(now):
            self._failed(now, self.note)
            return
        name, url, _ = self._chain[self._live]
        home, live = m.home, self._live
        began = time.ticks_ms()
        try:
            rows, unix = normalise((yield url % (home[0], home[1], self.fetch_radius())))
        except NET_ERRORS as e:
            if home != m.home or live != self._live:
                return              # home or the source changed while it was on its way: the next poll asks again
            # badge.ticks was latched before the request blocked: count the back-off from its end.
            self._failed(now + time.ticks_diff(time.ticks_ms(), began),
                         "%s: %s" % (name, "no answer" if isinstance(e, OSError) else str(e)[:40]))
            return
        if home != m.home or live != self._live:
            return                  # rows for a place or a source that is no longer the one shown
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
        code = self.code
        if code and self._online(now):              # a cancel since this job was armed has the last word
            try:
                j = yield self._here_url % code
                if self.code != code:
                    return                          # cancelled, or a new code, while it was on its way
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
            rows, _ = normalise((yield self._chain[self._live][2] % self.model.track))
            airborne = [r for r in rows if r[ALT] != 0] or rows
            self.model.ingest_tracked(airborne[0] if airborne else None, now)
        except NET_ERRORS:
            pass

    def _route(self, now, a=None):
        m = self.model
        a = a or self._route_target()
        if not a:
            return
            yield
        if len(m.routes) >= 60:
            m.routes.clear()        # a MicroPython dict has no oldest entry; start the memo over
        m.routes[a.cs] = False
        try:
            j = yield ROUTE_URL % (a.cs[:2], a.cs)
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
                self._next_route = now + (ROUTE_RETRY_BG_MS if AsyncFetch else ROUTE_RETRY_MS)
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
