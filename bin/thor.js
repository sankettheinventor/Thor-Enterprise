#!/usr/bin/env node
'use strict'
// THOR Enterprise launcher — ZERO dependencies, NO postinstall, NO network calls at install time. `npm
// install` runs none of this; it executes only when YOU type `thor <cmd>`. A security product must not be
// the weak link in its own install. See docs/NPM-SECURITY.md.
//
// First-run UX goal: the user provides only (a) Docker, (b) a Claude login, (c) their repo. Everything else
// — the room/cook images, the Python env, Postgres — THOR sets up itself. `thor doctor` checks every
// requirement and AUTO-FIXES what it can (builds images, creates the venv); `thor run <repo>` preflights
// then governs your project.
const { spawnSync } = require('child_process')
const fs = require('fs')
const path = require('path')
const os = require('os')

const ROOT = path.join(__dirname, '..')
const COMPOSE = path.join(ROOT, 'docker-compose.prod.yml')
const cmd = process.argv[2] || 'help'

const C = { g: '\x1b[32m', r: '\x1b[31m', y: '\x1b[33m', b: '\x1b[1m', d: '\x1b[2m', x: '\x1b[0m' }
const ok = (s) => console.log(`  ${C.g}✓${C.x} ${s}`)
const bad = (s) => console.log(`  ${C.r}✗${C.x} ${s}`)
const work = (s) => console.log(`  ${C.y}…${C.x} ${s}`)

function run(bin, args, opts = {}) {
  return spawnSync(bin, args, { stdio: opts.quiet ? 'pipe' : 'inherit', cwd: ROOT, encoding: 'utf8', ...opts })
}
function have(bin, args = ['--version']) {
  const r = spawnSync(bin, args, { stdio: 'pipe', encoding: 'utf8' })
  return r.status === 0
}
function imageExists(tag) {
  const r = spawnSync('docker', ['images', '-q', tag], { stdio: 'pipe', encoding: 'utf8' })
  return r.status === 0 && r.stdout.trim().length > 0
}
function claudeLogin() {
  const home = path.join(os.homedir(), '.claude', '.credentials.json')
  if (fs.existsSync(home)) return true
  if (process.env.CLAUDE_CODE_OAUTH_TOKEN) return true
  // a Windows login seen from WSL
  try {
    const base = '/mnt/c/Users'
    if (fs.existsSync(base)) {
      for (const u of fs.readdirSync(base)) {
        if (fs.existsSync(path.join(base, u, '.claude', '.credentials.json'))) return true
      }
    }
  } catch { /* ignore */ }
  return false
}

// returns true when the system is READY (all hard requirements met). Auto-fixes images + venv.
function doctor({ fix = true } = {}) {
  console.log(`${C.b}THOR doctor — checking your system${C.x}\n`)
  let ready = true

  // 1) Docker — the one thing we cannot install for you (needs system privileges)
  if (have('docker', ['info'])) ok('Docker is running')
  else {
    bad('Docker not running. Install + start Docker, then re-run:')
    console.log(`      ${C.d}https://docs.docker.com/get-docker/  (on Windows: Docker Desktop + WSL integration)${C.x}`)
    return false   // nothing else works without Docker
  }

  // 2) cook/verdict image — AUTO-BUILD if missing (this is the "download the system" step)
  if (imageExists('thor-room-claude:latest')) ok('Cook image thor-room-claude:latest')
  else if (fix) {
    work('Building cook image thor-room-claude:latest (first run — a few minutes)…')
    const r = run('docker', ['build', '-f', 'wall/image/Dockerfile.claude', '-t', 'thor-room-claude:latest', '.'])
    if (r.status === 0) ok('Built thor-room-claude:latest')
    else { bad('Failed to build cook image (see output above)'); ready = false }
  } else { bad('Cook image missing — run `thor doctor`'); ready = false }

  // 3) base room image — AUTO-BUILD if missing
  if (imageExists('thor-room:dev')) ok('Base room image thor-room:dev')
  else if (fix) {
    work('Building base room image thor-room:dev…')
    const r = run('docker', ['build', '-f', 'wall/image/Dockerfile', '-t', 'thor-room:dev', '.'])
    if (r.status === 0) ok('Built thor-room:dev')
    else { bad('Failed to build base room image'); ready = false }
  } else { bad('Base room image missing'); ready = false }

  // 4) Python env — AUTO-CREATE if missing
  const py = path.join(ROOT, '.venv', 'bin', 'python')
  const venvOk = fs.existsSync(py) &&
    spawnSync(py, ['-c', 'import fastapi,psycopg,docker,cryptography'], { stdio: 'pipe' }).status === 0
  if (venvOk) ok('Python control plane (.venv + deps)')
  else if (fix && have('python3')) {
    work('Creating Python venv + installing deps…')
    run('python3', ['-m', 'venv', '.venv'])
    const r = run(py, ['-m', 'pip', 'install', '-q', '-r', 'requirements.txt'])
    if (r.status === 0) ok('Python env ready')
    else { bad('Failed to install Python deps'); ready = false }
  } else { bad('Python 3 + venv needed (apt install python3 python3-venv)'); ready = false }

  // 5) Claude login — the cook reuses your subscription (no API cost). Cannot auth for you.
  if (claudeLogin()) ok('Claude login found (the cook — no API cost)')
  else {
    bad('No Claude login. Log into Claude Code, then THOR auto-discovers it:')
    console.log(`      ${C.d}run \`claude\` once and sign in, OR: export CLAUDE_CODE_OAUTH_TOKEN=$(claude setup-token)${C.x}`)
    ready = false
  }

  console.log('')
  if (ready) console.log(`${C.g}${C.b}READY${C.x} — run:  ${C.b}thor run <path-to-your-git-repo>${C.x}`)
  else console.log(`${C.y}Not ready yet — fix the ✗ above and re-run \`thor doctor\`.${C.x}`)
  return ready
}

function runProject(project) {
  if (!project) { console.error('usage: thor run <path-to-your-git-repo>'); process.exit(1) }
  if (!doctor({ fix: true })) process.exit(1)
  console.log('')
  const r = spawnSync('bash', [path.join(ROOT, 'tools', 'thor-up.sh'), project], { stdio: 'inherit', cwd: ROOT })
  process.exit(r.status === null ? 1 : r.status)
}

function compose(args, requireToken = false) {
  if (requireToken && !process.env.THOR_API_TOKEN) {
    console.error('Set THOR_API_TOKEN first:  export THOR_API_TOKEN=$(openssl rand -hex 32)')
    process.exit(1)
  }
  if (!have('docker', ['info'])) { console.error('Docker not running — see `thor doctor`.'); process.exit(1) }
  const r = spawnSync('docker', ['compose', '-f', COMPOSE, ...args], { stdio: 'inherit' })
  process.exit(r.status === null ? 1 : r.status)
}

switch (cmd) {
  case 'doctor': process.exit(doctor({ fix: true }) ? 0 : 1); break
  case 'run': runProject(process.argv[3]); break
  case 'up': case 'start': compose(['up', '-d', '--build'], true); break
  case 'down': compose(['down']); break
  case 'status': compose(['ps']); break
  case 'logs': compose(['logs', '-f', '--tail=100']); break
  default:
    console.log(`${C.b}THOR Enterprise — governance cage for AI coding agents${C.x}

  ${C.b}thor doctor${C.x}        check your system + AUTO-BUILD anything missing (run this first)
  ${C.b}thor run <repo>${C.x}    govern your project (preflights, then live-watch in the cockpit)

  thor up            production boot via docker compose (detached; needs THOR_API_TOKEN)
  thor status|logs|down   docker compose lifecycle

First run: you provide only (1) Docker, (2) a Claude login, (3) your git repo — THOR builds the
rest itself. Then open http://localhost:7080/ to watch + sign. Zero install scripts (docs/NPM-SECURITY.md).`)
}
