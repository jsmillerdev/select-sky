"""Radar view maths with no badge in it, so the desktop tests can run it."""

import math

import skygeo

ZOOM = 2.5               # the close-up shows this much less sky: every range setting then gives a round radius
HOLD_MS = 450            # a B press this long is a hold
PAN_PX = 16              # one press of a pan key moves the view this far, in pixels
AIM_PX = 12              # a flight this close to the crosshair is picked once the view rests; under PAN_PX, so one step lets go of it
AIM_MS = 400             # how long the view rests first


def reach(range_nm):
    """How far from home the close-up may be centred: its circle stays inside the range circle."""
    return range_nm * (1.0 - 1.0 / ZOOM)


def clamp(x, y, limit):
    """(x, y) pulled back to within limit of the origin, pointing the same way."""
    d = math.sqrt(x * x + y * y)
    return (x, y) if d <= limit else (x * limit / d, y * limit / d)


def ease(cur, goal, g):
    """One glide step of the scope, (radius, east nm, north nm) a share g of the way to the goal.

    The radius moves in log steps. A radius within 0.4% of its goal lands on it, and so does a centre
    that close, which is how the scope knows it is centred on home again.
    """
    r, x, y = cur
    gr, gx, gy = goal
    r *= (gr / r) ** g
    x += (gx - x) * g
    y += (gy - y) * g
    if abs(r - gr) < gr * 0.004:
        r = gr
    if abs(x - gx) + abs(y - gy) < r * 0.004:
        x, y = gx, gy
    return r, x, y


def compass_bit(brg):
    """The compass mark a bezel marker at this bearing covers, as a bit (N, E, S, W = 1, 2, 4, 8), or 0 if it is clear of all four."""
    q = int((brg + 45) // 90) % 4
    return 1 << q if abs(skygeo.turn(brg, q * 90)) < 9 else 0


def nearest(items, x, y, within):
    """The item whose dx, dy lie closest to (x, y) and no farther than within, else None."""
    best, best_d = None, within * within
    for a in items:
        d = (a.dx - x) ** 2 + (a.dy - y) ** 2
        if d <= best_d:
            best, best_d = a, d
    return best


def b_event(down, now, pressed, held, gap=False):
    """Tell a tap from a hold. down is when B went down, or None; returns (down, event).

    event is "tap" once B is up again, "hold" once it has been down HOLD_MS, else None. A press that
    began before the view was up (so was never seen going down) counts as nothing. So does one first
    seen after a gap, when the frame before this one was long ago (an alert, another view or a blocked
    frame came between): it began somewhere in the gap, so its length is unknown. And so does one that
    ended inside a blocked frame HOLD_MS or more after it began: it may have been a tap or a hold, and
    guessing wrong would step the range when the wearer asked for the close-up.
    """
    if pressed and not gap:
        return now, None
    if down is None:
        return None, None
    if not held:
        return None, "tap" if now - down < HOLD_MS else None
    if now - down >= HOLD_MS:
        return None, "hold"
    return down, None
