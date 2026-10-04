#!/usr/bin/env python3
"""Desktop checks for the parts of Select Sky that need no badge: maths, model, feeds.

Run from the workspace root:  python3 tests/test_logic.py
Drawing, input and networking only run on the badge or in badge.select Make.
"""

import ast
import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "select_sky"))

# MicroPython's tick helpers, for the one module that uses them at call time.
time.ticks_ms = lambda: int(time.monotonic() * 1000)
time.ticks_diff = lambda a, b: a - b

import config  # noqa: E402
import skydata  # noqa: E402
import skydemo  # noqa: E402
import skyfeed  # noqa: E402
import skygeo  # noqa: E402
import skyqr  # noqa: E402
from skymodel import ALT, CS, HEX, LAT, LON, SEEN, Model  # noqa: E402

SFO = (37.6213, -122.3790)
OAK = (37.7213, -122.2208)


def row(hex_id="abc123", cs="UAL1", alt=30000, gs=450, trk=90, lat=37.7, lon=-122.3, sqk="1200", seen=0, flags=0):
    return (hex_id, cs, "B738", alt, gs, trk, 0, lat, lon, sqk, flags, 0, 0, "A3", "N1", seen)


class Geo(unittest.TestCase):
    def test_distance_and_bearing(self):
        d, b = skygeo.dist_brg(SFO[0], SFO[1], OAK[0], OAK[1])
        self.assertAlmostEqual(d, 9.6, delta=0.3)          # SFO to OAK is about 9.6 nm
        self.assertAlmostEqual(b, 51, delta=3)             # and lies north-east

    def test_advance_round_trip(self):
        lat, lon = skygeo.advance(SFO[0], SFO[1], 90, 10)
        d, b = skygeo.dist_brg(SFO[0], SFO[1], lat, lon)
        self.assertAlmostEqual(d, 10, delta=0.05)
        self.assertAlmostEqual(b, 90, delta=0.5)

    def test_far_bearing_uses_great_circle(self):
        d, b = skygeo.dist_brg(37.6213, -122.379, 51.47, -0.4543)        # SFO to LHR
        self.assertAlmostEqual(d, 4664, delta=40)
        self.assertAlmostEqual(b, 33, delta=2)                           # leaves north-north-east, not due east

    def test_great_circle(self):
        self.assertAlmostEqual(skygeo.great_circle_nm(37.6213, -122.379, 40.6413, -73.7781), 2247, delta=25)  # SFO-JFK

    def test_offsets_take_the_short_way_over_the_antimeridian(self):
        east, north = skygeo.offset_nm(-16.69, 179.95, -16.69, -179.95)      # Taveuni: 0.1 degrees east
        self.assertAlmostEqual(east, 5.75, delta=0.1)
        self.assertAlmostEqual(north, 0, delta=0.01)
        east, _ = skygeo.offset_nm(-16.69, -179.95, -16.69, 179.95)
        self.assertAlmostEqual(east, -5.75, delta=0.1)
        self.assertAlmostEqual(skygeo.offset_nm(0, 179.9, 0, 180.1)[0], 12.0, delta=0.01)

    def test_elevation_follows_the_curve_of_the_earth(self):
        self.assertAlmostEqual(skygeo.elevation(6076.12, 1), 45, delta=0.1)
        self.assertAlmostEqual(skygeo.elevation(35000, 0), 90, delta=0.01)
        self.assertLess(skygeo.elevation(35000, 100), 90)
        self.assertLess(skygeo.elevation(35000, 250), 0)    # past the horizon, about 200 nm away at this height
        self.assertLess(skygeo.elevation(1000, 100), 0)
        self.assertEqual((skygeo.elevation(0, 5), skygeo.elevation(-1, 5)), (0.0, 0.0))     # no height, no angle

    def test_saved_exact_position_is_a_checked_pair(self):
        pos = lambda v: skygeo.exact_pos({"pos": v})        # noqa: E731
        self.assertEqual(pos([33.4512, -112.0638]), (33.4512, -112.0638))
        self.assertEqual(pos((90, -180)), (90.0, -180.0))
        self.assertEqual(pos([-90, 180]), (-90.0, 180.0))
        self.assertIsNone(skygeo.exact_pos({}))                               # settings saved before the position existed
        for bad in (None, [], [1], [1, 2, 3], "12", ["a", "b"], [None, 0], {"lat": 1, "lon": 2}, 5,
                    [90.0001, 0], [-90.0001, 0], [0, 180.0001], [0, -180.0001], [float("nan"), 0], [0, float("inf")]):
            self.assertIsNone(pos(bad), bad)

    def test_compass_and_turn(self):
        self.assertEqual(skygeo.compass(0), "N")
        self.assertEqual(skygeo.compass(359), "N")
        self.assertEqual(skygeo.compass(225), "SW")
        self.assertEqual(skygeo.turn(350, 10), 20)
        self.assertEqual(skygeo.turn(10, 350), -20)


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.m = Model()
        self.m.set_home(SFO[0], SFO[1], "SFO")

    def test_ingest_sorts_nearest_airborne_first(self):
        self.m.ingest([row("far", lat=37.9), row("near", lat=37.65), row("gnd", alt=0, lat=37.63)], 0)
        self.assertEqual([a.hex for a in self.m.order], ["near", "far", "gnd"])
        self.assertEqual(self.m.sel, "near")
        self.assertEqual(self.m.stats["seen"], 3)

    def test_range_splits_order_and_outer(self):
        self.m.ingest([row("in", lat=37.7), row("out", lat=38.4)], 0)
        self.assertEqual([a.hex for a in self.m.order], ["in"])
        self.assertEqual([a.hex for a in self.m.outer], ["out"])
        self.m.set_range(100)
        self.assertEqual(len(self.m.order), 2)

    def test_ground_filter(self):
        self.m.ingest([row("gnd", alt=0)], 0, show_ground=False)
        self.assertEqual(self.m.order, [])

    def test_dead_reckoning_moves_east(self):
        self.m.ingest([row(gs=360, trk=90, lat=37.62, lon=-122.38)], 0)
        a = self.m.order[0]
        self.m.advance(10000)                               # 10 s at 360 kt is 1 nm
        east, north = skygeo.offset_nm(37.62, -122.38, a.lat, a.lon)
        self.assertAlmostEqual(east, 1.0, delta=0.02)
        self.assertAlmostEqual(north, 0.0, delta=0.02)

    def test_coasting_stops(self):
        self.m.ingest([row(gs=360, trk=90, lat=37.62, lon=-122.38)], 0)
        a = self.m.order[0]
        a.move(600000, self.m.home)                         # ten minutes later: capped at 60 s
        east, _ = skygeo.offset_nm(37.62, -122.38, a.lat, a.lon)
        self.assertAlmostEqual(east, 6.0, delta=0.1)

    def test_lost_rows_are_pruned(self):
        self.m.ingest([row("a"), row("b", lat=37.75)], 0)
        self.m.ingest([row("a")], 20000)
        self.assertEqual(len(self.m.rows), 2)               # b is kept while it may only be late
        self.m.ingest([row("a")], 50000)
        self.assertEqual(list(self.m.rows), ["a"])

    def test_selection_survives_updates_and_steps(self):
        self.m.ingest([row("a", lat=37.65), row("b", lat=37.7), row("c", lat=37.8)], 0)
        self.m.step(1)
        self.assertEqual(self.m.sel, "b")
        self.assertFalse(self.m.auto)
        self.m.ingest([row("a", lat=37.65), row("b", lat=37.7)], 1000)
        self.assertEqual(self.m.sel, "b")
        self.m.ingest([row("a", lat=37.65)], 60000)         # b left: fall back to the nearest
        self.assertEqual(self.m.sel, "a")
        self.m.ingest([], 200000)
        self.assertIsNone(self.m.sel)
        self.m.step(1)                                      # must not raise on an empty sky

    def test_selecting_out_of_range_aircraft_is_safe(self):
        self.m.ingest([row("in", lat=37.7), row("out", lat=38.4)], 0)
        self.m.select("out")                                # as an acknowledged alert does
        self.assertEqual(self.m.index(), 0)
        self.m.step(1)
        self.assertEqual(self.m.sel, "in")

    def test_seen_count_does_not_inflate(self):
        for i in range(3):
            self.m.ingest([row("a"), row("far", lat=38.4)], i * 1000)
        self.assertEqual(self.m.stats["seen"], 1)           # repeats and out-of-range rows do not count

    def test_hiding_ground_traffic_removes_it_now(self):
        self.m.ingest([row("g", alt=0, lat=37.63), row("a", lat=37.7)], 0, show_ground=True)
        self.assertEqual([a.hex for a in self.m.order], ["a", "g"])
        self.m.ingest([row("g", alt=0, lat=37.63), row("a", lat=37.7)], 1000, show_ground=False)
        self.assertEqual([a.hex for a in self.m.order], ["a"])

    def test_an_aircraft_that_lands_with_ground_hidden_stops_flying(self):
        self.m.ingest([row("x", alt=600, gs=140, lat=37.65)], 0, show_ground=False)
        self.m.ingest([row("x", alt=0, gs=10, lat=37.65)], 12000, show_ground=False)
        self.assertNotIn("x", self.m.rows)

    def test_second_emergency_is_raised_when_the_first_is_acknowledged(self):
        self.m.ingest([row("e1", sqk="7700", lat=37.65), row("e2", sqk="7600", lat=37.7)], 0)
        first = self.m.alert
        self.m.acknowledge()
        self.assertIsNotNone(self.m.alert)
        self.assertNotEqual(self.m.alert.hex, first.hex)
        self.m.acknowledge()
        self.assertIsNone(self.m.alert)

    def test_alert_ends_when_the_squawk_clears(self):
        self.m.ingest([row("e1", sqk="7700", lat=37.65)], 0)
        self.m.ingest([row("e1", sqk="1200", lat=37.65)], 12000)
        self.assertIsNone(self.m.alert)                     # the overlay would draw None
        self.m.ingest([row("e1", sqk="7700", lat=37.65)], 24000)
        self.m.ingest([row("e1", sqk="7600", lat=37.65)], 36000)
        self.assertEqual(self.m.alert.emergency, "Radio failure")
        self.m.set_track("UAL1")                            # the alert is also the followed flight
        self.m.ingest([], 100000)                           # pruned from the table, still followed
        self.assertEqual(self.m.alert.emergency, "Radio failure")
        self.m.ingest_tracked(row("e1", sqk="1200"), 100000)
        self.assertIsNone(self.m.alert)

    def test_acknowledging_an_alert_for_an_aircraft_that_left_keeps_the_views_filled(self):
        self.m.ingest([row("e1", sqk="7700", lat=37.65), row("ok", lat=37.7)], 0)
        a = self.m.alert
        self.m.ingest([row("ok", lat=37.7)], 50000)         # e1 left and was pruned while the alert sat
        self.assertIs(self.m.alert, a)
        self.m.acknowledge()
        self.m.select(a.hex)                                # as skyoverlay.alert does
        self.assertEqual(self.m.selected().hex, "ok")

    def test_step_from_an_unlisted_selection_starts_at_the_nearest(self):
        self.m.ingest([row("in1", lat=37.65), row("in2", lat=37.7), row("out", lat=38.4)], 0)
        self.m.select("out")
        self.m.step(1)
        self.assertEqual(self.m.sel, "in1")
        self.m.select("out")
        self.m.step(-1)
        self.assertEqual(self.m.sel, "in2")

    def test_home_change_forgets_the_old_sky_and_its_records(self):
        self.m.ingest([row("sfo1", lat=37.65, lon=-122.38, sqk="7700")], 0)
        self.assertEqual(self.m.stats["seen"], 1)
        self.m.set_home(SFO[0], SFO[1], "SFO")              # the same place is no move
        self.assertEqual(list(self.m.rows), ["sfo1"])
        self.m.set_home(40.64, -73.78, "JFK")
        self.assertEqual((self.m.rows, self.m.order, self.m.outer, self.m.sel), ({}, [], [], None))
        self.m.ingest([row("jfk1", lat=40.7, lon=-73.8)], 13000)
        self.assertEqual(sorted(self.m.rows), ["jfk1"])
        self.assertEqual((self.m.stats["seen"], len(self.m.seen), self.m.airlines), (1, 1, {"UAL": 1}))

    def test_clear_forgets_every_aircraft_for_a_source_change(self):
        self.m.ingest([row("a", cs="UAL1")], 0)
        self.m.set_track("UAL1")
        self.m.clear()
        self.assertEqual((self.m.rows, self.m.order, self.m.sel, self.m.tracked), ({}, [], None, None))
        self.assertEqual(self.m.track, "UAL1")

    def test_unrecorded_updates_stay_out_of_the_session_records(self):
        self.m.ingest([row("d1", alt=39000, gs=500, lat=37.65), row("d2", lat=37.7)], 0, record=False)
        self.assertEqual(len(self.m.order), 2)
        self.assertEqual((self.m.stats["seen"], self.m.stats["peak"], self.m.stats["high"], self.m.airlines), (0, 0, 0, {}))
        self.m.ingest([row("r1", lat=37.65)], 1000)
        self.assertEqual((self.m.stats["seen"], self.m.stats["peak"]), (1, 3))

    def test_unknown_altitude_has_its_own_phase(self):
        self.m.ingest([row("a", alt=-1), row("b", alt=0, lat=37.63), row("c", alt=30000, lat=37.75)], 0)
        self.assertEqual([self.m.rows[h].phase for h in "abc"], ["NO ALT", "GROUND", "CRUISE"])

    def test_track_callsign_is_normalised(self):
        self.m.ingest([row("a", cs="UAL1")], 0)
        for typed in ("ual1", " UAL1 ", "UAL1"):
            self.m.set_track(typed)
            self.assertEqual((self.m.track, self.m.tracked.hex), ("UAL1", "a"))
        self.m.set_track(None)
        self.assertEqual((self.m.track, self.m.tracked), ("", None))

    def test_every_row_is_dead_reckoned_within_a_few_frames(self):
        self.m.ingest([row("h%03d" % i, lat=37.6 + i * 0.001, lon=-122.38) for i in range(100)], 0)
        start = {h: a.lon for h, a in self.m.rows.items()}
        moved_per_frame = []
        for t in range(16, 160, 16):                        # nine frames at 60 Hz
            before = {h: a.lon for h, a in self.m.rows.items()}
            self.m.advance(t)
            moved_per_frame.append(sum(1 for h, a in self.m.rows.items() if a.lon != before[h]))
        self.assertTrue(all(a.lon != start[h] for h, a in self.m.rows.items()))
        self.assertLess(max(moved_per_frame), 40)           # no frame pays for the whole sky
        self.m.advance(5000)                                # after a long pause one call catches every row up
        a = self.m.rows["h050"]
        east, _ = skygeo.offset_nm(a.lat0, a.lon0, a.lat, a.lon)
        self.assertAlmostEqual(east, 450 * 5 / 3600.0, delta=0.01)

    def test_a_followed_flight_outside_the_table_still_moves_every_call(self):
        self.m.set_track("BAW285")
        self.m.ingest_tracked(row("far", cs="BAW285", lat=51.4, lon=-0.4, gs=360, trk=90), 0)
        lon = self.m.tracked.lon
        self.m.advance(10000)
        self.assertGreater(self.m.tracked.lon, lon)

    def test_set_track_finds_a_present_aircraft_at_once(self):
        self.m.ingest([row("a", cs="UAL1")], 0)
        self.m.set_track("UAL1")
        self.assertEqual(self.m.tracked.hex, "a")
        self.m.set_track("")
        self.assertIsNone(self.m.tracked)

    def test_emergency_alert_and_acknowledge(self):
        self.m.ingest([row("a", sqk="7700")], 0)
        self.assertEqual(self.m.alert.hex, "a")
        self.assertEqual(self.m.alert.emergency, "General emergency")
        self.m.acknowledge()
        self.m.ingest([row("a", sqk="7700")], 1000)
        self.assertIsNone(self.m.alert)

    def test_history_is_capped(self):
        for i in range(60):
            self.m.ingest([row(lat=37.6 + i * 0.001, alt=30000 + i)], i * 1000)
        a = self.m.order[0]
        self.assertEqual(len(a.alts), 40)
        self.assertEqual(len(a.trail), 10)
        self.assertEqual(a.trail[-1], (a.lat0, a.lon0, 30059))      # each trail point keeps the altitude it was reported at

    def test_a_report_sets_the_names_the_views_show(self):
        untyped = list(row("u", lat=37.8))
        untyped[2] = ""
        self.m.ingest([row("a"), row("m", cs="RCH871", lat=37.65), row("f", cs="N512SP", flags=1, lat=37.7),
                       row("p", cs="N512SP", lat=37.75), row("z", cs="ZZZ123", lat=37.72), untyped], 0)
        r = self.m.rows
        self.assertEqual([r[h].operator for h in "amfpz"], ["United", "Military", "Military", "Private", "ZZZ"])
        self.assertEqual((r["a"].kind, r["u"].kind), ("737-800", "Unknown type"))
        self.assertEqual([(r[h].label, r[h].military, r[h].on_ground) for h in "af"], [("UAL1", False, False), ("N512SP", True, False)])
        self.assertEqual((r["u"].label, r["u"].operator), ("UAL1", "United"))
        g = list(row("g", cs="", alt=0, lat=37.63))
        self.m.ingest([g], 1000)
        self.assertEqual((r["g"].label, r["g"].on_ground, r["g"].emergency, r["g"].operator), ("N1", True, None, "Private"))

    def test_an_aircraft_keeps_its_offset_from_home_as_it_moves(self):
        self.m.ingest([row(gs=360, trk=90, lat=37.62, lon=-122.38)], 0)
        a = self.m.order[0]
        self.m.advance(10000)
        self.assertEqual((a.dx, a.dy), skygeo.offset_nm(SFO[0], SFO[1], a.lat, a.lon))
        self.assertEqual((a.dist, a.brg), skygeo.dist_brg(SFO[0], SFO[1], a.lat, a.lon))

    def test_tracking(self):
        self.m.set_track("UAL1")
        self.m.ingest([row("a", cs="UAL1")], 0)
        self.assertEqual(self.m.tracked.hex, "a")
        self.m.set_track("BAW285")
        self.m.ingest_tracked(row("far", cs="BAW285", lat=51.4, lon=-0.4), 0)
        self.assertEqual(self.m.tracked.cs, "BAW285")
        self.assertGreater(self.m.tracked.dist, 4000)
        self.assertNotIn("far", self.m.rows)                # followed, but not "nearby"
        self.m.ingest_tracked(None, 1000)
        self.assertIsNone(self.m.tracked)

    def test_progress(self):
        self.m.ingest([row("a", cs="UAL1", lat=39.0, lon=-98.0)], 0)
        a = self.m.rows["a"]
        self.assertIsNone(self.m.progress(a))
        self.m.routes["UAL1"] = {"o": ("SFO", "San Francisco", 37.6213, -122.379), "d": ("JFK", "New York", 40.6413, -73.7781)}
        self.assertAlmostEqual(self.m.progress(a), 0.5, delta=0.08)
        self.m.routes["UAL1"] = False
        self.assertIsNone(self.m.progress(a))
        nowhere = ("PUJ", "", 0.0, 0.0)                     # an airport without coordinates is at 0, 0
        for o, d in ((nowhere, nowhere), (("SFO", "", 37.6213, -122.379), nowhere), (nowhere, ("JFK", "", 40.6413, -73.7781))):
            self.m.routes["UAL1"] = {"o": o, "d": d}
            self.assertIsNone(self.m.progress(a))


class Demo(unittest.TestCase):
    def test_rows_are_well_formed_and_in_range(self):
        for t in (0, 12, 600, 3600, 86400):
            rows = skydemo.rows(SFO, t, 37)
            self.assertGreater(len(rows), 2, "the demo sky should never be empty at t=%d" % t)
            for r in rows:
                self.assertEqual(len(r), 16)
                d, _ = skygeo.dist_brg(SFO[0], SFO[1], r[LAT], r[LON])
                self.assertLessEqual(d, 37.5)
                self.assertGreater(r[ALT], 0)

    def test_fleet_moves_along_its_track(self):
        a = {r[HEX]: r for r in skydemo.rows(SFO, 0, 70)}
        b = {r[HEX]: r for r in skydemo.rows(SFO, 10, 70)}
        for h in a.keys() & b.keys():
            d, brg = skygeo.dist_brg(a[h][LAT], a[h][LON], b[h][LAT], b[h][LON])
            self.assertAlmostEqual(d, a[h][4] * 10 / 3600.0, delta=0.05)
            self.assertLess(abs(skygeo.turn(brg, a[h][5])), 2)

    def test_alert_and_routes(self):
        self.assertTrue(any(r[9] == "7700" for r in skydemo.rows(SFO, 0, 70, alert=True)))
        self.assertFalse(any(r[9] == "7700" for r in skydemo.rows(SFO, 0, 70)))
        for f in skydemo.FLEET:
            r = skydemo.route(f[0], SFO)
            if f[8]:
                self.assertIn(r["o"][0], skydata.AIRPORTS)
                self.assertNotEqual(r["o"][0], r["d"][0])
            else:
                self.assertFalse(r)
        self.assertFalse(skydemo.route("NOPE1", SFO))
        # Arrivals land at the airport nearest home; departures leave from it.
        self.assertEqual(skydemo.route("ASA331", (33.43, -112.01))["d"][0], "PHX")
        self.assertEqual(skydemo.route("DAL402", (33.43, -112.01))["o"][0], "PHX")

    def test_the_test_squawk_reaches_the_badge_at_every_range(self):
        for radius in (7, 15, 37, 100):                     # one and a half times a 5, 10, 25 and 100 nm range
            for t in range(0, 2000, 37):
                self.assertTrue(any(r[9] == "7700" for r in skydemo.rows(SFO, t, radius, alert=True)), (radius, t))

    def test_arrivals_end_and_departures_start_at_the_airport_nearest_home_for_every_home(self):
        for code, (_city, lat, lon) in skydata.AIRPORTS.items():
            for f in skydemo.FLEET:
                if not f[8] or f[6] == skydemo.LEVEL:
                    continue
                r = skydemo.route(f[0], (lat, lon))
                end = r["d"][0] if f[6] == skydemo.ARRIVAL else r["o"][0]
                self.assertEqual(end, code, "%s home: %s shows %s>%s" % (code, f[0], r["o"][0], r["d"][0]))
                self.assertNotEqual(r["o"][0], r["d"][0])

    def test_demo_squawks_are_valid_octal(self):
        for r in skydemo.rows(SFO, 0, 70):
            self.assertRegex(r[9], r"^[0-7]{4}$")


class Feeds(unittest.TestCase):
    def test_normalise_raw_readsb(self):
        payload = {"now": 1791039228123, "ac": [
            {"hex": "a1", "flight": "DAL2633 ", "t": "B738", "alt_baro": 2900, "gs": 153.3, "track": 30.58,
             "baro_rate": -768, "squawk": "6573", "category": "A3", "lat": 40.63, "lon": -73.99, "seen_pos": 0.1, "r": "N1"},
            {"hex": "a2", "alt_baro": "ground", "lat": 40.64, "lon": -73.78},
            {"hex": "a3", "flight": "NOPOS"},
            {"hex": "a4", "lat": 40.6, "lon": -73.7, "true_heading": 270.2, "geom_rate": 64},
        ]}
        rows, now = skyfeed.normalise(payload)
        self.assertEqual(now, 1791039228)                    # whole seconds: a float32 holds Unix time to 128 s only
        self.assertEqual([r[HEX] for r in rows], ["a1", "a2", "a4"])
        self.assertEqual(rows[0][CS], "DAL2633")
        self.assertEqual(rows[0][ALT], 2900)
        self.assertEqual(rows[0][4:7], (153, 30, -768))
        self.assertEqual(rows[1][ALT], 0)
        self.assertEqual(rows[2][3:7], (-1, -1, 270, 64))
        for r in rows:
            self.assertEqual(len(r), 16)

    def test_normalise_compact_and_v2(self):
        rows, now = skyfeed.normalise({"now": 1791039228, "n": 1, "a": [list(row())]})
        self.assertEqual((len(rows), now), (1, 1791039228))
        rows, now = skyfeed.normalise({"now": 1791039228.5, "aircraft": [{"hex": "b1", "lat": 1, "lon": 2}]})
        self.assertEqual((len(rows), now), (1, 1791039228))
        self.assertEqual(skyfeed.normalise({"ac": []}), ([], 0))

    def test_normalise_rejects_an_answer_without_an_aircraft_list(self):
        for bad in ({}, {"message": "Hello undefined!"}, [], None, "text"):
            with self.assertRaises(ValueError):
                skyfeed.normalise(bad)

    def test_normalise_keeps_pressure_altitude_below_sea_level_airborne(self):
        alts = (-275, 0, -0.4, "ground", None, 2900.6)
        ac = [{"hex": "h%d" % i, "lat": 40.6, "lon": -73.8, "alt_baro": a} for i, a in enumerate(alts)]
        for i, a in enumerate(alts):
            if a is None:
                del ac[i]["alt_baro"]
        rows, _ = skyfeed.normalise({"ac": ac})
        self.assertEqual([r[ALT] for r in rows], [1, 1, 1, 0, -1, 2900])      # 0 is ground, -1 unknown

    def test_normalise_leaves_out_rows_it_cannot_trust(self):
        good = list(row("ok"))
        broken = [good[:10], [None] * 16, "abc", None, list(row("b1", lat=91.0)), list(row("b2", lat=None)),
                  list(row("b3", gs=None)), list(row("b4", sqk=None, flags="x")), list(row("b5", lat=float("nan")))]
        rows, _ = skyfeed.normalise({"now": 1791039228, "a": [good] + broken})
        self.assertEqual([r[HEX] for r in rows], ["ok"])
        rows, _ = skyfeed.normalise({"a": [list(row("far", seen=1e36)), list(row("nocs", cs=None))]})
        self.assertEqual([(r[HEX], r[SEEN], r[CS]) for r in rows], [("far", 0.0, "UAL1"), ("nocs", 0, "")])
        m = Model()
        m.set_home(SFO[0], SFO[1], "SFO")
        m.ingest(rows, 0)                                   # a clean row never crashes the model or the clock
        m.advance(1000)

    def test_normalise_ignores_a_clock_it_cannot_use(self):
        for now in (1e30, -5, "soon", None, 12345, float("nan")):
            self.assertEqual(skyfeed.normalise({"now": now, "a": []}), ([], 0))
        self.assertEqual(skyfeed.normalise({"now": 1791039228123, "a": []})[1], 1791039228)

    def test_rows_feed_the_model(self):
        m = Model()
        m.set_home(40.64, -73.78, "JFK")
        rows, _ = skyfeed.normalise({"ac": [{"hex": "a2", "alt_baro": "ground", "lat": 40.64, "lon": -73.78},
                                            {"hex": "a4", "lat": 40.6, "lon": -73.7}]})
        m.ingest(rows, 0)
        self.assertEqual(len(m.order), 2)
        self.assertEqual(m.order[0].label, "A4")            # unknown altitude still sorts ahead of ground

    def test_lookups(self):
        self.assertEqual(skydata.airline("UAL1234")[0], "UAL")
        self.assertIsNone(skydata.airline("N512SP"))
        self.assertIsNone(skydata.airline(""))
        self.assertEqual(skydata.airline("ZZZ123")[1], "")  # unknown airline still parses
        self.assertEqual(skydata.type_name("NOPE"), "NOPE")
        self.assertEqual(skydata.glyph("R44", "A7"), 2)
        self.assertEqual(skydata.glyph("B738", "A3"), 0)


class QrCodes(unittest.TestCase):
    """The QR encoder against fixed vectors: byte mode, level L, mask 7, the version picked for the length.

    The vectors come from python-qrcode 8.2 (version, level and mask given) and match nayuki's qrcodegen 1.8.0
    module for module. Each is the packed rows as hex, so the test needs no third-party package.
    """

    QR_BASE = ("https://jsmillerdev.github.io/select-sky/#K7M2QX@yourprojectrefxxxxxx.supabase.co/functions/v1/sky"
               "?apikey=EXAMPLE-KEY-012345678901234567890123456789012345678901234")
    QR_VECTORS = (
        (12, ""
         "fe2bf882aa08bab2e8ba0ae8bafae882e208feabf8008000d33bb0c8138862b028844ad8731140009308fedaf0822190ba"
         "40c0baae98ba1ca882a400fe8290"
         ),
        (20, ""
         "fe233f8082e3a080ba822e80ba4b2e80baedae8082a92080feaabf8000b08000d31c3b0078d8a080ea98b180717ff0004b"
         "b2e580481476809a169a8069718900ca0dfe0000cf8c80fedbad80822a8f00ba60fc80baf31e00ba219a8082a3a400fec9"
         "f180"
         ),
        (28, ""
         "fe233f8082e3a080ba822e80ba432e80baedae8082a92080feaabf8000b08000d30c3b0005c8a0804a88b180517ff0004a"
         "3ce58035007680be7e9a8069a78900e649fe0000db8c80fee3ad80827a8f00ba56fc00ba8f1e00ba2d9a8082a7a400fefd"
         "f180"
         ),
        (40, ""
         "fe4f93f8829bea08bafa62e8ba73a2e8ba85e2e882d39208feaaabf800cad800d32683b061b0ee48c6629ff01405a4b0ca"
         "8cde58acfe5400df08a4f821afccd0bab7741000e2c748bea4471805554b188b9a8fa0009c98b8fefeaa90821c28f0ba32"
         "4f80ba9602f0ba3614e882b0fd90fe8d6a50"
         ),
        (53, ""
         "fe7793f8829bea08ba9a62e8ba2ba2e8bab5e2e882e39208feaaabf800d2d800d35e83b074f8ee4822ca9ff080c5a4b003"
         "34de5820fe54007390a4f89077ccd0e343741065cac748b68c471834234b1887f48fa000c498b8fea2aa90820c28e0ba58"
         "4f98badc02e0ba7414e882eefd90fea36a50"
         ),
        (65, ""
         "fe491f3f80829b2f2080baf9d02e80ba73622e80ba85f5ae8082d3b22080feaaaabf8000c9740000d326a7bb0049b4e0a4"
         "800264767480980406c1803e0d9c6480a07874af80624e6fcd00b8ecf74d003ad107a880d9c0e5c600bb42a0ed80fd70d5"
         "c400bade5545001c7ac8a280da7e3234805dff0c5d80a7b245f80000d43f8e80feb6e8ad0082507e8800ba0ccefd80baee"
         "cdf980ba1a4f9d8082ab6de800fee00cb500"
         ),
        (78, ""
         "fe311f3f8082f32f2080ba89d02e80ba33622e80bab5f5ae80828bb22080feaaaabf8000d1740000d35ea7bb00c8cce0a4"
         "8086ac767480b9e406c18006a59c6480782874af8087766fcd00601cf74d00c3a107a8808d58e5c6006b02a0ed80f500d5"
         "c400bf9655450078cac8a280d3ce323480503f0c5d80937c45f80000e63f8e80fef8e8ad0082147e8980ba70cefc00baf8"
         "cdf980ba6a4f9d8082b16de800fee60cb500"
         ),
        (98, ""
         "fe495773f8829b41b208baf9e182e8ba730ab2e8ba83e37ae882d77e5a08feaaaaabf800ca452800d3279de3b0a430efca"
         "68fae0fcaea82545bc4ad837ec555a08b45c7daf08ff8ec3204805ecf54e502770463728bc44a6aab87a862e8658e5b246"
         "3a30bedd9d7b88f4f8486e68dfb8be20b88c3ca6cc8057fdcdde5818725bcb6886b62f4a4851145ce490cab25e0fa000bc"
         "8518a8fee2a83af882627428b8ba2d8ccf98bac86d81f8ba40fc10d88295b74b80fe84c4fb18"
         ),
        (106, ""
         "fe515773f882fb41b208ba91e182e8ba130ab2e8baf3e37ae882ef7e5a08feaaaaabf800c2452800d32f9de3b00408efca"
         "683a20fcaea8a985bc4ad86fbc555a0839ac7daf08cafec320481934f54e50e20046372858bca6aab856262e8658393246"
         "3a30a2fd9d7b8864c8486e683ec0be20b8283ca6cc80a675cdde5874e25bcb689a362f4a4871745ce490c6525e0fa000dc"
         "8518a8fe82a83af882027428b8ba4d8ccf90bac86d81f8ba60fc10d882f5b74b80fec4c4fb18"
         ),
        (125, ""
         "fe1727313f8082df65d0a080baa440acae80ba5f67ab2e80babe15b82e8082eb109fa080feaaaaaabf8000ca55258000d3"
         "4e9c5b3b00bcb6be8ce08017ae3221d700599c3ec90380435b695ca500605a88e9c0002f2a6b60c78011edfff591003790"
         "4485d10019f8d10477808a0c0aaac28054b477af5d80a7a321c0e600f01420e4e080c2a25625bb00a927b74a0300d2a4c7"
         "4c64005dc876c1c000ef78eb60a78015365e7fad00e2deea8dc080714c35ec778086980e024380288aed27f4809e6610f1"
         "fb0000c8f8cb8e80fea83264ad00822326d08f00ba7068dcf800ba90e8ee3800ba36a7a59d8082f45745a900fe80d485f5"
         "00"
         ),
        (134, ""
         "fe5b27313f8082bf65d0a080bada40acae80ba29e7ab2e80bab515b82e8082fb109fa080feaaaaaabf8000ba55258000d3"
         "6e9c5b3b00a84abe8ce080b6263221d70024963ec90380826f695ca50018d288e9c000eb726b60c780b89dfff591009300"
         "4485d1003038d10477803f2a0aaac2800c1277af5d808ae521c0e600f9c620e4e080574a5625bb008d6fb74a03009be4c7"
         "4c6400a1a876c1c000daf8eb60a7806d545e7fad000b92ea8dc08035d435ec778086800e0243802922ed27f50093b610f1"
         "fb80008cf8cb8e80fe8e3264ad00822526d08f00ba5668dcf800bac2e8ee3980ba7ea7a59c0082e45745a900fea0d485f5"
         "00"
         ),
        (142, ""
         "fe3ec93b4bf882c28e379208baf0b3e212e8ba5c9b101ae8ba8d0ff6fae88289589c4208feaaaaaaabf800eb28e2b000d3"
         "56fff903b0350cbec84028e788a4cd3dc86914f9e271981e4779bad59854ceb50924c84750cefec2706881c55daf8826df"
         "2614a358f56363ad12e006b3f4a908d814c7c39dc7003fe52fdb7fd0e8ba38c848d88ab00a8aeac8989dd8cd08902f9caf"
         "dedfd064503808b298d6ac62f41cd05d70e453aa10b693f1d6e9d091502a64163046daa756060885d55352c3500218eeef"
         "7950b1a92a100a180b47f9f0e7e878bf59795d509b876fcbef9000c2f88928a8fef6fafeda90825798a888c8ba19bfb68f"
         "98ba8774ed99f8ba1a6cc81b808295fedaec00feb5319f2350"
         ),
        (150, ""
         "fe2cc93b4bf882ca0e379208bae9b3e212e8ba6c9b101ae8ba850ff6fae882ad589c4208feaaaaaaabf800c128e2b000d3"
         "397ff903b02c0b3ec8402842a8a4cd3dc8888479e271981baf79bad59868d6b50924c87602cefec2700ce9c55daf88ba0f"
         "a614a358984163ad12e0fe03f4a908d814fec39dc700df952fdb7fd0f8fa38c848d80a860a8aeac828ffd8cd08905fbb2f"
         "dedfd02d77b808b298e3ace2f41cd028106453aa10ab13f1d6e9d0ad302a6416309b5aa7560608ccd55352c3507ad96eef"
         "7950a40d2a100a180b07f9f0e7e879bf59795d509a876fcbef9800e2f88928a8fef6fafeda90821798a888c8ba19bfb68f"
         "98ba8774ed99e8ba1a6cc81b8082b5fedaec00fef5319f2350"
         ),
    )

    def test_matrices_match_the_reference_module_for_module(self):
        for length, want in self.QR_VECTORS:
            with self.subTest(length=length):
                size, rows = skyqr.matrix(self.QR_BASE[:length])
                self.assertEqual(b"".join(rows).hex(), want)
                self.assertEqual(len(rows), size)

    def test_the_version_follows_the_length(self):
        # Level L holds 17, 32, 53, 78, 106, 134 and 154 bytes in versions 1 to 7.
        for version, top in enumerate((17, 32, 53, 78, 106, 134, 154), 1):
            self.assertEqual(skyqr.matrix("a" * top)[0], 4 * version + 17)
            if version < 7:
                self.assertEqual(skyqr.matrix("a" * (top + 1))[0], 4 * version + 21)
        with self.assertRaises(ValueError):
            skyqr.matrix("a" * 155)

    def test_multibyte_text_counts_bytes(self):
        self.assertEqual(skyqr.matrix("\u00e9" * 17)[0], 29)      # 34 bytes of UTF-8: version 3

    def test_the_locate_text_fits_a_small_code(self):
        text = config.LOCATE_PAGE + "#K7M2QX@yourprojectrefxxxxxx.supabase.co/functions/v1/sky"
        self.assertEqual(text, self.QR_BASE[:len(text)])
        self.assertEqual(skyqr.matrix(text)[0], 37)                # version 5

    def test_rows_are_packed_bits_with_a_finder_in_three_corners(self):
        size, rows = skyqr.matrix("hello")
        self.assertEqual((size, {len(r) for r in rows}), (21, {3}))
        dark = lambda x, y: rows[y][x >> 3] >> (7 - (x & 7)) & 1
        ring = [(x, y) for x in range(7) for y in range(7) if max(abs(x - 3), abs(y - 3)) == 3]
        for ox, oy in ((0, 0), (size - 7, 0), (0, size - 7)):
            self.assertTrue(all(dark(ox + x, oy + y) for x, y in ring))
            self.assertFalse(dark(ox + 1, oy + 1))
            self.assertTrue(dark(ox + 3, oy + 3))
        self.assertTrue(dark(8, size - 8))                          # the one fixed dark module


def payload(*rows, now=1791039228):
    return {"now": now, "n": len(rows), "a": [list(r) for r in rows]}


class Radio:
    """network.WLAN(STA_IF) on the harness clock: up join_ms after the first connect(), never when join_ms is None."""

    def __init__(self, clock, join_ms=None, up=False):
        self.clock, self.join_ms = clock, join_ms
        self.on, self.asks = up, [-10 ** 9] if up else []
        if up:
            self.join_ms = 0

    def active(self, flag=None):
        if flag is None:
            return self.on
        self.on = bool(flag)

    def connect(self, ssid, password):
        self.asks.append(self.clock())

    def isconnected(self):
        return bool(self.asks) and self.join_ms is not None and self.clock() >= self.asks[0] + self.join_ms


class FeedHarness(unittest.TestCase):
    """Drive skyfeed.Feed on a virtual clock, with the radio and the network stubbed."""

    PROXY = "https://abc.supabase.co/functions/v1/sky"
    GEO = {"success": True, "latitude": 40.64, "longitude": -73.78, "city": "Testville", "timezone": {"offset": -14400}}

    def build(self, proxy=None, on_badge=False, home=(37.6213, -122.379, "SFO"), settings=None, ssid="x", join_ms=None):
        s = {"range": 25, "ground": False, "home": "", "track": "", "metric": False}
        s.update(settings or {})
        self.t = 0
        self.urls = []                                       # every request, in order
        self.radio = Radio(lambda: self.t, join_ms, up=join_ms == 0)
        network = SimpleNamespace(STA_IF=0, WLAN=lambda i: self.radio)
        patches = [mock.patch.object(config, "PROXY_URL", self.PROXY if proxy is None else proxy),
                   mock.patch.object(config, "HOME", home), mock.patch.object(skyfeed, "ON_BADGE", on_badge),
                   mock.patch.object(skyfeed, "requests", object()),
                   mock.patch.object(skyfeed, "secrets", SimpleNamespace(WIFI_SSID=ssid, WIFI_PASSWORD="y")),
                   mock.patch.object(time, "ticks_ms", lambda: self.t),
                   mock.patch.dict(sys.modules, {"network": network})]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.model = Model()
        self.model.range_nm = s["range"]
        self.settings = s
        self.feed = skyfeed.Feed(self.model, s)
        self.seen = set()                                    # every status the feed showed
        return self.feed

    def serve(self, answers):
        """Stub get_json: an answer is picked by a substring of the URL; a callable may raise."""
        def get_json(url):
            self.urls.append(url)
            if skyfeed.ON_BADGE and not self.radio.isconnected():
                raise AssertionError("a request went out before Wi-Fi was up: " + url)
            for key, answer in answers.items():
                if key in url:
                    return answer(url) if callable(answer) else answer
            raise OSError("nothing answers " + url)
        p = mock.patch.object(skyfeed, "get_json", get_json)
        p.start()
        self.addCleanup(p.stop)

    def pump(self, until_ms, step=16):
        while self.t < until_ms:
            self.feed.tick(self.t)
            self.model.advance(self.t)
            self.seen.add(self.feed.status)
            self.t += step

    def hosts(self):
        return [u.split("/")[2] for u in self.urls]


class RouteLegs(unittest.TestCase):
    SFO = ("SFO", "San Francisco", 37.619, -122.375)
    SNA = ("SNA", "Santa Ana", 33.6757, -117.868)
    DEN = ("DEN", "Denver", 39.8561, -104.6737)

    def aircraft(self, lat, lon, trk):
        return SimpleNamespace(lat=lat, lon=lon, trk=trk)

    def test_out_and_back_route_shows_the_leg_being_flown(self):
        ports = [self.SFO, self.SNA, self.SFO]
        leaving = skyfeed._leg(ports, self.aircraft(37.3, -122.0, 140))     # climbing out of SFO, south-east
        self.assertEqual((leaving[0][0], leaving[1][0]), ("SFO", "SNA"))
        returning = skyfeed._leg(ports, self.aircraft(34.2, -118.6, 315))   # north-west out of Santa Ana
        self.assertEqual((returning[0][0], returning[1][0]), ("SNA", "SFO"))

    def test_multi_stop_route_picks_the_nearest_leg(self):
        ports = [self.SNA, self.SFO, self.DEN]
        o, d = skyfeed._leg(ports, self.aircraft(39.0, -112.0, 80))          # over Utah, eastbound
        self.assertEqual((o[0], d[0]), ("SFO", "DEN"))

    def test_two_airports_and_unknown_track(self):
        o, d = skyfeed._leg([self.SFO, self.DEN], self.aircraft(38.5, -115.0, -1))
        self.assertEqual((o[0], d[0]), ("SFO", "DEN"))


class FeedPacing(FeedHarness):
    def test_callsign_lookup_keeps_clear_of_polls(self):
        """The relay sheds a second request inside a second, so the lookup must not chase a poll."""
        self.build(settings={"track": "BAW285"})
        self.model.set_track("BAW285")
        calls = []

        def relay(url):
            if calls and self.t - calls[-1] < 1000:
                raise skyfeed.HttpError(503)
            calls.append(self.t)
            if "cs=" in url:
                return {"now": 1791039228, "a": [list(row("far", cs="BAW285", lat=51.4, lon=-0.4))]}
            return {"now": 1791039228, "a": [list(row("a"))]}

        self.serve({"functions/v1/sky": relay})
        self.pump(20000)
        self.assertIsNotNone(self.model.tracked)
        self.assertEqual(self.model.tracked.cs, "BAW285")
        self.assertEqual(self.feed.status, "LIVE")
        self.assertTrue(all(b - a >= 2500 for a, b in zip(calls, calls[1:])), calls)


class FeedStartup(FeedHarness):
    def test_browser_without_a_proxy_flies_the_demo_and_still_finds_home(self):
        f = self.build(proxy="", home=None)
        self.serve({"ipwho": self.GEO})
        self.pump(30000)
        self.assertEqual((f.status, f.source, self.model.home_label, f.tz_s), ("DEMO", "demo", "TESTVILLE", -14400))
        self.assertEqual(self.hosts(), ["ipwho.is"])        # nothing else is ever asked
        self.assertGreater(len(self.model.order), 2)

    def test_browser_with_a_working_proxy_goes_live(self):
        f = self.build()
        self.serve({"supabase": payload(row("real1", lat=37.65), row("real2", lat=37.7))})
        self.pump(3000)
        self.assertEqual((f.status, f.source), ("LIVE", "edge fn"))
        self.assertEqual(sorted(self.model.rows), ["real1", "real2"])
        self.assertNotIn("DEMO", self.seen)
        self.assertEqual(f.clock(), 1791039228 + (self.t - f.rows_ms) // 1000)    # whole seconds, from the payload
        self.pump(self.t + 13300)
        self.assertEqual(f.clock(), 1791039228 + (self.t - f._anchor[1]) // 1000)
        self.assertIsInstance(f.clock(), int)

    def test_a_saved_home_code_this_build_no_longer_lists_falls_back_to_auto(self):
        f = self.build(home=None, settings={"home": "ZZZ"})
        self.serve({"ipwho": self.GEO})
        f._locate(0)
        self.assertEqual(self.model.home_label, "TESTVILLE")

    def test_proxy_url_may_carry_a_query_a_trailing_slash_or_a_percent(self):
        f = self.build(proxy="https://abc.supabase.co/functions/v1/sky?apikey=K")
        nearby, callsign = f._chain[0][1], f._chain[0][2]
        self.assertEqual(nearby % (37.6, -122.4, 25), "https://abc.supabase.co/functions/v1/sky?apikey=K&lat=37.6000&lon=-122.4000&r=25")
        self.assertEqual(callsign % "UAL1", "https://abc.supabase.co/functions/v1/sky?apikey=K&cs=UAL1")
        f = self.build(proxy="https://abc.supabase.co/functions/v1/sky?key=a%2Fb")
        self.assertEqual(f._chain[0][1] % (37.6, -122.4, 25), "https://abc.supabase.co/functions/v1/sky?key=a%2Fb&lat=37.6000&lon=-122.4000&r=25")
        f = self.build(proxy="https://abc.supabase.co/functions/v1/sky/")
        self.assertEqual(f._chain[0][2] % "UAL1", "https://abc.supabase.co/functions/v1/sky/?cs=UAL1")

    def test_a_badge_joining_wifi_for_20_s_makes_no_request_until_it_is_up_and_stays_live(self):
        f = self.build(on_badge=True, home=None, join_ms=20000)
        self.serve({"ipwho": self.GEO, "supabase": lambda u: payload(row("real1", lat=40.65, lon=-73.78))})
        self.pump(19900)
        self.assertEqual(self.urls, [])
        self.assertFalse(f.busy)                             # waiting needs no SYNC frame
        self.assertEqual(f.note, "Joining Wi-Fi")
        self.assertEqual(len(self.radio.asks), 1)            # asked once, not every poll
        self.pump(30000)
        self.assertEqual((f.status, f.source, self.model.home_label), ("LIVE", "edge fn", "TESTVILLE"))
        self.assertEqual(self.hosts()[:2], ["ipwho.is", "abc.supabase.co"])
        self.assertEqual(sorted(self.model.rows), ["real1"])
        self.assertNotIn("DEMO", self.seen)

    def test_a_badge_with_no_wifi_in_secrets_reaches_the_demo_and_says_why(self):
        f = self.build(on_badge=True, ssid="")
        self.serve({"supabase": payload(row("real1"))})
        self.pump(60000)
        self.assertEqual(f.status, "DEMO")
        self.assertEqual(f.note, "Demo traffic. Add Wi-Fi to secrets.py")
        self.assertEqual((self.urls, self.radio.asks), ([], []))     # never joins, never asks the firmware to

    def test_a_badge_whose_wifi_never_comes_up_gives_up_after_the_join_window_and_asks_again(self):
        f = self.build(on_badge=True)
        self.serve({"supabase": payload(row("real1"))})
        self.pump(skyfeed.JOIN_MS - 100)
        self.assertNotEqual(f.status, "DEMO")
        self.assertEqual(self.urls, [])
        self.pump(skyfeed.JOIN_MS + 40000)
        self.assertEqual(f.status, "DEMO")
        self.pump(200000)                                    # the demo checks the live sources again after a minute
        self.assertGreater(len(self.radio.asks), 2)
        self.assertTrue(all(b - a >= skyfeed.JOIN_RETRY_MS for a, b in zip(self.radio.asks, self.radio.asks[1:])))

    def test_a_dropped_link_waits_for_the_join_before_it_counts_as_failures(self):
        f = self.build(on_badge=True, join_ms=0)
        self.serve({"supabase": payload(row("real1", lat=37.65))})
        self.pump(3000)
        self.assertEqual(f.status, "LIVE")
        self.radio.asks, self.radio.join_ms = [self.t + 5000], 8000     # the link drops and rejoins 8 s later
        self.radio.on = False
        self.pump(self.t + 30000)
        self.assertEqual((f.status, f.source), ("LIVE", "edge fn"))
        self.assertNotIn("DEMO", self.seen)

    def test_a_missed_ip_lookup_is_tried_again_and_then_given_up(self):
        f = self.build(home=None)
        answers = iter([skyfeed.HttpError(429), self.GEO])

        def geo(url):
            a = next(answers)
            if isinstance(a, Exception):
                raise a
            return a

        self.serve({"ipwho": geo, "supabase": payload(row("real1", lat=37.65))})
        self.pump(skyfeed.GEO_RETRY_MS + 3000)
        self.assertEqual((self.model.home_label, f.tz_s), ("TESTVILLE", -14400))
        self.assertEqual(self.hosts().count("ipwho.is"), 2)
        f = self.build(home=None)
        self.serve({"ipwho": {"success": False}, "supabase": payload(row("real1", lat=37.65))})
        self.pump(skyfeed.GEO_RETRY_MS * 6)
        self.assertEqual((self.hosts().count("ipwho.is"), self.model.home_label), (skyfeed.GEO_TRIES, "SFO"))
        self.assertEqual(f.status, "LIVE")

    def test_a_home_chosen_in_setup_cancels_a_pending_ip_lookup(self):
        f = self.build(home=None)
        self.serve({"ipwho": {"success": False}, "supabase": payload(row("real1", lat=37.65))})
        self.pump(5000)
        self.settings["home"] = "JFK"
        f.relocate()
        self.pump(skyfeed.GEO_RETRY_MS * 3)
        self.assertEqual((self.hosts().count("ipwho.is"), self.model.home_label), (1, "JFK"))

    def test_a_new_home_clears_the_old_timezone(self):
        f = self.build(home=None)
        self.serve({"ipwho": self.GEO})
        f._locate(0)
        self.assertEqual(f.tz_s, -14400)
        self.settings["home"] = "JFK"
        f.relocate()
        f._locate(0)
        self.assertEqual((self.model.home_label, f.tz_s), ("JFK", None))


class FeedExact(FeedHarness):
    """Home from the position saved in Setup: it wins over the IP lookup, which only names the city and the time zone."""

    POS = [33.4512, -112.0638]

    def exact(self, **kw):
        kw.setdefault("home", None)
        kw["settings"] = dict(kw.get("settings") or {}, home="EXACT", pos=self.POS)
        return self.build(**kw)

    def test_exact_position_wins_over_the_ip_lookup(self):
        f = self.exact()
        self.serve({"ipwho": self.GEO, "supabase": payload(row("real1", lat=33.46, lon=-112.07))})
        self.pump(3000)
        self.assertEqual(self.model.home, (33.4512, -112.0638))      # not the 40.64, -73.78 the lookup answered
        self.assertTrue(f.exact)
        self.assertEqual(self.hosts()[:2], ["ipwho.is", "abc.supabase.co"])
        self.assertIn("lat=33.4512&lon=-112.0638", self.urls[1])     # all four decimals reach the aircraft source
        self.assertEqual(f.status, "LIVE")

    def test_the_lookup_under_an_exact_position_sets_the_city_and_time_zone_only(self):
        f = self.exact()
        self.serve({"ipwho": self.GEO, "supabase": payload(row("real1", lat=33.46, lon=-112.07))})
        f._locate(0)
        self.assertEqual((self.model.home, self.model.home_label, f.tz_s), ((33.4512, -112.0638), "TESTVILLE", -14400))
        self.assertEqual(self.hosts().count("ipwho.is"), 1)
        self.pump(skyfeed.GEO_RETRY_MS * 2)
        self.assertEqual(self.hosts().count("ipwho.is"), 1)          # answered, so it is not asked again
        self.assertEqual(self.model.home, (33.4512, -112.0638))

    def test_a_failed_lookup_leaves_the_label_here_and_the_time_zone_unknown(self):
        f = self.exact()
        self.serve({"ipwho": {"success": False}, "supabase": payload(row("real1", lat=33.46, lon=-112.07))})
        self.pump(skyfeed.GEO_RETRY_MS * 6)
        self.assertEqual((self.model.home, self.model.home_label, f.tz_s), ((33.4512, -112.0638), "HERE", None))
        self.assertEqual(self.hosts().count("ipwho.is"), skyfeed.GEO_TRIES)
        self.assertEqual(f.status, "LIVE")

    def test_a_late_ip_answer_names_the_city_but_never_moves_an_exact_home(self):
        f = self.exact()
        answers = iter([skyfeed.HttpError(429), self.GEO])

        def geo(url):
            a = next(answers)
            if isinstance(a, Exception):
                raise a
            return a

        self.serve({"ipwho": geo, "supabase": payload(row("real1", lat=33.46, lon=-112.07))})
        self.pump(skyfeed.GEO_RETRY_MS - 1000)
        self.assertEqual((self.model.home_label, f.tz_s), ("HERE", None))
        self.pump(skyfeed.GEO_RETRY_MS + 3000)
        self.assertEqual((self.model.home, self.model.home_label, f.tz_s), ((33.4512, -112.0638), "TESTVILLE", -14400))
        self.assertTrue(f.exact)

    def test_a_badge_joining_wifi_places_home_at_once_and_asks_for_the_city_when_it_is_up(self):
        f = self.exact(on_badge=True, join_ms=20000)
        self.serve({"ipwho": self.GEO, "supabase": lambda u: payload(row("real1", lat=33.46, lon=-112.07))})
        self.pump(19900)
        self.assertEqual((self.urls, self.model.home, self.model.home_label), ([], (33.4512, -112.0638), "HERE"))
        self.pump(40000)
        self.assertEqual((self.model.home, self.model.home_label, f.tz_s), ((33.4512, -112.0638), "TESTVILLE", -14400))
        self.assertEqual(self.hosts().count("ipwho.is"), 1)

    def test_config_home_wins_over_an_exact_position(self):
        f = self.exact(home=(10.0, 20.0, "PIN"))
        self.serve({"ipwho": self.GEO})
        self.pump(2000)
        self.assertEqual((self.model.home, self.model.home_label, f.exact, f.tz_s), ((10.0, 20.0), "PIN", False, None))
        self.assertNotIn("ipwho.is", self.hosts())

    def test_an_airport_pick_keeps_the_saved_position_but_does_not_use_it(self):
        f = self.build(home=None, settings={"home": "JFK", "pos": self.POS})
        self.serve({"ipwho": self.GEO})
        f._locate(0)
        self.assertEqual((self.model.home_label, f.exact, f.tz_s), ("JFK", False, None))
        self.assertEqual(self.settings["pos"], self.POS)
        self.assertEqual(self.hosts(), [])

    def test_exact_without_a_usable_position_falls_back_to_automatic(self):
        for bad in (None, [], [33.4], "x", ["a", "b"], [95.0, 0.0], [0.0, 190.0], [float("nan"), 0.0]):
            with self.subTest(pos=bad):
                f = self.build(home=None, settings={"home": "EXACT", "pos": bad})
                self.serve({"ipwho": self.GEO})
                f._locate(0)
                self.assertEqual((self.model.home, self.model.home_label, f.exact, f.tz_s), ((40.64, -73.78), "TESTVILLE", False, -14400))

    def test_settings_saved_before_the_position_existed_still_start(self):
        old = {"range": 25, "ground": False, "home": "", "track": "", "metric": False}     # no "pos" key at all
        for home in ("", "JFK", "EXACT"):
            with self.subTest(home=home):
                f = self.build(home=None, settings=dict(old, home=home))
                self.serve({"ipwho": self.GEO})
                f._locate(0)
                self.assertEqual((self.model.home_label, f.exact), ("JFK" if home == "JFK" else "TESTVILLE", False))
        tree = ast.parse((ROOT / "select_sky" / "__init__.py").read_text())
        defaults = next(n.value for n in tree.body if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "SETTINGS")
        self.assertIsNone(ast.literal_eval(defaults)["pos"])         # State.load merges a save over these defaults

    def test_an_ip_lookup_armed_before_a_setup_pick_cannot_move_the_picked_home(self):
        f = self.build(home=None)
        answers = iter([skyfeed.HttpError(429)])

        def geo(url):
            a = next(answers, self.GEO)
            if isinstance(a, Exception):
                raise a
            return a

        self.serve({"ipwho": geo, "supabase": payload(row("real1", lat=37.65))})
        while f._job != f._locate_ip:                                # the retry is armed: it runs on the next frame
            self.assertLess(self.t, skyfeed.GEO_RETRY_MS * 2)
            self.pump(self.t + 16)
        self.settings["home"] = "JFK"                                # a pick applies between the two frames
        f.relocate()
        self.pump(self.t + 16)
        self.assertEqual((self.model.home_label, self.hosts().count("ipwho.is")), ("SFO", 1))     # the stale job did nothing
        self.pump(self.t + 3000)
        self.assertEqual((self.model.home_label, f.tz_s, self.hosts().count("ipwho.is")), ("JFK", None, 1))


class FeedLocate(FeedHarness):
    """The locate job: ask the relay for the position a phone sent under a code, beside the aircraft polls."""

    CODE = "K7M2QX"
    WHERE = {"lat": 33.4512, "lon": -112.0638, "acc": 9}

    def waiting(self, url):
        raise skyfeed.HttpError(404)

    def relay(self, here, **kw):
        """Build a feed on a relay whose answer to a locate ask is here(url), and which also serves aircraft."""
        f = self.build(**kw)
        self.asks, self.polls = [], []                       # virtual time of each locate ask and each aircraft poll

        def sky(url):
            if "here=" in url:
                self.asks.append(self.t)
                return here(url)
            self.polls.append(self.t)
            return payload(row("a"))

        self.serve({"supabase": sky})
        return f

    def test_waiting_answers_are_normal_and_the_aircraft_polls_go_on(self):
        f = self.relay(self.waiting)
        self.pump(1000)
        f.locate(self.CODE, self.t)
        self.pump(self.t + 40000)
        self.assertTrue(14 <= len(self.asks) <= 16, self.asks)
        self.assertTrue(all(b - a >= skyfeed.LOCATE_EVERY_MS for a, b in zip(self.asks, self.asks[1:])), self.asks)
        self.assertTrue(all(b - a >= 12000 for a, b in zip(self.polls, self.polls[1:])), self.polls)
        self.assertGreaterEqual(len(self.polls), 4)
        self.assertEqual(len(set(self.asks + self.polls)), len(self.asks + self.polls))    # never two in one frame
        self.assertEqual((f.status, f.source, f._fails, f.note), ("LIVE", "edge fn", 0, "1 rows from edge fn"))
        self.assertIn(self.PROXY + "?here=" + self.CODE, self.urls)
        self.assertIsNone(f.take_pos())
        self.assertGreater(f.locate_left(self.t), 0)

    def test_a_position_is_delivered_once_and_the_asking_stops(self):
        state = {"n": 0}

        def here(url):
            state["n"] += 1
            if state["n"] < 3:
                raise skyfeed.HttpError(404)
            return self.WHERE

        f = self.relay(here)
        f.locate(self.CODE, 0)
        self.pump(20000)
        self.assertEqual(len(self.asks), 3)
        self.assertEqual(f.take_pos(), (33.4512, -112.0638, 9.0))
        self.assertIsNone(f.take_pos())
        self.assertEqual(f.locate_left(self.t), 0)
        self.pump(self.t + 20000)
        self.assertEqual(len(self.asks), 3)
        self.assertEqual((f.status, f._fails), ("LIVE", 0))

    def test_what_arrives_is_checked_before_it_is_handed_over(self):
        good = {"lat": -33.9, "lon": 151.2, "acc": None}
        for answer, want in ((good, (-33.9, 151.2, None)), ({"lat": 95, "lon": 0}, None), ({"lat": 0, "lon": -181}, None),
                             ({"lat": "x", "lon": 0}, None), ({"lat": float("nan"), "lon": 0}, None),
                             ({"error": "waiting"}, None), ([1, 2], None)):
            with self.subTest(answer=answer):
                f = self.relay(lambda url: answer)
                f.locate(self.CODE, 0)
                self.pump(3000)
                self.assertEqual(f.take_pos(), want)
                self.assertEqual(bool(f.code), want is None)  # a usable answer ends the asking

    def test_the_code_expires_after_five_minutes(self):
        self.assertEqual(skyfeed.LOCATE_LIFE_MS, 5 * 60 * 1000)
        f = self.relay(self.waiting)
        f.locate(self.CODE, 0)
        self.pump(10000)
        self.assertEqual(f.locate_left(self.t), skyfeed.LOCATE_LIFE_MS - self.t)
        self.pump(skyfeed.LOCATE_LIFE_MS + 5000)
        self.assertEqual(f.locate_left(self.t), 0)
        self.assertLess(max(self.asks), skyfeed.LOCATE_LIFE_MS)
        asked, polled = len(self.asks), len(self.polls)
        self.assertGreater(asked, 100)
        self.pump(self.t + 40000)
        self.assertEqual(len(self.asks), asked)              # nothing more is asked ...
        self.assertGreater(len(self.polls), polled + 2)      # ... and the polls never noticed
        self.assertEqual((f.status, f.source, f._fails), ("LIVE", "edge fn", 0))
        f.locate("NEWCOD", self.t)                           # a fresh code asks again
        self.pump(self.t + 6000)
        self.assertEqual(len(self.asks), asked + 2)

    def test_no_request_without_a_relay(self):
        f = self.build(proxy="")
        self.serve({})
        f.locate(self.CODE, 0)
        self.pump(20000)
        self.assertEqual(self.urls, [])

    def test_the_code_joins_the_relay_url_with_a_question_mark_or_an_ampersand(self):
        for proxy, want in ((self.PROXY, self.PROXY + "?here=K7M2QX"),
                            (self.PROXY + "?apikey=k", self.PROXY + "?apikey=k&here=K7M2QX"),
                            (self.PROXY + "?a=%41%20b", self.PROXY + "?a=%41%20b&here=K7M2QX")):
            with self.subTest(proxy=proxy):
                f = self.relay(self.waiting, proxy=proxy)
                f.locate(self.CODE, 0)
                self.pump(4000)
                self.assertIn(want, self.urls)

    def test_cancelling_stops_the_asking_even_for_a_job_already_armed(self):
        f = self.relay(self.waiting)
        f.locate(self.CODE, 0)
        self.pump(8000)
        asked = len(self.asks)
        f.locate_stop()
        self.pump(self.t + 20000)
        self.assertEqual((len(self.asks), f.locate_left(self.t)), (asked, 0))
        f.locate(self.CODE, self.t)
        while f._job != f._ask_phone:                        # armed: it runs on the next frame
            self.assertLess(self.t, 60000)
            self.pump(self.t + 16)
        f.locate_stop()
        self.pump(self.t + 16)
        self.assertEqual(len(self.asks), asked)

    def test_a_slow_failed_ask_is_not_repeated_at_once_and_costs_the_source_nothing(self):
        f = self.build(on_badge=True, join_ms=0)
        starts, ends = [], []

        def get_json(url):
            if "here=" not in url:
                return payload(row("a"))
            starts.append(self.t)
            self.t += 8000                                   # a timeout blocks the frame
            ends.append(self.t)
            raise OSError("timed out")

        with mock.patch.object(skyfeed, "get_json", get_json):
            f.locate(self.CODE, 0)
            while len(starts) < 3:
                f.tick(self.t)
                self.t += 16
        self.assertTrue(all(b - a >= skyfeed.LOCATE_EVERY_MS for a, b in zip(ends, starts[1:])), (starts, ends))
        self.assertEqual((f.status, f._fails), ("LIVE", 0))

    def test_nothing_is_asked_while_the_wifi_is_joining(self):
        f = self.relay(self.waiting, on_badge=True, join_ms=20000)      # serve() fails on a request before the radio is up
        f.locate(self.CODE, 0)
        self.pump(19000)
        self.assertEqual(self.urls, [])
        self.pump(30000)
        self.assertGreater(len(self.asks), 0)


class FeedStateMachine(FeedHarness):
    def test_proxy_500_twice_flies_the_demo_and_checks_again_after_a_minute(self):
        f = self.build()
        state = {"up": False}

        def sky(url):
            if state["up"]:
                return payload(row("real1", lat=37.65))
            raise ValueError("HTTP 500")

        self.serve({"supabase": sky})
        self.pump(2900)
        self.assertEqual(len(self.urls), 1)                  # the second try waits RETRY_MS
        self.assertEqual(f.status, "STALE" if f.rows_ms is not None else "WAIT")
        self.pump(3500)
        self.assertEqual(len(self.urls), 2)
        self.assertEqual((f.status, f.source, f.note), ("DEMO", "demo", "Demo traffic. edge fn: HTTP 500"))
        self.pump(60000)
        self.assertEqual(len(self.urls), 2)                  # the demo asks nothing for a minute
        self.pump(66000)
        self.assertEqual(len(self.urls), 3)                  # then one request tries the source again
        self.assertEqual(f.status, "DEMO")
        state["up"] = True
        self.pump(self.t + skyfeed.RETRY_LIVE_MS + 3000)
        self.assertEqual((f.status, f.source), ("LIVE", "edge fn"))

    def test_live_to_demo_leaves_no_live_aircraft_beside_the_demo_ones(self):
        state = {"up": True}

        def sky(url):
            if state["up"]:
                return payload(row("real1", cs="UAL1", lat=37.65), row("real2", cs="DAL2", lat=37.7))
            raise OSError("down")

        f = self.build()
        self.serve({"supabase": sky})
        self.pump(3000)
        self.assertEqual(f.status, "LIVE")
        state["up"] = False
        self.pump(30000)
        self.assertEqual(f.status, "DEMO")
        self.assertEqual([h for h in self.model.rows if not h.startswith("d")], [])
        self.assertEqual(f.note, "Demo traffic. edge fn: no answer")      # not the browser's own error text

    def test_demo_to_live_leaves_no_demo_aircraft_beside_the_live_ones_or_in_the_records(self):
        state = {"up": False}

        def sky(url):
            if state["up"]:
                return payload(row("real1", cs="UAL1", lat=37.65))
            raise OSError("down")

        f = self.build()
        self.serve({"supabase": sky})
        self.pump(40000)
        self.assertEqual(f.status, "DEMO")
        self.assertGreater(self.model.stats["seen"], 2)      # until a real answer arrives the demo fills the records
        state["up"] = True
        self.pump(skyfeed.RETRY_LIVE_MS + 40000)
        self.assertEqual(f.status, "LIVE")
        self.assertEqual(list(self.model.rows), ["real1"])
        self.assertEqual((self.model.stats["seen"], self.model.stats["peak"], self.model.airlines), (1, 1, {"UAL": 1}))
        state["up"] = False
        self.pump(self.t + 40000)
        self.assertEqual(f.status, "DEMO")
        self.assertEqual((self.model.stats["seen"], self.model.stats["peak"]), (1, 1))     # demo traffic is not recorded now

    def test_one_failed_retry_costs_one_request_per_source(self):
        f = self.build(on_badge=True, join_ms=0)             # edge fn, adsb.fi and adsb.lol
        self.serve({})
        while f._live is not None or self.t < 100:           # reach the demo
            self.pump(self.t + 16)
        while f._live is None:                               # wait for the minute to pass
            self.pump(self.t + 16)
        del self.urls[:]
        while f._live is not None:                           # and for the retry to give up again
            self.pump(self.t + 16)
        self.assertEqual(self.hosts(), ["abc.supabase.co", "opendata.adsb.fi", "api.adsb.lol"])

    def test_back_off_counts_from_the_end_of_a_slow_failed_request(self):
        # A request that times out blocks for TIMEOUT_S inside one frame; badge.ticks is latched at its start.
        f = self.build(on_badge=True, join_ms=0)
        starts, ends = [], []

        def get_json(url):
            starts.append(self.t)
            self.t += 8000
            ends.append(self.t)
            raise OSError("timed out")

        with mock.patch.object(skyfeed, "get_json", get_json):
            while len(starts) < 2:
                f.tick(self.t)
                self.t += 16
        self.assertGreaterEqual(starts[1] - ends[0], skyfeed.RETRY_MS)

    def test_transient_route_failure_is_asked_again_but_not_for_ever(self):
        f = self.build()
        self.model.set_home(*SFO, "SFO")
        self.model.ingest([row("a", cs="UAL1")], 0)
        calls = []

        def fail(url):
            calls.append(self.t)
            raise OSError("timed out")

        self.serve({"vrs-standing": fail})
        f._locate(0)
        f._next_poll = 10 ** 9                               # leave the polling out of it
        f._route(0)
        self.assertIsNotNone(f._route_target())              # a timeout is not "no route on file"
        self.assertIsNone(f._due(1000))                      # but it waits ROUTE_RETRY_MS before asking again
        self.assertEqual(f._due(skyfeed.ROUTE_RETRY_MS), f._route)
        for t in (skyfeed.ROUTE_RETRY_MS, 2 * skyfeed.ROUTE_RETRY_MS):
            f._route(t)
        self.assertEqual(len(calls), 3)
        self.assertIsNone(f._route_target())                 # three misses in a row end the asking
        self.model.routes.clear()
        self.serve({"vrs-standing": lambda u: (_ for _ in ()).throw(skyfeed.HttpError(404))})
        f._route(0)                                          # a real 404 means "no such route" at once
        self.assertEqual(self.model.routes, {"UAL1": False})

    def test_a_found_route_is_kept_when_the_memo_is_full(self):
        f = self.build()
        self.model.set_home(*SFO, "SFO")
        self.model.ingest([row("a", cs="UAL1")], 0)
        for i in range(60):
            self.model.routes["X%d" % i] = False
        ports = {"_airports": [{"iata": "SFO", "lat": 37.6, "lon": -122.4}, {"iata": "JFK", "lat": 40.6, "lon": -73.8}]}
        self.serve({"vrs-standing": ports})
        f._route(0)
        self.assertEqual(self.model.routes["UAL1"]["d"][0], "JFK")
        self.assertIsNone(f._route_target())

    def test_polling_keeps_its_rhythm_far_beyond_the_32_bit_clock(self):
        # App.frame unwraps badge.ticks, so the feed sees a clock that only grows; 0 still means "due now".
        f = self.build()
        polls = []
        self.serve({"supabase": lambda u: polls.append(self.t) or payload(row("a"))})
        self.pump(3000)
        self.t = 2 ** 33 + 10000
        self.pump(self.t + 40000)
        self.assertEqual(len(polls) - 1, 4)                  # one per POLL_S, 12 s apart
        del polls[:]
        f.refresh()
        self.pump(self.t + 100)
        self.assertEqual(len(polls), 1)
        self.assertEqual(f.age_s(self.t), (self.t - f.rows_ms) / 1000.0)


if __name__ == "__main__":
    unittest.main(verbosity=1)
