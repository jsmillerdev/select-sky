# Badgeware app runtime

This workspace creates an app for the Pimoroni Tufty 2350 Badgeware environment.
The current browser compatibility profile targets Badgeware v3.0.2.
badge.select runs supported app code in a MicroPython/WASM runtime with browser
display and input adapters. It does not emulate the RP2350 processor, boot UF2
firmware, or supply every MicroPython hardware module.

## Entry file and drawing loop

Put this structure in `my_badge_app/__init__.py`, adapting its contents to the app:

```python
from badgeware import *

badge.mode(LORES | VSYNC)

def update():
    screen.pen = color.rgb(20, 24, 28)
    screen.clear()
    screen.pen = color.rgb(62, 207, 142)
    screen.text("Hello!", 10, 20)

run(update)
```

`update()` takes no arguments. Let it finish and return `None` to keep running;
`run(update)` presents the screen and polls input between frames. A non-`None`
return ends that loop. Do not put an endless `while True` loop inside `update()`
or replace `run(update)` with one: the browser needs frames to return control.
Keep work per frame short, and keep persistent app variables outside the
function. Use `global` when assigning those variables inside a function.

Choose the mode once at startup: `LORES | VSYNC` draws at 160 × 120 pixels;
`HIRES | VSYNC` draws at 320 × 240. `screen.width` and `screen.height` reflect
the mode. `screen.pen` determines the color for both clearing and drawing, so
set the background pen before `screen.clear()` and the drawing pen afterward.
The simple text call is `screen.text(text, x, y, font_size=0)`; its default bitmap
font uses scale 1 when the size is omitted or zero. Named palette colors may
differ from exact RGB values; use `color.rgb(r, g, b)` for exact channels.

## Helpers and assets

The launcher changes into the app directory and adds it to the import path.
For a sibling `my_badge_app/helpers.py`, use `import helpers` or
`from helpers import draw_message`. Do not assume that `my_badge_app` itself is
an importable package. For example:

```python
# helpers.py
from badgeware import *

def draw_message(message):
    screen.pen = color.white
    screen.text(message, 10, 20)
```

```python
# In __init__.py, import at module scope and call from update().
from helpers import draw_message
```

Include assets beneath the app folder and use relative paths, such as
`open("assets/data.bin", "rb")`. A ZIP can contain the app files at its root or
inside one enclosing app folder. The workspace packager supplies that enclosing
`my_badge_app/` folder. The importer preserves its name for apps that need paths
under `/system/apps/my_badge_app/`.

An imported project allows up to 128 files, 256 KiB per text file, and 1 MiB total
decoded text and asset content. A binary asset may use up to that same 1 MiB total.
Compression does not increase the limits. App files need safe relative paths;
parent-directory traversal and files outside the app do not belong in the ZIP.

## Buttons and time

Read input in `update()`. `badge.pressed(BUTTON_A)` is true only on the frame a
press begins; `badge.held(BUTTON_A)` stays true while it is down. The app controls
include `BUTTON_A`, `BUTTON_B`, `BUTTON_C`, `BUTTON_UP` and `BUTTON_DOWN`. Choose
which ones fit the app. The virtual badge's Home control and Escape return to
the SELECT launcher.

For intervals, `import time`, record `time.ticks_ms()`, and compare readings with
`time.ticks_diff(now, started)` to handle wraparound. `badge.ticks` is a property
captured at the most recent input poll. Browser ticks follow simulated time;
they are not the current date or wall clock. An elapsed timer needs no network,
but a clock showing the actual time needs a separately verified time source.

## Internet requests in the browser

`requests.get(url, headers=None, timeout=3)` and the `urequests` alias support
GET requests to absolute `http://` or `https://` URLs. Responses expose
`status_code`, lowercase browser-visible `headers`, `text`, byte-preserving
`content`, `json()` and `close()`. Close a response after reading it. HTTP error
statuses such as 404 still return a response; connection, CORS and timeout
failures raise `OSError`.

The default and maximum timeout are three seconds. Accepted response bodies are
limited to 256 KiB, checked after the browser buffers them. Requests block the
badge program while the page stays responsive; several requests in one frame
can exceed the five-second frame watchdog. Fetch once at startup or arrange
deliberate refreshes instead of requesting every frame.

Browser CORS, TLS, mixed-content and header restrictions apply. A physical badge
may reach a service whose browser permissions do not allow badge.select. No
proxy, raw sockets, Wi-Fi association, `fetch.AsyncFetch`, other HTTP methods or
automatic authentication are supplied. Browser secrets start empty. Cross-origin
cookies are omitted; same-origin cookies follow normal browser behavior. Do not
bundle private credentials into an app ZIP.

## Checking and trying the app

Syntax and package checks catch different problems from running an app. Desktop
CPython does not provide `badgeware`; a successful syntax check cannot prove
that drawing, imports, input or networking work in the browser. The generated
[API reference](api.md) covers a curated set of verified entries, not every available API or
library. Check additional behavior in the intended runtime.

The workspace packager checks app paths, the entry file, Python UTF-8 encoding
and size limits while preserving file bytes. It does not compile or run Python.

Import the app folder or ZIP through Make, then press Run. Output shows printed
messages and runtime failures. Error cards link to project files and lines;
after editing, Run again to get fresh results. A ZIP that packages successfully
has not necessarily been run or visually checked.

Changing 2D/3D or resizing the browser editor keeps the current interpreter.
Navigation away pauses it; returning resumes it. Run starts the edited app
afresh, and Stop ends the interpreter. Reloading a full project view starts a
fresh session. Source is saved in browser storage, but live program memory is
not persistent storage. This kit does not install firmware or test a physical
badge.
