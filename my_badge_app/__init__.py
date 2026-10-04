from badgeware import *

# pressed() reports a new press, so holding a button counts only once.
badge.mode(LORES | VSYNC)
display.backlight(0.85)
count = 0


def update():
    global count
    if badge.pressed(BUTTON_A):
        count += 1
    if badge.pressed(BUTTON_B):
        count -= 1
    if badge.pressed(BUTTON_C):
        count = 0

    screen.pen = color.rgb(18, 28, 24)
    screen.clear()
    screen.pen = color.rgb(62, 207, 142)
    screen.text("BUTTON COUNTER", 8, 14)
    screen.pen = color.white
    screen.text(str(count), 12, 42, 3)
    screen.text("A +1  B -1", 8, 88)
    screen.text("C resets", 8, 104)


print("Press A to add, B to subtract, or C to reset.")
run(update)
