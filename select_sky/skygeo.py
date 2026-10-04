"""Flat-earth navigation maths: good to a few percent inside a few hundred miles."""

import math

FT_PER_NM = 6076.12
EARTH_NM = 3440.0
FLAT_NM = 150.0       # beyond this the flat-earth form is too wrong to show
POINTS = ("N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
          "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW")


def lon_scale(lat):
    """Share of a degree of longitude that is as wide as a degree of latitude, floored near the poles."""
    return max(0.05, math.cos(math.radians(lat)))


def offset_nm(lat0, lon0, lat, lon):
    """East and north distance in nautical miles from (lat0, lon0)."""
    dlon = lon - lon0
    if dlon > 180.0:                    # the short way round the antimeridian
        dlon -= 360.0
    elif dlon < -180.0:
        dlon += 360.0
    return dlon * 60.0 * lon_scale((lat + lat0) * 0.5), (lat - lat0) * 60.0


def dist_brg(lat0, lon0, lat, lon, off=None):
    """Distance in nautical miles and true bearing in degrees. off is offset_nm's answer, when already measured."""
    dx, dy = off or offset_nm(lat0, lon0, lat, lon)
    d = math.sqrt(dx * dx + dy * dy)
    if d <= FLAT_NM:
        return d, math.degrees(math.atan2(dx, dy)) % 360
    # A flight followed from far away needs the great circle and its initial bearing.
    p0, p1, dl = math.radians(lat0), math.radians(lat), math.radians(lon - lon0)
    y = math.sin(dl) * math.cos(p1)
    x = math.cos(p0) * math.sin(p1) - math.sin(p0) * math.cos(p1) * math.cos(dl)
    return great_circle_nm(lat0, lon0, lat, lon), math.degrees(math.atan2(y, x)) % 360


def advance(lat, lon, track, nm):
    """The position after flying nm nautical miles along a track."""
    r = math.radians(track)
    return lat + nm * math.cos(r) / 60.0, lon + nm * math.sin(r) / (60.0 * lon_scale(lat))


def great_circle_nm(lat1, lon1, lat2, lon2):
    """Haversine distance, for routes too long for the flat-earth form."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * EARTH_NM * math.asin(min(1.0, math.sqrt(a)))


def elevation(alt_ft, dist_nm):
    """Angle above the horizon in degrees, allowing for the curve of the earth: it
    turns negative once the aircraft is over the horizon. 0 without a height."""
    if alt_ft <= 0:
        return 0.0
    r = EARTH_NM + alt_ft / FT_PER_NM
    t = dist_nm / EARTH_NM
    return math.degrees(math.atan2(r * math.cos(t) - EARTH_NM, r * math.sin(t)))


def compass(bearing):
    return POINTS[int((bearing % 360) / 22.5 + 0.5) % 16]


def turn(a, b):
    """Signed shortest turn from heading a to heading b, in degrees."""
    return (b - a + 180) % 360 - 180
