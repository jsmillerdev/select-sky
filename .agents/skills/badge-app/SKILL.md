---
name: badge-app
description: Create or modify Badgeware MicroPython apps for the Pimoroni Tufty 2350, then package their code and assets for import into badge.select. Use for app programming, not firmware emulation or physical badge deployment.
---

# Build a badge app

Work in the user's chosen local project. Read its `AGENTS.md` if present. In the
downloaded starter kit, edit `my_badge_app/`; `__init__.py` is the entry file.
When starting from this skill alone, copy `assets/my_badge_app/` into the new
workspace and `scripts/package.py` into that workspace's `scripts/` folder.
Adapt an existing app in place when the user already has one. Keep helper modules
and required assets in the app folder. The user's idea determines the design
and controls.

Read [runtime.md](references/runtime.md) for the app lifecycle, local imports,
browser limits and validation boundaries. Use [api.md](references/api.md) when
choosing drawing, input or timing calls. Its entries are a curated teaching
subset shared with the website's editor, not an exhaustive list of supported
APIs. Verify additional APIs against the target runtime before relying on them.

Use the normal Badgeware structure: import from `badgeware`, choose the display
mode, define a short `update()` function, and call `run(update)`. Keep state
outside the drawing function when it must survive between frames. Import a
sibling helper as `import helpers`, not as a package named after the app folder.
See the reference for examples and the reason this matters.

Make the requested app work within the browser's supported runtime. If an idea
needs an unavailable hardware feature or library, explain that specific gap and
offer a small adaptation. Do not silently replace working badge APIs with mocks
or claim that arbitrary Pico firmware runs here.

Check syntax and relevant behavior with the tools available. Desktop Python
cannot execute Badgeware drawing or prove MicroPython compatibility. When a
badge.select preview is available, import the app and exercise its main drawing,
input and error paths. Report separately what ran locally, what ran in the
browser, and what remains untested.

From the workspace root, package the result with:

```sh
python3 scripts/package.py
```

The output is `dist/my_badge_app.zip`; pass another app folder name to the script
if using an existing app. To try it, open **Make** on badge.select,
choose **Open file**, select the ZIP, and press **Run**. **Open app folder** can
also import `my_badge_app/` directly. Keep credentials and development-only files
out of the app folder. Return the ZIP path and concise usage/testing notes; this
workflow does not flash hardware or deploy a website.
