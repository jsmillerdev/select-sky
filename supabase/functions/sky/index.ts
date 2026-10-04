// sky: a Supabase Edge Function that lets a browser read live aircraft positions.
//
// Public ADS-B feeds send no CORS headers, so the virtual badge on badge.select
// cannot call them. This relay adds the headers, trims each aircraft to the 16
// columns the badge draws (about a fifth of the upstream size) and caches each
// answer for five seconds so many badges share one upstream request.
//
//   GET ?lat=37.62&lon=-122.38&r=25   aircraft within r nautical miles (1 to 100)
//   GET ?cs=UAL1                      one callsign, anywhere
//
// Answers 502 when both feeds fail and 503 when this instance has used its one
// upstream request per second; an answer under a minute old is sent instead, if any.
//
// Deploy with verify_jwt = false: the data is public and the badge sends no key.

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Max-Age': '86400',
}
// The feeds ask for a contact in the User-Agent. Change it to your own project.
const USER_AGENT = 'select-sky-badge/1.0 (+https://github.com/jsmillerdev/select-sky)'
const CACHE_MS = 5000
const STALE_MS = 60_000 // the badge extrapolates a position for 60 s at most (COAST_S)
// The badge's browser aborts at 3 s, so the whole request gets 2.3 s and adsb.fi gets 0.9 s of it.
const DEADLINE_MS = 2300
const FIRST_TRY_MS = 900
const MAX_RADIUS_NM = 100

type Query = { lat: number; lon: number; r: number } | { cs: string }

// Tried in order. adsb.fi answers faster; adsb.lol is the fallback.
const UPSTREAMS: ((q: Query) => string)[] = [
  (q) => 'cs' in q
    ? `https://opendata.adsb.fi/api/v2/callsign/${q.cs}`
    : `https://opendata.adsb.fi/api/v3/lat/${q.lat}/lon/${q.lon}/dist/${q.r}`,
  (q) => 'cs' in q
    ? `https://api.adsb.lol/v2/callsign/${q.cs}`
    : `https://api.adsb.lol/v2/point/${q.lat}/${q.lon}/${q.r}`,
]

type Hit = { at: number; now: number; rows: (string | number)[][] }
const cache = new Map<string, Hit>()

// Fresh upstream fetches are capped per isolate at about one a second, the rate adsb.fi
// allows. Cache hits and requests that join a fetch already under way cost nothing.
let tokens = 1
let refilledAt = Date.now()
function takeToken() {
  const now = Date.now()
  tokens = Math.min(1, tokens + (now - refilledAt) / 1000)
  refilledAt = now
  if (tokens < 1) return false
  tokens -= 1
  return true
}

// One upstream request per key at a time. Resolves to the fresh answer, null when both
// feeds failed, or undefined when the rate cap shed the request.
const inflight = new Map<string, Promise<Hit | null | undefined>>()

function reply(body: string, status = 200, extra: Record<string, string> = {}) {
  return new Response(body, { status, headers: { ...CORS, 'Content-Type': 'application/json', ...extra } })
}

function parse(url: URL): Query | null {
  const cs = (url.searchParams.get('cs') ?? '').trim().toUpperCase()
  if (cs) return /^[A-Z0-9]{2,8}$/.test(cs) ? { cs } : null
  // Number('') and Number(' ') are 0, so a blank value must count as missing.
  const num = (k: string, d: number) => {
    const v = (url.searchParams.get(k) ?? '').trim()
    return v ? Number(v) : d
  }
  const lat = num('lat', NaN)
  const lon = num('lon', NaN)
  const r = num('r', 25)
  if (!Number.isFinite(lat) || !Number.isFinite(lon) || !Number.isFinite(r)) return null
  if (Math.abs(lat) > 90 || Math.abs(lon) > 180) return null
  // Rounding the position to 0.01 degrees lets nearby badges share a cache entry.
  return { lat: +lat.toFixed(2), lon: +lon.toFixed(2), r: Math.round(Math.max(1, Math.min(MAX_RADIUS_NM, r))) }
}

async function fetchUpstream(q: Query) {
  const end = Date.now() + DEADLINE_MS
  for (const [i, url] of UPSTREAMS.entries()) {
    const left = end - Date.now()
    if (left < 300) break
    try {
      const res = await fetch(url(q), {
        headers: { 'User-Agent': USER_AGENT, Accept: 'application/json' },
        signal: AbortSignal.timeout(i === 0 ? Math.min(FIRST_TRY_MS, left) : left),
      })
      if (res.ok) return await res.json()
    } catch (_) {
      // Fall through to the next feed.
    }
  }
  return null
}

// Row: [hex, callsign, type, alt_ft (0 ground, -1 unknown, airborne readings at or below the
//       1013 hPa datum are sent as 1), gs_kt, track_deg, vrate_fpm,
//       lat, lon, squawk, dbFlags, dist_nm, bearing_deg, category, registration, seen_pos_s]
// deno-lint-ignore no-explicit-any
function compact(x: any) {
  return [
    x.hex ?? '', (x.flight ?? '').trim(), x.t ?? '',
    x.alt_baro === 'ground' ? 0 : typeof x.alt_baro === 'number' ? Math.max(1, Math.round(x.alt_baro)) : -1,
    Math.round(x.gs ?? -1), Math.round(x.track ?? x.true_heading ?? -1),
    Math.round(x.baro_rate ?? x.geom_rate ?? 0),
    +Number(x.lat).toFixed(4), +Number(x.lon).toFixed(4),
    x.squawk ?? '', x.dbFlags ?? 0, +Number(x.dst ?? 0).toFixed(1), Math.round(x.dir ?? 0),
    x.category ?? '', x.r ?? '', Math.round(x.seen_pos ?? 0),
  ]
}

// An answer served from the cache is older than the upstream said. Add that age to the
// payload clock and to every row's seen_pos so the badge still dead-reckons from the right moment.
function render(h: Hit) {
  const age = Math.round((Date.now() - h.at) / 1000)
  const rows = age ? h.rows.map((r) => [...r.slice(0, 15), (r[15] as number) + age]) : h.rows
  return JSON.stringify({ now: h.now + age, n: rows.length, a: rows })
}

async function load(key: string, q: Query) {
  if (!takeToken()) return undefined
  const data = await fetchUpstream(q)
  if (!data) return null
  // deno-lint-ignore no-explicit-any
  const rows = (data.ac ?? data.aircraft ?? []).filter((x: any) => x.lat != null && x.lon != null).map(compact)
  // "now" is epoch milliseconds on v3 feeds and float seconds on v2. The badge wants seconds.
  const now = Number(data.now ?? Date.now())
  const entry: Hit = { at: Date.now(), now: Math.round(now > 1e11 ? now / 1000 : now), rows }

  cache.set(key, entry)
  if (cache.size > 128) cache.delete(cache.keys().next().value!)
  return entry
}

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: CORS })
  if (req.method !== 'GET') return reply('{"error":"GET only"}', 405)
  const q = parse(new URL(req.url))
  if (!q) return reply('{"error":"use ?lat=&lon=&r= or ?cs="}', 400)

  const key = JSON.stringify(q)
  const hit = cache.get(key)
  if (hit && Date.now() - hit.at < CACHE_MS) {
    const left = Math.max(0, Math.floor((CACHE_MS - (Date.now() - hit.at)) / 1000))
    return reply(render(hit), 200, { 'X-Cache': 'HIT', 'Cache-Control': `public, max-age=${left}` })
  }

  let job = inflight.get(key)
  if (!job) {
    job = load(key, q).finally(() => inflight.delete(key))
    inflight.set(key, job)
  }
  const fresh = await job
  if (fresh) return reply(render(fresh), 200, { 'Cache-Control': 'public, max-age=5' })
  // No fresh answer: an old one beats an error for a minute. render() ages it so the badge
  // dead-reckons the aircraft forward instead of drawing them where they were.
  if (hit && Date.now() - hit.at < STALE_MS) return reply(render(hit), 200, { 'X-Cache': 'STALE' })
  if (fresh === undefined) return reply('{"error":"busy"}', 503, { 'Retry-After': '2' })
  return reply('{"error":"feeds unreachable"}', 502)
})
