# Select Sky settings. Edit this file, then copy the app folder to the badge again.
# Nothing here is secret: do not put passwords or service keys in an app.

# Live aircraft relay: yours. The app ships without one. A browser cannot call
# ADS-B feeds directly (they send no CORS headers), so the virtual badge needs
# the Supabase Edge Function from supabase/functions/sky in this project.
# Deploy it to your own Supabase project, then paste its URL:
#   PROXY_URL = "https://YOUR-PROJECT.supabase.co/functions/v1/sky"
# While it is empty the browser shows demo traffic. A real badge on Wi-Fi
# asks adsb.fi and adsb.lol directly, so it is live either way.
# Blank it again before you share this file: the relay runs on your quota.
# Keep a path after the host (https://host/path); a query string such as ?apikey=... is fine.
PROXY_URL = ""

# The page the QR code in Setup opens on your phone. It sends the phone's position to your relay
# (PROXY_URL), which hands it to the badge. The default is this project's page.
LOCATE_PAGE = "https://jsmillerdev.github.io/select-sky/"

# Where "nearby" is. None looks the position up from your IP address once at
# startup, which is only as precise as your city. Set (latitude, longitude,
# "LABEL") to pin it and skip that lookup. On the badge, the Exact position row
# in Setup sets a precise position without editing this file. HOME wins when
# both are set.
HOME = None

# Used when the lookup fails and HOME is None: SFO, home of Supabase SELECT.
DEFAULT_HOME = (37.6213, -122.3790, "SFO")

# Callsign to follow anywhere in the world, such as "UAL1". The Setup view
# edits this on the badge as well. Changing this value replaces the callsign
# saved on the badge the next time the app starts.
TRACK = ""

# Seconds between aircraft updates. The feeds ask for 10 seconds or more.
POLL_S = 12

# Sent to the feeds from a real badge so operators can reach the project.
CONTACT = "select-sky-badge/1.0 (+https://github.com/jsmillerdev/select-sky)"

# View shown at startup: WALL, RADAR, BOARD, TRACK, STATS or SETUP.
START_VIEW = "WALL"

# Set False to skip the startup animation.
SPLASH = True
