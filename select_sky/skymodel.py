"""The sky as a table: one row per aircraft, kept moving between feed updates."""

import skydata
import skygeo

# Column order of a feed row, shared with the Edge Function and the demo.
HEX, CS, TYPE, ALT, GS, TRK, VR, LAT, LON, SQK, FLAGS, DST, DIR, CAT, REG, SEEN = range(16)

EMERGENCY = {"7500": "Unlawful interference", "7600": "Radio failure", "7700": "General emergency"}
TRAIL_MAX = 10
HISTORY_MAX = 40
RANGES = (5, 10, 25, 50, 100)    # what counts as nearby, in nautical miles: the choices Setup and the radar cycle
LOST_MS = 40000      # drop a row this long after the feed last reported it
SEEN_MAX = 4000      # past this many remembered aircraft the de-duplication set restarts from the current rows
COAST_S = 60         # stop extrapolating a position after this many seconds
ADVANCE_MS = 125     # every row is dead-reckoned about this often, a slice per frame


def _phase(alt, vr):
    if alt < 0:
        return "NO ALT"
    if alt == 0:
        return "GROUND"
    if vr > 300:
        return "CLIMB"
    if vr < -300:
        return "DESCENT"
    return "CRUISE" if alt >= 18000 else "LEVEL"


class Aircraft:
    def __init__(self, hex_id, now):
        self.hex = hex_id
        self.cs = self.type = self.sqk = self.reg = ""
        self.alt = self.gs = self.trk = -1
        self.vr = self.flags = 0
        self.lat = self.lon = self.lat0 = self.lon0 = 0.0
        self.t0 = self.seen_ms = self.first_ms = now
        self.dist = self.brg = self.dx = self.dy = 0.0
        self.trail = []         # (lat, lon, alt) at each reported move
        self.alts = []
        self.speeds = []
        self.airline = None
        self.glyph = 0
        self.cls = skydata.OTHER
        # What the report says, worked out once in load() rather than on every read.
        self.label = hex_id.upper()
        self.on_ground = self.military = False
        self.emergency = None
        self.phase = "NO ALT"
        self.operator = "Private"
        self.kind = "Unknown type"

    def load(self, row, now):
        self.cs, self.type, self.alt = row[CS], row[TYPE], row[ALT]
        self.gs, self.trk, self.vr = row[GS], row[TRK], row[VR]
        self.sqk, self.flags, self.reg = row[SQK], row[FLAGS], row[REG]
        moved = row[LAT] != self.lat0 or row[LON] != self.lon0
        self.lat0, self.lon0 = row[LAT], row[LON]
        self.t0 = now - int(row[SEEN] * 1000)
        self.seen_ms = now
        al = self.airline = skydata.airline(self.cs)
        self.glyph = skydata.glyph(self.type, row[CAT])
        if moved:
            self.trail.append((self.lat0, self.lon0, self.alt))
            if len(self.trail) > TRAIL_MAX:
                self.trail.pop(0)
        if self.alt >= 0:
            self.alts.append(self.alt)
            self.speeds.append(max(0, self.gs))
            if len(self.alts) > HISTORY_MAX:
                self.alts.pop(0)
                self.speeds.pop(0)
        self.label = self.cs or self.reg or self.hex.upper()
        self.on_ground = self.alt == 0
        self.military = bool(self.flags & 1)
        self.emergency = EMERGENCY.get(self.sqk)
        self.phase = _phase(self.alt, self.vr)
        self.operator = al[1] if al and al[1] else "Military" if self.military else "Private" if not al else al[0]
        self.kind = skydata.type_name(self.type) or "Unknown type"
        self.cls = skydata.classify(self.type, row[CAT], self.flags, self.cs)

    def move(self, now, home):
        """Dead-reckon from the last report, then refresh offset, range and bearing."""
        dt = min(COAST_S, (now - self.t0) / 1000.0)
        if self.gs > 0 and self.trk >= 0 and dt > 0:
            self.lat, self.lon = skygeo.advance(self.lat0, self.lon0, self.trk, self.gs * dt / 3600.0)
        else:
            self.lat, self.lon = self.lat0, self.lon0
        off = skygeo.offset_nm(home[0], home[1], self.lat, self.lon)
        self.dx, self.dy = off
        self.dist, self.brg = skygeo.dist_brg(home[0], home[1], self.lat, self.lon, off)


class Model:
    def __init__(self):
        self.home = (0.0, 0.0)
        self.home_label = ""
        self.rows = {}          # hex -> Aircraft
        self.range_nm = 25      # what counts as nearby
        self.order = []         # within range: nearest first, airborne ahead of ground traffic
        self.outer = []         # reported but beyond range, for the radar's rim
        self.sel = None         # hex of the selected aircraft
        self.auto = True        # the app cycles the selection through the nearest few
        self.routes = {}        # callsign -> {"o": airport, "d": airport} or False if unknown
        self.track = ""         # callsign followed anywhere in the world
        self.tracked = None     # its Aircraft, once found
        self.alert = None       # Aircraft squawking an emergency, until acknowledged
        self.acked = set()
        self.fresh = 0          # aircraft that came into range in the last update
        self._near = set()
        self._seq = []          # every row, in the order advance() walks them
        self._cur = 0           # where the next advance() slice starts
        self._adv_ms = 0        # when advance() last ran
        self.want = ("all", "", "")     # the filter: class preset, airline prefix, ICAO type; "" means any
        self.mask = skydata.ALL         # classes the preset lets through, one bit each
        self.active = False             # the filter narrows the lists
        self.hidden = 0                 # aircraft in range that the filter keeps out of order; 0 with no filter
        self._alert_seen = None         # the alert alert_age() is timing
        self._alert_ms = 0              # when that alert first showed
        self.reset_records()

    def reset_records(self):
        """Start the session records over."""
        self.seen = set()
        self.stats = {"seen": 0, "peak": 0, "high": 0, "high_cs": "", "fast": 0, "fast_cs": "",
                      "near": 9999.0, "near_cs": ""}
        self.airlines = {}      # ICAO prefix -> aircraft seen this session

    def clear(self):
        """Forget every aircraft, such as when the feed changes between live and demo."""
        self.rows = {}
        self.tracked = None
        self.fresh = 0
        self._near = set()
        self._sort()                # empties order and outer, and drops the selection

    def set_home(self, lat, lon, label):
        moved = (lat, lon) != self.home
        self.home = (lat, lon)
        self.home_label = label
        self.routes = {}            # demo routes are anchored to home
        for a in self.rows.values():
            a.trail = []
        if moved:                   # the old sky and its records belong to the old home
            self.rows = {}
            self._sort()            # empties order and outer, and clears the selection
            self.reset_records()

    def ingest(self, rows, now, show_ground=True, record=True):
        """Merge a feed update: upsert reported aircraft, drop the ones that left.

        record=False keeps the update out of the session records. The feed asks for it
        for demo traffic once a live source has answered; before that the demo fills them.
        """
        st = self.stats
        for row in rows:
            if not show_ground and row[ALT] == 0:
                self.rows.pop(row[HEX], None)       # landed, or Ground traffic was just switched off
                continue
            a = self.rows.get(row[HEX])
            if a is None:
                a = self.rows[row[HEX]] = Aircraft(row[HEX], now)
            a.load(row, now)
            a.move(now, self.home)
            if record and a.dist <= self.range_nm and self.shown(a):
                # The records describe the sky you chose, range and filter, not the feed's wider net.
                if a.hex not in self.seen:
                    if len(self.seen) >= SEEN_MAX:
                        self.seen = set(self.rows)
                    self.seen.add(a.hex)
                    st["seen"] += 1
                    if a.airline:
                        self.airlines[a.airline[0]] = self.airlines.get(a.airline[0], 0) + 1
                if a.alt > st["high"]:
                    st["high"], st["high_cs"] = a.alt, a.label
                if a.gs > st["fast"]:
                    st["fast"], st["fast_cs"] = a.gs, a.label
                if a.alt > 0 and a.dist < st["near"]:
                    st["near"], st["near_cs"] = a.dist, a.label
            if a.emergency and a.hex not in self.acked and self.alert is None:
                self.alert = a
        for h in [h for h, a in self.rows.items() if now - a.seen_ms > LOST_MS]:
            del self.rows[h]
        if self.alert and not self.alert.emergency:
            self.alert = None                       # the squawk was cleared before anyone acknowledged it
        was_near = self._near
        self._sort()
        self._near = set(a.hex for a in self.order)
        self.fresh = len(self._near - was_near)
        if record:
            st["peak"] = max(st["peak"], len(self.order))
        if self.track:
            hit = [a for a in self.rows.values() if a.cs == self.track]
            if hit:
                self.tracked = hit[0]

    def ingest_tracked(self, row, now):
        """Result of a worldwide callsign lookup: None when the flight is not airborne."""
        if row is None:
            if self.tracked and self.tracked.hex not in self.rows:
                self.tracked = None
            return
        a = self.rows.get(row[HEX])
        if a is None:
            a = self.tracked if self.tracked and self.tracked.hex == row[HEX] else Aircraft(row[HEX], now)
            a.load(row, now)
            a.move(now, self.home)
        self.tracked = a
        if self.alert and not self.alert.emergency:
            self.alert = None                       # the tracked flight was the alert, and its squawk cleared

    def set_track(self, callsign):
        callsign = (callsign or "").strip().upper()
        self.track = callsign
        hit = [a for a in self.rows.values() if a.cs == callsign] if callsign else ()
        self.tracked = hit[0] if hit else None
        if self.active:
            self._sort()                # a tracked flight the filter hides appears at once, and leaves at once
            self._near = set(a.hex for a in self.order)     # following a flight is not an arrival

    def advance(self, now):
        """Dead-reckon a slice of the rows, so a whole sky is covered every ADVANCE_MS and no frame pays for all of it."""
        seq, last, self._adv_ms = self._seq, self._adv_ms, now
        n = len(seq)
        if n:
            k = min(n, 1 + n * (now - last) // ADVANCE_MS)
            i = self._cur
            for j in range(k):
                seq[(i + j) % n].move(now, self.home)
            self._cur = (i + k) % n
        if self.tracked and self.tracked.hex not in self.rows:
            self.tracked.move(now, self.home)

    def _sort(self):
        self._seq = list(self.rows.values())            # hidden rows still dead-reckon
        near, outer, hidden = [], [], 0
        for a in self._seq:
            if self.shown(a):
                if a.dist <= self.range_nm:
                    near.append(a)
                else:
                    outer.append(a)                     # the radar rim obeys the filter too
            elif a.dist <= self.range_nm and a.cls != skydata.OTHER:
                hidden += 1
        self.hidden, self.outer = hidden, outer
        self.order = sorted(near, key=lambda a: (a.on_ground, a.dist))
        if not self.order:
            self.sel = None
        elif self.selected() not in self.order:
            self.sel = self.order[0].hex

    def set_filter(self, show="all", airline="", craft=""):
        """Narrow order and outer to a class preset, one airline and one ICAO type; the three AND together.

        Returns the values kept: anything unrecognised, such as junk in a saved setting, becomes the
        neutral value. The session records restart, because they describe the sky you chose.
        """
        info = skydata.show_info(show) or skydata.SHOWS[0]
        want = (info[0], airline[:3] if isinstance(airline, str) else "", craft[:4] if isinstance(craft, str) else "")
        if want == self.want:
            return want                                 # nothing changed: keep the records
        self.want, self.mask = want, info[2]
        self.active = want != ("all", "", "")
        self.reset_records()
        self._sort()
        self._near = set(a.hex for a in self.order)     # a filter change is not an arrival
        self.fresh = 0
        return want

    def shown(self, a):
        """Whether the filter lets an aircraft into the lists. A squawking or tracked flight always gets in."""
        if not self.active or a.emergency or (self.track and a.cs == self.track):
            return True
        if not (self.mask >> a.cls) & 1:
            return False
        if self.want[1] and not (a.airline and a.airline[0] == self.want[1]):
            return False
        return not self.want[2] or a.type == self.want[2]

    def choices(self, key):
        """Values the Show, Airline and Aircraft type rows step through, the neutral one first.

        Airlines and types come from the aircraft in range now, whatever the filter says, so a narrow
        pick never hides the others. Both lists are sorted: dicts and sets keep no order on the badge.
        """
        if key == "show":
            return tuple(t[0] for t in skydata.SHOWS)
        near = [a for a in self.rows.values() if a.dist <= self.range_nm and a.cls != skydata.OTHER]
        if key == "airline":                            # airliners and heavies only: no flight schools, no military
            got = set(a.airline[0] for a in near if a.airline and a.cls in (skydata.AIRLINER, skydata.HEAVY))
            return ("",) + tuple(sorted(got, key=lambda p: (skydata.carrier_name(p).lower(), p)))
        return ("",) + tuple(sorted(set(a.type for a in near if a.type)))

    def set_range(self, nm):
        self.range_nm = nm
        self._sort()

    def selected(self):
        return self.rows.get(self.sel)

    def index(self):
        """Position of the selection in order; 0 when it is out of range or absent."""
        a = self.selected()
        return self.order.index(a) if a in self.order else 0

    def step(self, delta):
        """Move the selection up or down the list and stop it following the nearest."""
        if not self.order:
            return
        self.auto = False
        if self.selected() in self.order:
            self.sel = self.order[(self.index() + delta) % len(self.order)].hex
        else:                       # off the list: start at the nearest end rather than skipping it
            self.sel = self.order[0 if delta > 0 else -1].hex

    def select(self, hex_id):
        """Pick an aircraft and stop the app cycling the selection."""
        if hex_id in self.rows:     # an aircraft that has since left would blank the views
            self.sel = hex_id
            self.auto = False

    def acknowledge(self):
        if self.alert:
            self.acked.add(self.alert.hex)
        self.alert = next((a for a in self.rows.values() if a.emergency and a.hex not in self.acked), None)

    def alert_age(self, now):
        """Milliseconds the alert has been up. Its clock starts the first time this is asked; 0 with no alert."""
        if self.alert is not self._alert_seen:
            self._alert_seen, self._alert_ms = self.alert, now
        return now - self._alert_ms if self.alert else 0

    def restart_alert_clock(self):
        """An alert still up gets its full time from now, such as after the badge wakes."""
        self._alert_seen = None

    def dismiss_alert(self):
        """Acknowledge the alert and select its aircraft if it is listed. The auto-cycle is left running."""
        a = self.alert
        self.acknowledge()
        if a in self.order:                             # one beyond the range cannot be the selection
            self.sel = a.hex

    def route(self, a):
        """Route for an aircraft, or None while unknown."""
        return self.routes.get(a.cs) or None

    def progress(self, a):
        """Fraction of the route flown, 0..1, or None without a route."""
        r = self.route(a)
        if not r or not ((r["o"][2] or r["o"][3]) and (r["d"][2] or r["d"][3])):
            return None             # an airport without coordinates is at 0, 0
        done = skygeo.great_circle_nm(r["o"][2], r["o"][3], a.lat, a.lon)
        left = skygeo.great_circle_nm(a.lat, a.lon, r["d"][2], r["d"][3])
        return done / (done + left) if done + left > 0 else None
