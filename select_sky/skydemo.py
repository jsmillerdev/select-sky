"""Demo traffic: an endlessly moving sky for when no live feed is reachable.

Each aircraft flies a straight chord across a 70 nm circle around home and
re-enters on the far side, so the radar, the board and the records all have
something honest to show without a network.
"""

import math

import skydata
import skygeo

REACH_NM = 70.0
LEVEL, ARRIVAL, DEPARTURE = 0, 1, 2

# callsign, type, category, registration, altitude ft, speed kt, profile, flags,
# origin, destination, heading, closest approach nm, start along the chord nm
FLEET = (
    ("UAL1892", "B739", "A3", "N68891", 34000, 452, LEVEL, 0, "SFO", "EWR", 285, 1.5, -6),
    ("SWA2415", "B38M", "A3", "N8730Q", 9000, 262, ARRIVAL, 0, "DEN", "SFO", 105, -4, 12),
    ("DAL402", "A321", "A3", "N301DV", 11000, 296, DEPARTURE, 0, "SFO", "JFK", 320, 7, -20),
    ("AAL1267", "B738", "A3", "N921NN", 36000, 461, LEVEL, 0, "LAX", "ORD", 140, -9, 30),
    ("ASA331", "B39M", "A3", "N915AK", 8000, 250, ARRIVAL, 0, "SEA", "SFO", 60, 12, -45),
    ("JBU615", "A320", "A3", "N651JB", 33000, 440, LEVEL, 0, "JFK", "SFO", 240, -15, 8),
    ("FDX1422", "B763", "A5", "N103FE", 31000, 470, LEVEL, 0, "PHX", "SEA", 195, 3, -2),
    ("UPS2957", "B752", "A4", "N472UP", 12000, 310, DEPARTURE, 0, "SFO", "DEN", 15, 18, 55),
    ("SKW5421", "E75L", "A3", "N205SY", 7000, 240, ARRIVAL, 0, "PHX", "SFO", 350, -22, -30),
    ("N512SP", "C172", "A1", "N512SP", 3500, 108, LEVEL, 0, "", "", 80, 6, 18),
    ("N88HP", "R44", "A7", "N88HP", 900, 85, LEVEL, 0, "", "", 262, -2.5, -60),
    ("BAW285", "A388", "A5", "G-XLEK", 38000, 488, LEVEL, 0, "LHR", "SFO", 128, 30, 25),
    ("JAL2", "B77W", "A5", "JA742J", 39000, 495, LEVEL, 0, "NRT", "SFO", 300, -35, 40),
    ("AFR84", "B77W", "A5", "F-GSQM", 37000, 480, LEVEL, 0, "CDG", "SFO", 170, 10, -12),
    ("UAE225", "A388", "A5", "A6-EVF", 40000, 492, LEVEL, 0, "DXB", "SFO", 45, -6, -38),
    ("EJA532", "C68A", "A2", "N532QS", 41000, 430, LEVEL, 0, "", "", 225, 14, 48),
    ("RCH871", "C17", "A5", "08-8198", 28000, 420, LEVEL, 1, "", "", 98, 0.8, 3),
    ("KAL23", "B748", "A5", "HL7633", 35000, 485, LEVEL, 0, "ICN", "SFO", 330, 21, -52),
    # one of each class the Show filter sorts by
    ("DAL158", "A359", "A5", "N501DN", 39000, 488, LEVEL, 0, "ICN", "SFO", 295, -12, 18),
    ("N4587P", "P28A", "A1", "N4587P", 3000, 110, LEVEL, 0, "", "", 340, 4, -25),
    ("FDX9114", "AT72", "A2", "N802FX", 8000, 230, LEVEL, 0, "", "", 165, 5, -25),
    ("ARMY31", "H60", "A7", "07-20031", 1500, 120, LEVEL, 1, "", "", 70, 3, -40),
)


def rows(home, t_s, radius_nm, alert=False):
    """Feed rows for the fleet t_s seconds into the session, within radius_nm of home.

    The aircraft that carries the test squawk while alert is set is always included.
    """
    lat0, lon0 = home
    lon_scale = 60.0 * skygeo.lon_scale(lat0)
    out = []
    for i, (cs, typ, cat, reg, cruise, gs, profile, flags, _o, _d, hdg, near, start) in enumerate(FLEET):
        half = math.sqrt(REACH_NM * REACH_NM - near * near)
        s = (start + half + gs * t_s / 3600.0) % (2 * half) - half
        u = (s + half) / (2 * half)
        h = math.radians(hdg)
        east = near * math.cos(h) + s * math.sin(h)
        north = -near * math.sin(h) + s * math.cos(h)
        dist = math.sqrt(east * east + north * north)
        if dist > radius_nm and not (alert and i == 1):
            continue
        alt, vr = cruise, 0
        if profile == ARRIVAL:
            alt, vr = int(cruise + 6000 * (1 - u) * 2 - 6000), -900
        elif profile == DEPARTURE:
            alt, vr = int(cruise - 8000 + 16000 * u), 1800
        sqk = "7700" if alert and i == 1 else "%04o" % ((0o1200 + i * 0o421) & 0o7777)
        out.append(("d%05x" % (0xA1B00 + i * 577), cs, typ, max(600, alt), gs, hdg, vr,
                    lat0 + north / 60.0, lon0 + east / lon_scale, sqk, flags,
                    dist, math.degrees(math.atan2(east, north)) % 360, cat, reg, 0))
    return out


def route(callsign, home):
    """Bundled route for a demo flight, or False for one that files none.

    Arrivals land at, and departures leave from, the listed airport nearest
    home, so the route agrees with what the aircraft is seen doing.
    """
    for f in FLEET:
        if f[0] == callsign and f[8]:
            o, d = f[8], f[9]
            local = min(skydata.AIRPORTS, key=lambda k: skygeo.dist_brg(home[0], home[1], skydata.AIRPORTS[k][1], skydata.AIRPORTS[k][2])[0])
            if f[6] == ARRIVAL and d != local:
                o = d if o == local else o      # an arrival from here is flown the other way round
                d = local
            elif f[6] == DEPARTURE and o != local:
                d = o if d == local else d
                o = local
            return {"o": _airport(o), "d": _airport(d)}
    return False


def _airport(code):
    city, lat, lon = skydata.AIRPORTS[code]
    return (code, city, lat, lon)
