# THOR — Dashboard design system & guidelines

**One theme for every THOR surface, taken from the codebase — not re-invented.**
[`dashboard.css`](dashboard.css) is the original THOR watchdog's launch dashboard stylesheet, copied
**verbatim** (714 lines: refined Apple-style tokens, the full `kb-*` kanban, `acard` approval cards,
`feed-row` activity feed, `status-card`s, drawer, toasts). The cockpit and the future mobile surface
both link it, so they share one proven look.

## What was harvested (per the owner's instruction: take the CSS + JS, don't rebuild)
- **CSS:** `dashboard.css` — copied verbatim from `_reference/.thor/dashboard/dashboard.css`.
- **JS idioms:** the proven helpers and render structure from the original (`esc`, `relTime`, the
  fetch/poll loop, and the exact markup each CSS class expects — `kb-col/kb-card`, `acard`,
  `activity/feed-row`, `status-card`, `trust-bar`). The original `dashboard.js` (2096 lines) is bound
  to the old watchdog's API + DOM, so its *mechanisms* were harvested and re-pointed at our
  DashboardAPI rather than copied wholesale.

## Palette / type (tokens in `dashboard.css`)
Warm paper (`--page #EDEBE3`), brand orange (`--brand #E85D1A`), refined status colors
(ok/warn/bad/info), Figtree + JetBrains Mono. Don't introduce new tokens — use these.

## Layout — four quadrants (PM Surface PRD)
**Direct** (kanban) · **Watch** (live rooms + cost) · **Decide** (approval cards) · **Audit**
(ledger feed), under a `trust-bar` + `status-row`. The cockpit adds one small local rule (the 2×2
quad grid); everything else is `dashboard.css` classes.

## Principles (non-negotiable)
1. **A window, not a brain** — reads projections; writes only direction + signatures.
2. **Show the source, not the claim** — the feed footnote says it: *"every row is a signed,
   hash-chained event from the ledger — not the cook's claim."*
3. **Plain language** for the operator (legible refusal, not codes).
4. **Fail loud** — disconnected → red `trust-bar`, signing disabled; never stale-as-live.

## Wired to (our DashboardAPI, `:7080`)
`/state/summary` · `/kanban` · `/rooms/live` · `/cards` · `/audit/feed` · `/cost` · `/findings`
(+ `/dashboard.css` served by the supervisor). Interactive **click-to-Sign** (`POST /approve`) is T7.
