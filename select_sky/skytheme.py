"""Supabase dark palette and type for a 320 x 240 panel."""

from badgeware import *

rgb = color.rgb

# Surfaces, darkest first. Neutrals keep R == B so the panel shows no colour cast.
BG_DEEP = rgb(8, 12, 8)
BG = rgb(16, 20, 16)
PANEL = rgb(24, 24, 24)
RAISED = rgb(33, 32, 33)
SELECTED = rgb(41, 40, 41)
LINE = rgb(49, 48, 49)
LINE_HI = rgb(66, 65, 66)

TEXT = rgb(239, 239, 239)
TEXT_2 = rgb(189, 190, 189)
TEXT_3 = rgb(140, 139, 140)
TEXT_4 = rgb(99, 97, 99)

GREEN = rgb(62, 207, 142)
GREEN_HI = rgb(133, 224, 186)
GREEN_FACE = rgb(50, 179, 121)
GREEN_MID = rgb(29, 114, 76)
GREEN_DIM = rgb(0, 98, 57)
GREEN_TINT = rgb(0, 41, 24)
GREEN_INK = rgb(8, 39, 27)

AMBER = rgb(242, 175, 72)
AMBER_TINT = rgb(52, 28, 0)
RED = rgb(241, 106, 80)
RED_STRONG = rgb(229, 77, 46)
RED_TINT = rgb(59, 24, 19)
SKY = rgb(82, 169, 255)
SKY_TINT = rgb(25, 41, 54)
VIOLET = rgb(158, 140, 252)
VIOLET_TINT = rgb(41, 35, 56)

# Pixel fonts for labels and tables. Vector Mona Sans carries the big type; it
# ships with the firmware, and the pixel faces stand in if it is missing.
F_CAPS = font.ark
F_BODY = font.nope
F_BOLD = font.absolute
F_HUGE = font.ignore
try:
    F_SANS = font.load("/system/assets/fonts/MonaSans-Medium.af")
except Exception:
    F_SANS = None

# Altitude ramp: warm near the ground, Supabase green in the climb, cool at cruise.
_STOPS = ((0, (255, 140, 40)), (3, (250, 205, 70)), (9, (62, 207, 142)),
          (20, (70, 205, 235)), (31, (82, 169, 255)), (42, (158, 140, 252)))


def _ramp():
    out = []
    for kft in range(46):
        for i in range(len(_STOPS) - 1):
            a, b = _STOPS[i], _STOPS[i + 1]
            if kft <= b[0] or i == len(_STOPS) - 2:
                t = min(1.0, max(0.0, (kft - a[0]) / (b[0] - a[0])))
                out.append(rgb(*[int(a[1][k] + (b[1][k] - a[1][k]) * t) for k in range(3)]))
                break
    return out


ALT_RAMP = _ramp()


def alt_color(alt_ft):
    """Ramp colour for an altitude in feet. Ground and unknown read as grey."""
    if alt_ft <= 0:
        return TEXT_3
    return ALT_RAMP[min(45, int(alt_ft) // 1000)]
