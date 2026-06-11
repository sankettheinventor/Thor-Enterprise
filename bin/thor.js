#!/usr/bin/env node
'use strict'
// THOR Enterprise launcher — ZERO dependencies, NO postinstall, NO network calls. `npm install` runs
// none of this; it executes only when YOU type `thor <cmd>`. It only shells out to `docker compose` with
// the bundled compose file — a security product must not be the weak link in its own install.
// See docs/NPM-SECURITY.md.
const { spawnSync } = require('child_process')
const path = require('path')

const COMPOSE = path.join(__dirname, '..', 'docker-compose.prod.yml')
const cmd = process.argv[2] || 'help'

function docker(args) {
  const r = spawnSync('docker', args, { stdio: 'inherit' })
  if (r.error) {
    console.error('Docker not found. Install Docker first: https://docs.docker.com/get-docker/')
    process.exit(1)
  }
  process.exit(r.status === null ? 1 : r.status)
}

switch (cmd) {
  case 'up':
  case 'start':
    if (!process.env.THOR_API_TOKEN) {
      console.error('Set THOR_API_TOKEN first, e.g.:\n  export THOR_API_TOKEN=$(openssl rand -hex 32)')
      process.exit(1)
    }
    docker(['compose', '-f', COMPOSE, 'up', '-d', '--build'])
    break
  case 'down':
    docker(['compose', '-f', COMPOSE, 'down'])
    break
  case 'status':
    docker(['compose', '-f', COMPOSE, 'ps'])
    break
  case 'logs':
    docker(['compose', '-f', COMPOSE, 'logs', '-f', '--tail=100'])
    break
  default:
    console.log(`THOR Enterprise — governance cage for AI coding agents

  thor up       boot the control plane   (docker compose up -d --build)
  thor status   show service status
  thor logs     follow logs
  thor down     stop everything

Requires Docker. Set THOR_API_TOKEN before \`thor up\` (see DEPLOYMENT.md).
This launcher has ZERO dependencies and NO install scripts — see docs/NPM-SECURITY.md.`)
}
