# Badge app API reference

This is the curated API subset used by badge.select editor help. It is not an exhaustive list of every runtime API. Read runtime.md for the app lifecycle and browser limitations.

## screen.pen

```python
screen.pen = color
```

The color or brush used by subsequent drawing calls. Assign it before drawing text, shapes or clearing the screen.

## screen.clear

```python
screen.clear()
```

Fill the screen with the current pen. Set screen.pen to the background color first, then choose a different pen for your drawing.

## screen.text

```python
screen.text(text, x, y, font_size=0)
```

Draw text in the current pen and font at pixel coordinates. This is the simple position overload; the default bitmap font uses scale 1 when font_size is omitted or 0. Returns the drawn bounds.

- **text**: Text to draw, as a string. Use str(value) to display a number.
- **x**: Horizontal position in pixels from the left. Pass the position arguments in order.
- **y**: Vertical position in pixels from the top.
- **font_size=0**: Optional font size. For bitmap fonts, 1 is normal and 2 doubles it. For vector fonts, this is point size. 0 uses the font default.

## screen.rectangle

```python
screen.rectangle(x, y, width, height)
```

Draw a filled rectangle using the current pen. Coordinates and dimensions are in pixels. A rect object is also accepted.

- **x**: Left edge in pixels.
- **y**: Top edge in pixels.
- **width**: Rectangle width in pixels.
- **height**: Rectangle height in pixels.

## screen.circle

```python
screen.circle(x, y, radius)
```

Draw a filled circle using the current pen. The position is its center and the radius is in pixels. A vec2 center is also accepted.

- **x**: Center position from the left, in pixels.
- **y**: Center position from the top, in pixels.
- **radius**: Distance from the center to the edge, in pixels.

## screen.line

```python
screen.line(x1, y1, x2, y2)
```

Draw a line between two pixel positions using the current pen. Two vec2 points are also accepted.

- **x1**: Starting horizontal coordinate in pixels.
- **y1**: Starting vertical coordinate in pixels.
- **x2**: Ending horizontal coordinate in pixels.
- **y2**: Ending vertical coordinate in pixels.

## screen.width

```python
screen.width
```

Read-only drawing width in pixels: 160 in LORES or 320 in HIRES. Useful for placing drawings relative to the screen.

## screen.height

```python
screen.height
```

Read-only drawing height in pixels: 120 in LORES or 240 in HIRES.

## badge.mode

```python
badge.mode(mode=None)
```

Choose screen resolution and timing flags, usually once before run(update). Combine LORES or HIRES with VSYNC using |. With no argument, returns the current flags.

- **mode=None**: LORES | VSYNC for 160 × 120, or HIRES | VSYNC for 320 × 240. Omit to read the current mode.

## badge.pressed

```python
badge.pressed(button=None)
```

With a button argument, returns true only on the frame when that press begins. Use for one action per press. With no argument, returns the tuple of newly pressed buttons.

- **button=None**: A button constant such as BUTTON_A. Omit to get all buttons whose press began this frame.

## badge.held

```python
badge.held(button=None)
```

With a button argument, returns true on every frame while it is down. Use for continuous movement. With no argument, returns the tuple of buttons currently held.

- **button=None**: A button constant such as BUTTON_A. Omit to get all held buttons.

## badge.ticks

```python
badge.ticks
```

Millisecond tick count captured at the latest input poll. run(update) polls for each frame. The browser uses simulated time; this is not a wall clock. Use time.ticks_diff for elapsed intervals.

## color.rgb

```python
color.rgb(r, g, b, a=255)
```

Create a color from red, green and blue channels, each 0–255. Optional alpha is 0 for transparent or 255 for opaque.

- **r**: Red channel, 0–255.
- **g**: Green channel, 0–255.
- **b**: Blue channel, 0–255.
- **a=255**: Optional alpha, 0–255. Defaults to fully opaque.

## color.white

```python
color.white
```

The named white palette color. Use color.rgb(255, 255, 255) when you need exact RGB white rather than the board palette.

## color.black

```python
color.black
```

The named black palette color. Use color.rgb(0, 0, 0) when you need exact RGB black rather than the board palette.

## display.backlight

```python
display.backlight(value)
```

Set the display backlight level with a fraction from 0 (off) to 1 (full brightness).

- **value**: Brightness fraction in the range 0–1, such as 0.85.

## run

```python
run(update, *, duration=None)
```

Call update() repeatedly, present the screen and poll buttons between frames. update takes no arguments; let it return None to continue. A non-None return ends the loop. Keep each update short so input can respond.

- **update**: The drawing function itself, without calling it: run(update), not run(update()).
- **duration=None**: Optional keyword-only duration in milliseconds. None leaves the loop running until update returns a result or the app is stopped.

## LORES

```python
LORES
```

160 × 120 drawing resolution. Use badge.mode(LORES | VSYNC).

## HIRES

```python
HIRES
```

320 × 240 drawing resolution. Use badge.mode(HIRES | VSYNC).

## VSYNC

```python
VSYNC
```

The display synchronization flag. Combine with a resolution flag using |; it does not choose the resolution itself.

## BUTTON_A

```python
BUTTON_A
```

The badge’s A button. Pass it to badge.pressed or badge.held.

## BUTTON_B

```python
BUTTON_B
```

The badge’s B button. Pass it to badge.pressed or badge.held.

## BUTTON_C

```python
BUTTON_C
```

The badge’s C button. Pass it to badge.pressed or badge.held.

## BUTTON_UP

```python
BUTTON_UP
```

The badge’s upper arrow button. Pass it to badge.pressed or badge.held.

## BUTTON_DOWN

```python
BUTTON_DOWN
```

The badge’s lower arrow button. Pass it to badge.pressed or badge.held.

## time.ticks_ms

```python
time.ticks_ms()
```

Requires import time. Read the millisecond tick counter. It wraps eventually, so measure intervals with time.ticks_diff. In the browser this follows simulated time, not the current date or wall clock.

## time.ticks_diff

```python
time.ticks_diff(end, start)
```

Requires import time. Subtract two tick readings while handling counter wrap. Readings from ticks_ms produce milliseconds. Keep the readings within half the counter’s wrap period.

- **end**: The later tick reading, usually time.ticks_ms().
- **start**: An earlier reading from the same tick function.
