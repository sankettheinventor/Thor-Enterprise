# `npm install` security — THOR Enterprise

THOR exists to govern untrusted AI coding agents. It would be self-refuting if installing THOR itself
opened the exact supply-chain hole THOR defends against. This document is the honest threat model for
`npm install` and the concrete posture THOR's npm packages take.

## 1. The threat: why `npm install` is dangerous

`npm install` is not "download some files." By default it can **execute arbitrary code on your machine**
and pull in a large, unreviewed dependency tree:

1. **Lifecycle scripts (`preinstall` / `install` / `postinstall`).** Any package — including a *transitive*
   dependency you never chose — can run a script at install time, with your user's privileges. This is the
   single most common npm attack vector (e.g. `event-stream`, `ua-parser-js`, countless crypto-stealers).
2. **Transitive dependency explosion.** A "small" app can pull 1,000+ packages from hundreds of maintainers.
   Each is a trust decision you didn't consciously make. One compromised maintainer account = code in your tree.
3. **Typosquatting / dependency confusion.** A malicious `thor-enterprize` or an internal name published
   publicly with a higher version can be installed instead of the real one.
4. **Lockfile / integrity drift.** Without a committed lockfile and `npm ci`, `npm install` can silently
   resolve a *different* (newer, possibly compromised) version than what was reviewed.
5. **Post-publish tampering.** A version can be re-published or a maintainer compromised after you first
   audited it.

For a security product, every one of these is a direct contradiction of the product's promise.

## 2. THOR's npm posture (what we actually ship)

THOR ships **two** npm artifacts, both hardened to neutralize the threats above.

### 2a. `thor-enterprise` — the launcher (root `package.json`)
- **ZERO runtime dependencies.** `"dependencies": {}`. There is no transitive tree to compromise (kills
  threats #2, #3, #5 for the launcher entirely).
- **NO lifecycle scripts.** No `postinstall`/`preinstall`/`install`. `npm install thor-enterprise` runs
  **no THOR code at install time** (kills threat #1). `bin/thor.js` runs only when *you* type `thor up`.
- **The launcher does nothing privileged or networked.** It only shells out to `docker compose` with the
  bundled `docker-compose.prod.yml`. It fetches no code, evaluates no remote input.
- **The real engine runs in Docker**, not in Node. So even a hypothetical launcher compromise has a bounded
  blast radius — it cannot reach into the governed control plane, which lives behind container + Postgres
  + the signed ledger.

### 2b. `@thor-enterprise/cockpit` — the React UI (`ui/package.json`)
A browser SPA legitimately needs a build toolchain, so it has dependencies — but they are minimized and pinned:
- **Exact-pinned versions, no `^`/`~` ranges.** `react 18.3.1`, `@noble/ed25519 2.1.0`, `vite 5.4.11`, etc.
  `npm install` cannot silently float to a newer (possibly compromised) version (kills threat #4).
- **The crypto is `@noble/ed25519` + `@noble/hashes`** — audited, **zero-dependency** crypto libraries. The
  signing primitive (the heart of the human-signs authority) pulls in *nothing else*.
- **No `postinstall` in our package.** (Transitive build tooling may have its own; see the operator rules.)
- **The operator's private key never leaves the browser.** It is generated client-side and held in
  `localStorage`; the build pipeline never sees it. A compromised build dependency cannot exfiltrate a key
  it never touches.

## 3. How to install safely (operator rules)

```bash
# Launcher — zero deps, no scripts: safe as-is, but still:
npm install -g thor-enterprise --ignore-scripts

# React UI — install from the COMMITTED lockfile, reproducibly, scripts blocked:
cd ui && npm ci --ignore-scripts && npm run build
```

- **Use `npm ci`, not `npm install`,** for the UI — it installs the exact, reviewed `package-lock.json`
  and fails if anything drifted.
- **`--ignore-scripts`** blocks every lifecycle script in the whole tree (defense in depth against threat #1).
  THOR's own packages need none, so this never breaks THOR.
- **Commit `ui/package-lock.json`** and review changes to it like code — a lockfile diff is a supply-chain diff.
- **Run `npm audit`** on the UI tree and treat new advisories as build-breakers.
- Prefer **published-with-provenance** packages and pin by integrity hash (the lockfile does this).

## 4. The deeper point: THOR governs this attack class for the *agent*

The same supply-chain risk this document is about is one THOR **enforces against the AI worker** at runtime:
a cook inside a room can only reach the network through the **one-door governed gateway** with a host
**allowlist** — so a malicious `postinstall` script the cook pulls in **cannot phone home** (its egress is
denied), and the cook's writes are gated by the Leash. THOR treats `npm install` inside a room as exactly
what it is: untrusted code execution that must be caged. Shipping THOR's *own* installer with zero deps and
no install scripts is the same principle applied to ourselves.

## 5. Summary

| Threat | Launcher (`thor-enterprise`) | React UI (`@thor-enterprise/cockpit`) |
|---|---|---|
| Install-time code execution | None — zero scripts | None in our pkg; `--ignore-scripts` blocks the tree |
| Transitive dependency risk | None — zero deps | Minimized; pinned; audited `@noble` crypto |
| Version drift | N/A | Exact-pinned + `npm ci` from lockfile |
| Key exfiltration | N/A | Key is browser-only; build never sees it |
| Blast radius if compromised | Bounded — engine is in Docker | Bounded — presentation only; Manager re-verifies every signature |

THOR's installer is not the weak link in THOR.
