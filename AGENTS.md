# Instructions for coding agents

This workspace contains one MicroPython Badgeware app and its development tools.
Start with [README.md](README.md), then read
[.agents/skills/badge-app/SKILL.md](.agents/skills/badge-app/SKILL.md) and its
runtime/API references before changing the app. These local files are available
even when your agent does not automatically discover project skills.

Work inside `my_badge_app/` unless the user's request requires a tooling change.
Keep `__init__.py` at its root, preserve assets, and make the smallest complete
change that serves the requested behavior. Use the documented Badgeware APIs;
do not assume CPython libraries, arbitrary RP2350 hardware or firmware emulation.

After editing, run this from the workspace root:

```sh
python3 scripts/package.py
```

The helper creates `dist/my_badge_app.zip` with only the app's files. A successful
package confirms paths, encoding and size limits, not Python execution. Do not
report runtime success without running the app. If browser interaction is
available, open Make, import the ZIP through **Open file**, choose
**Run**, and exercise the changed behavior. Otherwise give the user the ZIP and
state that runtime behavior remains untested.

Never upload the whole workspace: `AGENTS.md`, the `.agents` skill folder and
`scripts/` belong on the development computer. **Open app folder** expects just
`my_badge_app/`. Reimporting creates a separate browser project, so identify the
new import when reporting results; browser edits do not update this local folder.

Keep the work local to this app. Packaging does not authorize hardware access,
firmware flashing, website deployment or live service configuration. Networking
uses browser rules and the runtime's documented limits; do not add real secrets
to the downloadable app.
