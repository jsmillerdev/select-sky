# Select Sky: details

Reference notes for [Select Sky](README.md): what the hardware does, how the
relay behaves and what it costs, every setting, how the code is laid out, what
data goes where, and what has and has not been tested.

## Hardware it uses

- **Screen:** 320 x 240, with antialiased vector type and shapes.
- **Buttons:** all five, with auto-repeat on the arrows.
- **Rear lights:** follow the radar sweep, glow as an aircraft comes close,
  blink for a new arrival and flash for an emergency code.
- **Light sensor:** Auto dim (off by default) lowers the backlight when the room
  is dark. It is experimental: see [Status](#status).
- **Battery:** shown in the top bar. The rear lights switch off below 15% on
  battery power.
- **Clock:** the top bar shows the time once a live feed or the badge clock
  supplies it.
- **Storage:** your settings persist between runs.

## Try it in the browser

1. Package the app:

   ```sh
   python3 scripts/package.py select_sky
   ```

2. Open [Make](https://badge.select/make), choose **Open file** and select
   `dist/select_sky.zip`.
3. Choose **Run**. Click the badge, then use the arrow keys, **A**, **S** (for
   B) and **D** (for C).

In the browser the app shows demo traffic around your location until you give
it a relay of your own. The chip in the top bar reads **DEMO** or **LIVE** to
tell you which one you are seeing.

## Get live aircraft

The app ships without a live source for the browser. To see real aircraft on
the virtual badge, deploy your own relay and give the app its URL.

Aircraft broadcast their position over ADS-B, and community feeds publish those
positions. The feeds do not send CORS headers, so a web page cannot read them.
The relay in this project, the Supabase Edge Function `supabase/functions/sky`,
adds the headers, trims each aircraft to the 16 values the badge draws and
caches each answer for five seconds.

1. Create a Supabase project, or pick one you already use.
2. Create the table that holds a phone's position for a few minutes. Only
   [Set your exact position](#set-your-exact-position) needs it, so skip this
   step if you want aircraft alone. The migration in `supabase/migrations`
   makes the table and keeps it out of the Data API:

   ```sh
   supabase db push --project-ref YOUR_PROJECT_REF
   ```

3. Deploy the function to it. Callers send no key, so it runs without JWT
   verification. It reaches the table with the secret key that Supabase gives
   every Edge Function, so you set no secret:

   ```sh
   supabase functions deploy sky --project-ref YOUR_PROJECT_REF --no-verify-jwt
   ```

4. Give the app your URL, in one of two ways:

   - **In Make:** after you import the ZIP, choose **Files**, open `config.py`
     and set `PROXY_URL`. The change stays in your browser.
   - **In the source:** set `PROXY_URL` in `select_sky/config.py`, then package
     the app again.

   ```python
   PROXY_URL = "https://YOUR_PROJECT_REF.supabase.co/functions/v1/sky"
   ```

5. Choose **Run**. The chip turns green and reads **LIVE**.

Before you share your copy of the app, set `PROXY_URL` back to `""`. Everyone
who runs a copy with your URL uses your relay and your Supabase quota.

A real badge on Wi-Fi does not need the relay. If `PROXY_URL` is empty or the
relay stops answering, the badge asks adsb.fi and then adsb.lol directly. If no
source answers, the app shows demo traffic and tries the live sources again
every minute.

What the relay costs you:

- One badge that polls every 12 seconds makes about 216,000 calls a month.
  Compare that with the Edge Function quota of your Supabase plan.
- Supabase can pause a Free plan project that has no database activity, and
  aircraft requests make no database queries. If the chip changes to **DEMO**
  after a quiet week, resume the project in the Supabase dashboard.

The function is public, so anyone with the URL can call it. For aircraft it only
reads two fixed feeds and limits the radius to 100 nautical miles. It answers
from a 5-second cache, serves an answer up to 60 seconds old if both feeds
fail, and returns 503 when requests for different places exceed about one
upstream request per second per instance.

For the phone flow it also accepts a position under a six-character code and
gives it out once. Anyone with the URL can store a position under any code, and
the function does not limit how many it stores.

The feeds ask for a contact in the User-Agent, so change `USER_AGENT` in
`index.ts` to one for your own project.

## Put it on a badge

1. Plug in the badge with a USB data cable and double-press RESET.
2. Copy the `select_sky` folder into the `apps` folder on the TUFTY drive.
3. If your badge has no Wi-Fi details yet, add them to `secrets.py` on the
   drive:

   ```python
   WIFI_SSID = "your network"
   WIFI_PASSWORD = "your password"
   ```

4. Eject the drive, press RESET and open **Select Sky** from the launcher.

The complete steps are in the
[first app guide](https://badge.select/guides/first-program).

## Set your exact position

The badge has no GPS. Without help it takes home from your IP address, which is
only as precise as your city. To center the radar on where you stand, set an
exact position.

**With your phone.** This needs your relay (`PROXY_URL` starting with
`https://`) and the table from [Get live aircraft](#get-live-aircraft).

1. On the badge, open **Setup**, pick **Exact position** and press B (LOCATE).
   The badge shows a QR code.
2. Scan the code with your phone and open the link.
3. Tap **Share my location**, then allow location access when your phone asks.

The phone sends its position to your relay. The badge collects it within a few
seconds, saves it, sets Home to Exact and re-centers the radar. The code works
for five minutes and the screen counts down. Press A to cancel. When the code
has expired, press B for a new one.

**By typing.** Without a relay, or when the phone route does not work, pick
**Exact position** and press B (EDIT). On the QR screen, press C (TYPE) to
reach the same editor. Set each digit with UP and DOWN, move with A and C, and
save with B. Latitude goes to 90 and longitude to 180.

The QR code opens `LOCATE_PAGE`, the one-file page in `docs/index.html`. It
works with any relay: the code and the relay's address travel in the part of
the link after `#`, which your browser keeps on the phone. To host your own
copy, publish `docs/` with GitHub Pages and set `LOCATE_PAGE`.

## Settings

Change most settings on the badge in the **Setup** view. `select_sky/config.py`
holds the ones you set once:

| Setting | Purpose |
| --- | --- |
| `PROXY_URL` | URL of your own `sky` Edge Function. Empty, as shipped, means demo traffic in the browser. |
| `LOCATE_PAGE` | The page the QR code in Setup opens on your phone. The page sends the phone's position to your relay. Change it only to use your own copy of `docs/index.html`. |
| `HOME` | `(latitude, longitude, "LABEL")` to pin where "nearby" is. `None` looks it up from your IP address, or uses the exact position you set in Setup. |
| `TRACK` | A callsign to follow anywhere, such as `"UAL1"`. |
| `POLL_S` | Seconds between updates. The feeds ask for 10 or more. |
| `CONTACT` | The User-Agent a real badge sends to the feeds. |
| `START_VIEW`, `SPLASH` | The first view, and whether to play the startup animation. |

## How it works

```text
select_sky/
  __init__.py     App object and frame loop
  config.py       Settings you edit
  skyfeed.py      Sources: Edge Function, direct feeds, demo. One request per frame at most
  skymodel.py     Aircraft rows, dead reckoning, selection, records, alerts
  skydemo.py      Demo traffic that crosses the sky on straight tracks
  skygeo.py       Distance, bearing, elevation
  skydata.py      Airlines, aircraft types and airports
  skyqr.py        QR code encoder for the locate screen
  skyui.py        Drawing kit and the top and bottom bars
  skytheme.py     Supabase dark palette, fonts and the altitude ramp
  skyhw.py        Rear lights, light sensor, backlight and battery
  skyoverlay.py   Startup, emergency takeover, toasts and view transitions
  view_*.py       One module per view
supabase/functions/sky/index.ts   The relay
supabase/migrations/              The table that holds a position until the badge collects it
docs/index.html                   The phone page that sends a position to the relay
tests/test_logic.py               Desktop tests for the maths, model and feeds
tests/sim/run.mjs                 Runs the packaged app in the badge.select simulator
```

The feed reports each aircraft every 12 seconds. Between reports the model
moves each aircraft along its track at its ground speed, so the radar stays in
motion.

## Develop

```sh
python3 tests/test_logic.py              # maths, model, demo and feed parsing
python3 scripts/package.py select_sky    # builds dist/select_sky.zip
```

Packaging checks paths, encoding and size limits. It does not run the app. To
check behaviour, import the ZIP in Make and choose **Run**.

`tests/sim/run.mjs` does that for you in headless Chrome: it imports the ZIP,
presses the buttons you list and saves screenshots of the badge screen.

```sh
cd tests/sim && npm install playwright-core
node run.mjs ../../dist/select_sky.zip out "wait:6000;shot:wall;key:C;wait:2000;shot:radar"
```

To run the relay on your computer:

```sh
deno run --allow-net supabase/functions/sky/index.ts
curl 'http://localhost:8000/?lat=37.62&lon=-122.38&r=25'
```

That serves aircraft only. The phone flow needs the table, so to try it locally
run `supabase start` and `supabase functions serve`.

## Data and privacy

- **Aircraft positions:** [adsb.fi](https://adsb.fi/) and
  [adsb.lol](https://adsb.lol/) (ODbL). Both are community feeds, and adsb.fi
  asks for personal, non-commercial use. Read their terms before you rely on
  them, and keep the attribution.
- **Routes:** the VRS standing data that adsb.lol hosts. A route belongs to a
  callsign, not to today's flight, so it can be wrong.
- **Location:** the badge has no GPS. When `HOME` is `None`, the app sends one
  request to [ipwho.is](https://ipwho.is/) at startup to find your approximate
  position, which is only as precise as your city. Set `HOME` to skip that
  request.
- **Exact position:** to center the radar where you stand, set the Exact
  position row in Setup, by phone or by typing. The badge stores the position,
  and the app sends it to the aircraft source like any home position. With Home
  set to Exact, the app still asks ipwho.is for your city name and time zone.
  That request carries no position, and the app ignores the coordinates in the
  answer.
- **Position from a phone:** the page at `LOCATE_PAGE` is one static file. It
  reads your phone's position only after you tap the button and allow location
  access. It sends the position to one place, the relay named in the QR code,
  which is your own `PROXY_URL`. The page loads no other scripts, fonts or
  analytics and sends nothing anywhere else. The relay stores the position
  (rounded to about a metre), its accuracy and the time it arrived in one row
  of the `sky_handoff` table, under the code on the badge screen. It stores no
  IP address and no user agent, and it does not log positions. The row is
  deleted when the badge collects it. The relay ignores a row after ten minutes
  and deletes expired rows when it next handles a locate request, so a position
  that nobody collects can stay in the table for longer than ten minutes if no
  locate request follows. Once collected, the position lives only on the badge.
  The table has no Data API access, and the function reaches it with the
  project's secret key. The code is the only secret: anyone who sees the QR
  code while it is on screen could send a position to it, or collect yours
  first. Supabase and GitHub keep their own request logs as they do for any
  site.
- The app sends your home position to the aircraft source, rounded to four
  decimal places. The relay rounds it to two.
- Do not put passwords or service keys in the app folder. The app needs none.

## Status

Select Sky was developed and tested in the badge.select browser simulator. It
has also run on one physical SELECT badge: it launched, joined Wi-Fi from
`secrets.py` and showed live aircraft through the relay. Calling the feeds
directly from a badge, with no relay, follows the firmware source but is
untested.

On a real badge every update is a blocking request. The screen keeps its last
frame, and a button press that starts and ends during the request is lost. The
8-second timeout covers each connect and read, not the whole request, and the
DNS lookup has no timeout, so a slow or failing source can hold the screen for
longer than 8 seconds. No request has been timed on a badge.

Not verified on hardware:

- **Auto dim:** the light sensor's polarity and range are undocumented. The app
  learns the range from what it sees, so a single bright moment can leave the
  screen dimmer indoors until you relaunch. Setup shows the live reading: cover
  the sensor and check that the reading falls.
- **Direct feeds:** download time and memory for 50 to 200 KB responses.
- **Launch time and frame rate:** the badge compiles about 180 KB of source on
  every launch. If frames run slower than about 90 ms, the app turns off
  antialiasing; that threshold is untested on the device.
- **Rear lights:** their positions on the case are unknown, so the sweep follows
  them in index order.
- **SELECT's own Wi-Fi manager:** the app does not opt in to it, and how the two
  coexist is unknown.
- **Scan to locate:** a phone camera reading the QR code off the badge screen,
  the time the badge takes to draw the code, and the phone page on iOS Safari
  and Android Chrome. The tests decode screenshots of the code with three
  software readers and run the page in desktop Chrome with a mocked position.

## Starter kit files

The rest of this workspace is the badge.select starter kit.
`scripts/package.py` builds the ZIP, and `AGENTS.md` and `.agents/` guide
coding agents. Those files come from badge.select, and the
MIT license in this repo does not cover them.

Logos, screenshots and social images are in [`branding/`](branding/README.md).
