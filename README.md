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

Simulator captures. The views show live traffic near San Francisco; the alert uses
demo traffic. Every screen, including About, Startup and the position editor, is
in [`branding/screens/`](branding/screens/).

## Controls

| Button | Action |
| --- | --- |
| **A** / **C** | Previous / next view |
| **B** | The action in the bottom bar. Held on Radar: zoom |
| **UP** / **DOWN** | Select an aircraft or a row |
| **HOME** | Back to the launcher |

## Get started

Pick the row that matches what you want. Each one stands on its own.

| You want | You need | Time |
| --- | --- | --- |
| [Try it in your browser](#1-try-it-in-your-browser) | Nothing | 1 minute |
| [Run it on your badge](#2-run-it-on-your-badge) | The badge, a USB cable, Wi-Fi | 5 minutes |
| [Live aircraft in the browser](#3-live-aircraft-in-the-browser) | A free Supabase account | 10 minutes |

A badge on Wi-Fi shows live aircraft by itself. Supabase is only for live
aircraft in the browser simulator, which cannot reach the flight feeds directly.

### 1. Try it in your browser

1. Download [`dist/select_sky.zip`](dist/select_sky.zip).
2. Open [Make](https://badge.select/make), choose **Open file** and pick the ZIP.
3. Choose **Run**.

The badge shows demo traffic with a **DEMO** chip. Keys: arrows, **A**, **S**
(B) and **D** (C).

### 2. Run it on your badge

1. Connect the badge over USB and double-press RESET. A drive named TUFTY
   appears.
2. Unzip [`dist/select_sky.zip`](dist/select_sky.zip) and copy the `select_sky`
   folder into `apps` on the TUFTY drive.
3. If the badge has no Wi-Fi yet, add `secrets.py` at the top of the drive:

   ```python
   WIFI_SSID = "your network"
   WIFI_PASSWORD = "your password"
   ```

4. Eject the drive, press RESET and open **Select Sky**.

The badge finds you by IP address and reads adsb.fi and adsb.lol directly. The
chip reads **LIVE**. No Supabase needed.

### 3. Live aircraft in the browser

The public flight feeds do not allow web pages to read them, so the browser
needs a relay. The relay is one Supabase Edge Function that you deploy to your
own project. It needs no database and no secrets, and the Free plan is enough.

1. Create a project at [supabase.com](https://supabase.com/dashboard). Its
   **project ref** is the ID in the dashboard URL,
   `supabase.com/dashboard/project/YOUR_PROJECT_REF`.
2. Install the [Supabase CLI](https://supabase.com/docs/guides/cli/getting-started) and sign in:

   ```sh
   brew install supabase/tap/supabase
   supabase login
   ```

   Not on a Mac? Follow the install guide, or put `npx` in front of every
   `supabase` command (needs Node.js).

3. Get this repository and deploy the relay from its folder:

   ```sh
   git clone https://github.com/jsmillerdev/select-sky.git
   cd select-sky
   supabase functions deploy sky --project-ref YOUR_PROJECT_REF --no-verify-jwt --use-api
   ```

   `--use-api` builds the function on Supabase, so you do not need Docker.

4. In Make, after you import the ZIP, choose **Files**, open `config.py` and set:

   ```python
   PROXY_URL = "https://YOUR_PROJECT_REF.supabase.co/functions/v1/sky"
   ```

5. Choose **Run**. The chip changes from **DEMO** to **LIVE**.

Clear `PROXY_URL` before you share your copy, or others will use your relay.

The relay only runs when a badge calls it. To keep usage low:

- The badge pauses after 30 minutes without a button press (**Pause after** in
  Setup).
- **Live data** off shows demo traffic and sends nothing.
- `supabase functions delete sky --project-ref YOUR_PROJECT_REF` turns the
  relay off.

## Exact position

The badge has no GPS, so by default it locates you by IP address. For a precise
position, open **Setup → Exact position** and press **B**:

- **Without a relay**, a coordinate editor opens. Set each digit with UP and
  DOWN, move with A and C, and save with B.
- **With a relay**, a QR code appears. Scan it with your phone and allow
  location access. To type the coordinates instead, press **C** (TYPE).

**The phone route needs one small table**, where the relay parks the position
until the badge collects it and deletes it. Create it once in the same project,
from the repository folder:

```sh
supabase db push --project-ref YOUR_PROJECT_REF
```

Skip it if you are happy to type coordinates. Live aircraft work without it.

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
