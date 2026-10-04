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
// It also hands a phone's position to the badge that asked for it (scan-to-locate). The badge
// shows a QR code holding a random 6 character code; the phone page posts its GPS fix under
// that code and the badge collects it once:
//
//   POST {"here": CODE, "lat": 37.62, "lon": -122.38, "acc": 12}   store it, answers {"ok":true},
//                                                                  or 503 while 500 positions are waiting
//   GET ?here=CODE                                                 {"lat","lon","acc"}, or 404 until stored
//
// The position waits in public.sky_handoff for 10 minutes and is deleted as it is collected.
//
// Deploy with verify_jwt = false: the aircraft data is public and nobody sends a key. The table
// is not: it has no Data API access, and only this function reaches it, with its own secret key.

import { createClient, type SupabaseClient } from 'npm:@supabase/supabase-js@2.117.2'

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
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

const CODE = /^[A-HJ-KM-NP-Z2-9]{6}$/
const HANDOFF_TTL_MS = 10 * 60_000
const MAX_BODY = 1024
const MAX_WAITING = 500 // positions parked at once: a flood of made-up codes cannot fill the database

// Made on first use, so the aircraft endpoints never depend on the database.
let db: SupabaseClient | undefined
function handoff() {
  db ??= createClient(Deno.env.get('SUPABASE_URL')!, JSON.parse(Deno.env.get('SUPABASE_SECRET_KEYS')!).default)
  return db.from('sky_handoff')
}

const bad = (message: string) => reply(JSON.stringify({ error: message }), 400)
const inRange = (v: unknown, min: number, max: number): v is number => typeof v === 'number' && v >= min && v <= max

// Expired rows go on every valid request, so the table only ever holds the last few minutes.
async function purge() {
  const { error } = await handoff().delete().lt('created_at', new Date(Date.now() - HANDOFF_TTL_MS).toISOString())
  if (error) throw error
}

// The request body as text, or null when it is longer than MAX_BODY bytes. A long body is read
// to the end but not kept: the gateway holds the reply until the whole upload has been consumed.
async function readBody(req: Request) {
  const chunks: Uint8Array<ArrayBuffer>[] = []
  let size = 0
  for await (const chunk of req.body ?? []) {
    size += chunk.length
    if (size <= MAX_BODY) chunks.push(chunk)
  }
  return size > MAX_BODY ? null : new Blob(chunks).text()
}

async function store(req: Request) {
  const text = await readBody(req)
  if (text === null) return bad('body too large')
  let body
  try {
    body = JSON.parse(text)
  } catch (_) {
    return bad('body must be JSON')
  }
  const { here, lat, lon, acc = null } = body ?? {}
  if (typeof here !== 'string' || !CODE.test(here)) return bad('here must be a 6 character code')
  if (!inRange(lat, -90, 90) || !inRange(lon, -180, 180)) return bad('lat and lon must be numbers on Earth')
  if (acc !== null && !inRange(acc, 0, 1e6)) return bad('acc must be a number of metres')

  await purge()
  const { count, error: full } = await handoff().select('*', { count: 'exact', head: true })
  if (full) throw full
  if (count! >= MAX_WAITING) return reply('{"error":"busy"}', 503, { 'Retry-After': '60' })
  // Posting again under the same code replaces the position and restarts its 10 minutes.
  const { error } = await handoff().upsert({
    code: here,
    lat: +lat.toFixed(5), // about a metre
    lon: +lon.toFixed(5),
    acc: acc === null ? null : Math.round(acc),
    created_at: new Date().toISOString(),
  })
  if (error) throw error
  return reply('{"ok":true}')
}

async function claim(code: string) {
  if (!CODE.test(code)) return bad('here must be a 6 character code')
  await purge() // an expired row is gone before the claim looks for it
  // One statement finds, deletes and returns the row, so two badges cannot both collect it.
  const { data, error } = await handoff().delete().eq('code', code).select('lat, lon, acc')
  if (error) throw error
  return data.length ? reply(JSON.stringify(data[0])) : reply('{"error":"waiting"}', 404)
}

async function locate(req: Request, url: URL) {
  let res
  try {
    res = req.method === 'POST' ? await store(req) : await claim(url.searchParams.get('here') ?? '')
  } catch (e) {
    console.error('sky_handoff', e)
    res = reply('{"error":"storage error"}', 500)
  }
  res.headers.set('Cache-Control', 'no-store') // a position is collected once and never cached
  return res
}

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: CORS })
  const url = new URL(req.url)
  if (req.method === 'POST' || (req.method === 'GET' && url.searchParams.has('here'))) return locate(req, url)
  if (req.method !== 'GET') return reply('{"error":"GET or POST only"}', 405)
  const q = parse(url)
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
