# Select Sky

`select * from sky;`

![Select Sky: a flight wall for the Supabase SELECT badge](branding/social/readme-banner.png)

A flight wall for the Supabase SELECT badge (a Pimoroni Tufty 2350). It shows
the aircraft around you, or one flight anywhere in the world. Inspired by
[FlightWall](https://theflightwall.com/). Unofficial. Not for navigation.

<p align="center">
  <img src="branding/badge/hero-radar.png" width="45%" alt="The SELECT badge on its lanyard, showing the Select Sky radar view">
  <img src="branding/badge/hero-radar-left.png" width="45%" alt="The same badge seen from an angle">
</p>

## Views

| View | Shows |
| --- | --- |
| **Wall** | One aircraft as a name plate: airline logo, callsign, route, altitude, speed, track and vertical speed. |
| **Radar** | Aircraft at their true positions, colored by altitude. Hold **B** to zoom. |
| **Board** | A table you can sort by distance, altitude, speed or callsign. |
| **Track** | Where to look for one flight, plus its history and route. |
| **Stats** | Counts, records, an altitude histogram and top airlines. |
| **Setup** | Range, filters, units, position, a callsign to follow, brightness and lights. |

An emergency squawk (7500, 7600 or 7700) fills the screen and flashes the rear
lights. It clears after 10 seconds or on any button press. **Hold alerts** in
Setup keeps it until you press a button.

**Filters.** Setup's **Show**, **Airline** and **Aircraft type** rows narrow
every view. They combine, and a **Filter** chip shows while any is on. Tracked
flights and emergencies always show.

**Radar zoom.** Hold **B** to zoom 2.5× on the selected flight. **A**, **C**,
**UP** and **DOWN** pan; resting the crosshair on a flight selects it. Hold
**B** again to zoom out.

<table>
<tr>
  <td align="center"><img src="branding/screens/wall.png" width="260" alt="Wall view: one flight with its airline logo, route and readouts"><br><sub>Wall</sub></td>
  <td align="center"><img src="branding/screens/radar.png" width="260" alt="Radar view: aircraft colored by altitude around a sweep"><br><sub>Radar</sub></td>
  <td align="center"><img src="branding/screens/board.png" width="260" alt="Board view: a table of aircraft with airline logos"><br><sub>Board</sub></td>
</tr>
<tr>
  <td align="center"><img src="branding/screens/track.png" width="260" alt="Track view: where to look for one flight, its history and route"><br><sub>Track</sub></td>
  <td align="center"><img src="branding/screens/stats.png" width="260" alt="Stats view: counts, altitude histogram, records and top airlines"><br><sub>Stats</sub></td>
  <td align="center"><img src="branding/screens/setup.png" width="260" alt="Setup view: a list of settings"><br><sub>Setup</sub></td>
</tr>
<tr>
  <td align="center"><img src="branding/screens/locate.png" width="260" alt="Setup showing a QR code to scan with a phone"><br><sub>Exact position</sub></td>
  <td align="center"><img src="branding/screens/filter.png" width="260" alt="Setup with a filter on and a Filter chip in the top bar"><br><sub>Filter</sub></td>
  <td align="center"><img src="branding/screens/radar-zoom.png" width="260" alt="Radar zoomed in on one flight"><br><sub>Radar, zoomed</sub></td>
</tr>
<tr>
  <td align="center"><img src="branding/screens/alert.png" width="260" alt="Squawk alert: code 7700 with the aircraft's logo, callsign, distance and altitude"><br><sub>Squawk alert</sub></td>
  <td align="center"><img src="branding/screens/callsign.png" width="260" alt="Callsign editor: one character per slot"><br><sub>Track callsign</sub></td>
  <td align="center"><img src="branding/screens/paused.png" width="260" alt="Paused screen: no updates until a button press"><br><sub>Paused</sub></td>
</tr>
</table>

Simulator captures. The views show live traffic near London; the alert uses
demo traffic. Every screen, including About, Startup and the position editor, is
in [`branding/screens/`](branding/screens/).

## Controls

| Button | Action |
| --- | --- |
| **A** / **C** | Previous / next view |
| **B** | The action in the bottom bar. Held on Radar: zoom |
| **UP** / **DOWN** | Select an aircraft or a row |
| **HOME** | Back to the launcher |

## Install

**In the browser:** open [Make](https://badge.select/make), choose **Open file**,
pick [`dist/select_sky.zip`](dist/select_sky.zip) and choose **Run**. Keys: arrows,
**A**, **S** (B) and **D** (C). The browser shows demo traffic until you add a
[relay](#live-aircraft).

**On a badge:**

1. Connect the badge over USB and double-press RESET.
2. Unzip [`dist/select_sky.zip`](dist/select_sky.zip) and copy `select_sky` into
   `apps` on the TUFTY drive.
3. If the badge has no Wi-Fi yet, add `secrets.py` at the top of the drive:

   ```python
   WIFI_SSID = "your network"
   WIFI_PASSWORD = "your password"
   ```

4. Eject, press RESET and open **Select Sky**.

A badge on Wi-Fi reads adsb.fi and adsb.lol directly and needs no relay.

## Live aircraft

The public feeds send no CORS headers, so the browser simulator needs a relay.
One ships here as a Supabase Edge Function for your own project:

```sh
supabase db push --project-ref YOUR_PROJECT_REF
supabase functions deploy sky --project-ref YOUR_PROJECT_REF --no-verify-jwt
```

Then set it in `config.py` (in Make: **Files** → `config.py`):

```python
PROXY_URL = "https://YOUR_PROJECT_REF.supabase.co/functions/v1/sky"
```

The top-bar chip changes from **DEMO** to **LIVE**. Clear `PROXY_URL` before
sharing your copy, or others will use your relay.

The relay only runs when a badge calls it. To keep usage low:

- The badge pauses after 30 minutes without a button press (**Pause after** in
  Setup).
- **Live data** off shows demo traffic and sends nothing.
- `supabase functions delete sky --project-ref YOUR_PROJECT_REF` turns the
  relay off.

## Exact position

The badge has no GPS, so by default it locates you by IP address. For a precise
position, open **Setup → Exact position**, press **B** and scan the QR code with
your phone. The phone sends its location through your relay, and the relay
deletes it once the badge collects it. Without a relay, the same row opens a
coordinate editor.

## Develop

```sh
python3 tests/test_logic.py              # desktop tests
python3 scripts/package.py select_sky    # builds dist/select_sky.zip
python3 scripts/build_logos.py           # rebuilds the airline logo sheets
```

| Path | Contents |
| --- | --- |
| `select_sky/` | The app. `config.py` holds the settings you edit. |
| `supabase/` | The relay function and its migration. |
| `docs/index.html` | The phone page for Exact position. |
| `tests/` | Desktop tests and a simulator harness. |
| `branding/` | Logos, screenshots and social images. |

[DETAILS.md](DETAILS.md) covers every setting, the code layout, data and
privacy, and running the relay locally.

## Status

Built in the badge.select simulator and run on one SELECT badge with a relay.
Filters, the self-clearing alert, radar zoom and airline logos have run only in
the simulator so far. Reading the feeds without a relay is untested on hardware.
See [DETAILS.md](DETAILS.md#status).

## Credits

- **Aircraft positions:** [adsb.fi](https://adsb.fi/) and
  [adsb.lol](https://adsb.lol/) (ODbL).
- **Routes:** VRS standing data hosted by adsb.lol. Routes belong to callsigns,
  so they can be wrong for a given day.
- **Airline logos:** FlightAware and RadarBox artwork, collected in
  [Jxck-S/airline-logos](https://github.com/Jxck-S/airline-logos).
- **Starter kit:** `AGENTS.md`, `.agents/` and `scripts/package.py` come from
  badge.select.

## License

MIT, see [LICENSE](LICENSE). The license does not cover the starter kit or the
airline logos, which are trademarks of their airlines and are used here only to
identify them.

Supabase and the Supabase mark are trademarks of Supabase Inc. FlightWall is a
trademark of its owner. This project is not affiliated with either, or with any
airline.
