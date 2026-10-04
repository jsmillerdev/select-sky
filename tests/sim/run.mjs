// Runs a packaged app in the real badge.select simulator, headless, and records what it shows.
// It imports the ZIP in Make through "Open file", presses Run, drives the badge buttons and
// saves 2x screenshots of the badge screen plus the program output.
//
// Setup (once):  cd tests/sim && npm install playwright-core     (uses your installed Chrome)
// usage: node run.mjs <zip> <outDir> "<steps>" [--mock <fixtureDir>] [--headed]
// steps (semicolon separated):
//   wait:MS | key:A|B|C|UP|DOWN | hold:NAME:MS | shot:NAME | out | lights | eval:JS | offline | online
import { chromium } from 'playwright-core'
import fs from 'node:fs'
import path from 'node:path'

const [zip, outDir, steps = 'wait:3000;shot:boot;out', ...flags] = process.argv.slice(2)
const mockDir = flags.includes('--mock') ? flags[flags.indexOf('--mock') + 1] : null
fs.mkdirSync(outDir, { recursive: true })
const KEYS = { A: 'KeyA', B: 'KeyS', C: 'KeyD', UP: 'ArrowUp', DOWN: 'ArrowDown' }
const sleep = ms => new Promise(r => setTimeout(r, ms))

const browser = await chromium.launch({ channel: 'chrome', headless: !flags.includes('--headed') })
const context = await browser.newContext({ viewport: { width: 1400, height: 1000 } })
const page = await context.newPage()
const netlog = []
let offline = false
page.on('console', m => { if (m.type() === 'error') netlog.push('console.error: ' + m.text().slice(0, 300)) })

// Optional deterministic fixtures: <mockDir>/routes.json = [{match: "substring", file: "x.json", status: 200, delay: 0}]
const routes = mockDir ? JSON.parse(fs.readFileSync(path.join(mockDir, 'routes.json'), 'utf8')) : []
await context.route(url => !url.hostname.endsWith('badge.select'), async route => {
  const url = route.request().url()
  if (offline) { netlog.push('OFFLINE ' + url); return route.abort('internetdisconnected') }
  const hit = routes.find(r => url.includes(r.match))
  if (!hit) { netlog.push('LIVE ' + url); return route.continue() }
  netlog.push(`MOCK ${hit.status || 200} ${url}`)
  if (hit.delay) await sleep(hit.delay)
  if (hit.abort) return route.abort('failed')
  if (hit.forward) {                       // relay to a local server from Node (no browser CORS / network limits)
    try {
      const res = await fetch(hit.forward + new URL(url).search)
      return route.fulfill({ status: res.status, headers: Object.fromEntries(res.headers), body: Buffer.from(await res.arrayBuffer()) })
    } catch (e) { netlog.push('FORWARD FAILED ' + e); return route.abort('failed') }
  }
  return route.fulfill({
    status: hit.status || 200,
    headers: { 'access-control-allow-origin': '*', 'content-type': 'application/json' },
    body: hit.file ? fs.readFileSync(path.join(mockDir, hit.file)) : (hit.body || ''),
  })
})

await page.goto('https://badge.select/make', { waitUntil: 'networkidle' })
const chooser = page.waitForEvent('filechooser')
await page.getByRole('button', { name: 'Open file' }).click()
await (await chooser).setFiles(zip)
await page.waitForURL(/make\/editor/, { timeout: 15000 })
const projectName = await page.locator('h1, h2').first().innerText().catch(() => '?')
console.log('imported project:', projectName, '| url:', page.url().replace(/project=[^&]+/, 'project=…'))
await page.locator('button').filter({ hasText: /^Run$/ }).first().click()

const sim = page.frameLocator('iframe[src*="simulator"]')
const frame = () => page.frames().find(f => f.url().includes('/simulator/'))
await sim.locator('#badge-screen').waitFor({ timeout: 20000 })

async function shot(name) {
  const data = await frame().evaluate(() => {
    const c = document.getElementById('badge-screen')
    const scale = c.width <= 160 ? 4 : 2
    const o = document.createElement('canvas')
    o.width = c.width * scale; o.height = c.height * scale
    const g = o.getContext('2d'); g.imageSmoothingEnabled = false
    g.drawImage(c, 0, 0, o.width, o.height)
    return { url: o.toDataURL('image/png'), w: c.width, h: c.height }
  })
  fs.writeFileSync(path.join(outDir, name + '.png'), Buffer.from(data.url.split(',')[1], 'base64'))
  console.log(`shot ${name}.png (${data.w}x${data.h})`)
}

async function dumpOutput() {
  const text = await page.evaluate(() => {
    document.querySelectorAll('details').forEach(d => { d.open = true })
    const d = Array.from(document.querySelectorAll('details')).map(x => x.innerText).join('\n')
    return d || document.body.innerText.slice(-4000)
  })
  const simText = await frame().evaluate(() => ({
    console: document.getElementById('console')?.innerText || '',
    status: document.getElementById('status')?.innerText || '',
    phase: document.getElementById('app-phase')?.innerText || '',
    lights: document.getElementById('app-lights')?.innerText || document.getElementById('case-lights')?.innerText || '',
  }))
  fs.writeFileSync(path.join(outDir, 'output.txt'), text + '\n\n=== SIM ===\n' + JSON.stringify(simText, null, 1) + '\n\n=== NET ===\n' + netlog.join('\n'))
  console.log('output.txt written;', 'phase:', simText.phase, '| status:', simText.status.slice(0, 120))
}

for (const step of steps.split(';').map(s => s.trim()).filter(Boolean)) {
  const [op, a, b] = step.split(':')
  if (op === 'wait') await sleep(+a)
  else if (op === 'key' || op === 'hold') {
    await sim.locator('#badge-screen').focus().catch(() => {})
    await frame().evaluate(([code, ms]) => new Promise(res => {
      window.dispatchEvent(new KeyboardEvent('keydown', { code, key: code, bubbles: true }))
      setTimeout(() => { window.dispatchEvent(new KeyboardEvent('keyup', { code, key: code, bubbles: true })); res() }, ms)
    }), [KEYS[a], op === 'hold' ? +b : 120])
    await sleep(150)
  }
  else if (op === 'shot') await shot(a)
  else if (op === 'out') await dumpOutput()
  else if (op === 'lights') console.log('lights:', await frame().evaluate(() => document.getElementById('case-lights')?.outerHTML.slice(0, 600)))
  else if (op === 'eval') console.log('eval:', JSON.stringify(await frame().evaluate(step.slice(5))))
  else if (op === 'offline') offline = true
  else if (op === 'online') offline = false
  else console.log('unknown step', step)
}
await dumpOutput()
await browser.close()
