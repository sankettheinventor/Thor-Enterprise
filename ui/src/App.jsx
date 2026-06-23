import React, { useCallback, useEffect, useState } from 'react'
import { del, get, post } from './api.js'
import { rejectCard, signCard } from './sign.js'
import { enablePush, pushSupported } from './push.js'

const OWNER = 'Sanket'
const isLive = (s) => ['building', 'in_qa'].includes(s)
const inProg = (s) => ['building', 'in_qa', 'awaiting_signature'].includes(s)
const pad2 = (n) => String(n).padStart(2, '0')
const greetWord = () => { const h = new Date().getHours(); return h < 12 ? 'Morning' : h < 17 ? 'Afternoon' : 'Evening' }

export default function App() {
  const [connected, setConnected] = useState(true)
  const [toasts, setToasts] = useState([])
  const [busy, setBusy] = useState('')
  const [d, setD] = useState({ features: [], rooms: [], audit: [], bugs: [], cards: [], health: {}, lies: {}, cost: {} })
  const [view, setView] = useState('home')   // 'home' (CTO) | 'board' (Jira-style kanban)
  const [sel, setSel] = useState(null)       // selected feature_id for the board drawer

  const refresh = useCallback(async () => {
    try {
      const [progress, rooms, audit, bugs, cards, health, lies, cost] = await Promise.all([
        get('/progress'), get('/rooms/live'), get('/audit/feed'), get('/bugs'),
        get('/cards'), get('/health/system'), get('/lies'), get('/cost').catch(() => ({})),
      ])
      setD({
        features: progress.features || [], rooms: rooms.rooms || rooms || [],
        audit: audit.events || audit || [], bugs: bugs.bugs || [], cards: cards.cards || cards || [],
        health: health || {}, lies: lies || {}, cost: cost || {},
      })
      setConnected(true)
    } catch { setConnected(false) }
  }, [])

  useEffect(() => {
    refresh()
    let es
    try {
      es = new EventSource('/stream')
      es.addEventListener('hello', () => setConnected(true))
      es.onmessage = () => refresh()
      es.onerror = () => setConnected(false)
    } catch { /* polling carries it */ }
    const t = setInterval(refresh, 8000)
    return () => { if (es) es.close(); clearInterval(t) }
  }, [refresh])

  const toast = (msg) => { const id = Math.random(); setToasts((t) => [...t, { id, msg }]); setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3200) }
  const featureOf = (fid) => d.features.find((f) => f.feature_id === fid)
  const titleOf = (fid) => featureOf(fid)?.title || fid

  const act = {
    sign: async (cardId, fid) => { if (!connected) return; setBusy(cardId); const r = await signCard(cardId); setBusy(''); toast(r.verified ? `Signed ${fid} — merged` : `Rejected: ${r.reason || 'verification failed'}`); refresh() },
    reject: async (cardId, fid) => { if (!connected) return; setBusy(cardId); const r = await rejectCard(cardId); setBusy(''); toast(r.verified ? `Declined ${fid}` : `Rejected: ${r.reason || '?'}`); refresh() },
    newTask: async () => { const t = window.prompt('New task — feature title:'); if (t && t.trim()) { const r = await post('/features', { title: t.trim() }); toast(r.feature_id ? `Created ${r.feature_id}` : 'Failed'); refresh() } },
    stop: async (fid) => { await post(`/features/${fid}/stop`); toast(`Stopped ${fid}`); refresh() },
    prioritize: async (fid, p) => { await post('/commands/prioritize', { feature_id: fid, priority: p }); toast(`Priority → P${p}`); refresh() },
    markReady: async (fid) => { await post('/commands/mark_ready', { feature_id: fid }); toast('Marked ready — Scheduler will pick it up'); refresh() },
  }

  // ---- derived metrics (all from real endpoints) ----
  const openCards = d.cards.filter((c) => (c.status || 'open') === 'open')
  const liveFeatures = d.features.filter((f) => isLive(f.status))
  const liveIds = liveFeatures.map((f) => f.feature_id)
  const metaTrust = d.health.self_audit_meta_trust != null ? Math.round(d.health.self_audit_meta_trust * 100) : null
  const lies = d.lies.total ?? 0
  const inProgress = d.features.filter((f) => inProg(f.status)).length
  const done = d.features.filter((f) => f.status === 'done').length
  const stub = d.features.filter((f) => ['backlog', 'ready'].includes(f.status || 'backlog')).length
  const halted = d.health.sentinel?.halted
  const blocks = d.audit.filter((e) => e.event_type === 'action.decided').length
  const budget = d.cost?.budget_used_pct ?? d.cost?.used_pct ?? null
  const sessions = liveFeatures.length ? liveFeatures : d.features.filter((f) => f.status === 'awaiting_signature')

  return (
    <div className="cto">
      <header className="cto-top">
        <button className="cto-logo-m" aria-label="THOR"><Bolt /></button>
        <div className="cto-title">THOR Enterprise<span className="slash">/CTO</span></div>
        <div className="cto-top-right">
          <button className="ghost-btn" onClick={act.newTask}>+ New</button>
          <span className={`conn ${connected ? '' : 'off'}`}><span className="conn-dot" />Thor<span className="conn-sep">·</span><span className="conn-state">{connected ? 'Connected' : 'Offline'}</span></span>
        </div>
      </header>

      <div className="cto-body">
        <nav className="rail">
          <div className="rail-logo"><Bolt /></div>
          <button className={`rail-ico ${view === 'home' ? 'active' : ''}`} title="Home" onClick={() => setView('home')}><Home /></button>
          <button className={`rail-ico ${view === 'board' ? 'active' : ''}`} title="Board" onClick={() => setView('board')}><BoardIcon /></button>
          {pushSupported() && <button className="rail-ico" title="Notifications" onClick={async () => { const r = await enablePush(); toast(r.ok ? 'Notifications on' : `Push: ${r.reason}`) }}>🔔</button>}
          <div className="rail-foot"><div className="rail-avatar">{OWNER[0]}</div></div>
        </nav>

        {view === 'board'
          ? <Board features={d.features} owner={OWNER} rooms={d.rooms} cards={d.cards} sel={sel} setSel={setSel} act={act} />
          : <>
        <main className="cto-main">
          <h1 className="greeting">{greetWord()}, {OWNER}</h1>
          <p className="greet-sub">
            You have <b className="o">{openCards.length} decision{openCards.length === 1 ? '' : 's'}</b> waiting
            {liveIds.length > 0
              ? <> and the agent is multi-tasking on <b className="g">Task — {liveIds.slice(0, 4).join(', ')}</b></>
              : <> and the agent is <b className="g">idle — assign a task</b></>}
          </p>

          <section className="statpanel">
            <Stat n={pad2(openCards.length)} label="Decision waiting for you" />
            <Stat n={metaTrust != null ? `${metaTrust}%` : '—'} label="System meta trust" />
            <Stat n={`${lies}`} label="Lies caught" tone={lies > 0 ? 'red' : ''} />
            <Stat n={`${inProgress}`} label="In progress task" />
          </section>

          <Section title="Need your decisions" accent={openCards.length ? `· ${openCards.length} decision${openCards.length === 1 ? '' : 's'} today` : ''}>
            {openCards.length === 0
              ? <div className="cto-empty">Nothing needs your signature right now. THOR is governing.</div>
              : openCards.map((c) => (
                <Decision key={c.card_id} card={c} title={titleOf(c.feature_id)} feature={featureOf(c.feature_id)}
                  busy={busy === c.card_id} connected={connected} act={act} />
              ))}
          </Section>

          <Section title="Featured status">
            <div className="featured">
              <div className="featured-row">
                <Fcard label="Done" n={done} tone="green" />
                <Fcard label="In Progress" n={inProgress} tone="orange" />
                <Fcard label="Stub" n={stub} />
              </div>
              <div className="featured-caps">
                <span>Done = merged features</span>
                <span>Counts come from the manager's Kanban</span>
                <span>In Progress = Building / QA / awaiting signature</span>
              </div>
            </div>
          </Section>
        </main>

        <aside className="session">
          <div className="session-label">Active Session</div>
          {sessions.length === 0
            ? <div className="session-empty">No live session.<br />Assign a task to wake the agent.</div>
            : sessions.slice(0, 8).map((f, i) => (
              <button key={f.feature_id} className={`scard ${i === 0 && isLive(f.status) ? 'hot' : ''}`}
                onClick={() => isLive(f.status) && act.stop(f.feature_id)} title={isLive(f.status) ? 'Click to stop' : ''}>
                <div className="scard-top"><span className="scard-id">{f.feature_id}</span><span className="scard-sep">·</span><span className="scard-agent">Claude</span>
                  {isLive(f.status) && <span className="scard-live"><span className="dot" />live</span>}
                </div>
                <div className="scard-title">{f.title}</div>
              </button>
            ))}
        </aside>
        </>}
      </div>

      <footer className="cto-foot">
        <span className={`foot-item ${halted ? 'bad' : ''}`}><span className={`fdot ${halted ? 'bad' : 'ok'}`} />{halted ? 'Watchdog HALTED' : 'Watchdog active'}</span>
        <i>·</i><span className="foot-item">4 Layers</span>
        <i>·</i><span className="foot-item">{blocks} Blocks Today</span>
        <i>·</i><span className="foot-item"><span className={`fdot ${liveIds.length ? 'ok' : 'idle'}`} />{liveIds.length ? 'Claude Session Live' : 'Agent idle'}</span>
        {liveIds.length ? <><i>·</i><span className="foot-item">{liveIds[0]}</span></> : null}
        {budget != null ? <><i>·</i><span className="foot-item">{Math.round(budget)}% Budget</span></> : null}
      </footer>

      <div className="toast-wrap">{toasts.map((t) => <div key={t.id} className="toast">{t.msg}</div>)}</div>
    </div>
  )
}

/* ---------- presentational ---------- */
const Stat = ({ n, label, tone }) => (
  <div className="stat">
    <div className={`stat-n ${tone || ''}`}>{n}</div>
    <div className={`stat-l ${tone || ''}`}>{label}</div>
  </div>
)

const Section = ({ title, accent, children }) => (
  <section className="cto-sec">
    <div className="sec-head">
      <div className="sec-title">{title}{accent ? <span className="sec-accent"> {accent}</span> : null}</div>
      <button className="viewall">View All ›</button>
    </div>
    {children}
  </section>
)

const Fcard = ({ label, n, tone }) => (
  <div className="fcard">
    <div className={`fcard-l ${tone || ''}`}>{label}</div>
    <div className="fcard-n">{n}</div>
  </div>
)

function Decision({ card, title, feature, busy, connected, act }) {
  const kind = (card.type || 'merge').toLowerCase()
  const tag = kind.includes('depend') ? { cls: 'dep', ico: '📦', label: 'Dependency' }
    : kind.includes('merge') ? { cls: 'merge', ico: '◆', label: 'Merge' }
      : { cls: 'maint', ico: '●', label: kind }
  return (
    <article className="dcard">
      <span className={`dtag ${tag.cls}`}><span className="dtag-ico">{tag.ico}</span>{tag.label}</span>
      <h3 className="dcard-title">{title}</h3>
      <p className="dcard-desc">
        THOR's verdict passed against reality — your signature merges this into <b>main</b>.
        {feature?.open_bugs ? ` ${feature.open_bugs} open bug flagged.` : ' No open bugs.'}
      </p>
      <div className="dcard-meta">
        <Meta ico="◷" text={`Pending · ${card.feature_id}`} />
        <Meta ico="◰" text={feature ? feature.title.slice(0, 22) : 'feature'} />
        <Meta ico="◳" text={`card ${String(card.card_id).slice(0, 8)}`} />
      </div>
      <div className="dcard-acts">
        <button className="btn-black" disabled={!connected || busy} onClick={() => act.sign(card.card_id, card.feature_id)}>{busy ? 'Signing…' : 'Approve'}</button>
        <button className="btn-out" disabled={!connected || busy} onClick={() => act.reject(card.card_id, card.feature_id)}>Reject</button>
      </div>
    </article>
  )
}
const Meta = ({ ico, text }) => <span className="dmeta"><span className="dmeta-ico">{ico}</span>{text}</span>

/* ---------- Jira-style board view (PRD Module 8: catalog as columns, read-and-sign over the Manager) ---------- */
const BOARD_COLS = [
  { key: 'backlog', label: 'Backlog', tone: 'grey' },
  { key: 'ready', label: 'Ready', tone: 'blue' },
  { key: 'building', label: 'In Progress', tone: 'orange' },
  { key: 'in_qa', label: 'In QA', tone: 'purple' },
  { key: 'awaiting_signature', label: 'Your Call', tone: 'amber' },
  { key: 'done', label: 'Done', tone: 'green' },
]
const COL_OF = { backlog: 'backlog', ready: 'ready', building: 'building', working: 'building', in_qa: 'in_qa', qa: 'in_qa', awaiting_signature: 'awaiting_signature', merge_pending: 'awaiting_signature', done: 'done', merged: 'done' }
const colOf = (s) => COL_OF[s || 'backlog'] || 'backlog'
const prioLabel = (p) => (p == null ? 'P2' : p <= 1 ? 'P0' : p === 2 ? 'P1' : 'P2')
const prioCls = (p) => (p == null ? 'p2' : p <= 1 ? 'p0' : p === 2 ? 'p1' : 'p2')
// sample task breakdown + QA cases until Genesis fills the real ones (the structure the planner will populate)
const tasksFor = (f) => f.tasks || [
  { id: 't1', title: 'Design + acceptance criteria', status: (f.stage ?? 0) >= 1 ? 'done' : 'todo' },
  { id: 't2', title: `Implement ${f.title || f.feature_id}`, status: (f.stage ?? 0) >= 2 ? 'done' : (f.stage === 1 ? 'doing' : 'todo') },
  { id: 't3', title: 'Write tests', status: (f.stage ?? 0) >= 3 ? 'done' : 'todo' },
  { id: 't4', title: 'QA + verdict', status: (f.stage ?? 0) >= 4 ? 'done' : 'todo' },
  { id: 't5', title: 'Sign + merge', status: f.status === 'done' ? 'done' : 'todo' },
]
const qaFor = (f) => f.qa_cases || ['Happy path returns the expected output', 'Invalid input is rejected', 'Edge cases handled', 'No regression in existing behaviour']

function Board({ features, owner, sel, setSel, act }) {
  const byCol = {}; BOARD_COLS.forEach((c) => (byCol[c.key] = []))
  features.forEach((f) => byCol[colOf(f.status)].push(f))
  const selF = features.find((f) => f.feature_id === sel)
  return (
    <main className="board-view">
      <div className="board-head2">
        <div className="board-title2">Project Board <span className="muted">· {features.length} features · sample tasks until Genesis</span></div>
        <button className="ghost-btn" onClick={act.newTask}>+ Feature</button>
      </div>
      <div className="board-grid">
        {BOARD_COLS.map((col) => (
          <div key={col.key} className="bcol">
            <div className="bcol-head"><span className={`bdot ${col.tone}`} />{col.label}<span className="bcol-n">{byCol[col.key].length}</span></div>
            <div className="bcol-body">
              {byCol[col.key].length === 0
                ? <div className="bcol-empty">—</div>
                : byCol[col.key].map((f) => {
                  const tasks = tasksFor(f); const doneN = tasks.filter((t) => t.status === 'done').length
                  return (
                    <button key={f.feature_id} className="bcard" onClick={() => setSel(f.feature_id)}>
                      <div className="bcard-top"><span className={`prio-chip ${prioCls(f.priority)}`}>{prioLabel(f.priority)}</span><span className="bcard-id">{f.feature_id}</span></div>
                      <div className="bcard-title">{f.title || f.feature_id}</div>
                      <div className="bcard-tasks"><div className="bcard-bar"><div className="bcard-fill" style={{ width: `${Math.round(100 * doneN / tasks.length)}%` }} /></div><span>{doneN}/{tasks.length}</span></div>
                      <div className="bcard-foot">
                        <span className="assignee" title="Assignee: Claude (cook)">C</span>
                        <span className="watcher" title={`Watcher (commander): ${owner}`}>{owner[0]}</span>
                        {f.open_bugs > 0 ? <span className="bug-chip">{f.open_bugs} bug</span> : null}
                      </div>
                    </button>
                  )
                })}
            </div>
          </div>
        ))}
      </div>
      <BoardDrawer f={selF} owner={owner} act={act} close={() => setSel(null)} />
    </main>
  )
}

function BoardDrawer({ f, owner, act, close }) {
  const tasks = f ? tasksFor(f) : []; const qa = f ? qaFor(f) : []
  return (
    <>
      <div className={`scrim ${f ? 'open' : ''}`} onClick={close} />
      <aside className={`bdrawer ${f ? 'open' : ''}`}>
        {f && (
          <>
            <div className="bdrawer-head">
              <div className="bdrawer-crumb"><span>Board</span><span>/</span><span>{f.feature_id}</span><button className="drawer-close" onClick={close}>✕</button></div>
              <div className="bdrawer-title">{f.title || f.feature_id}</div>
              <div className="bdrawer-meta">
                <span className={`prio-chip ${prioCls(f.priority)}`}>{prioLabel(f.priority)}</span>
                <span className="dpill"><span className="label">status</span>{f.status || 'backlog'}</span>
                <span className="dpill"><span className="label">assignee</span>Claude</span>
                <span className="dpill"><span className="label">watcher</span>{owner} · commander</span>
              </div>
            </div>
            <div className="bdrawer-body">
              <div className="bsec"><div className="bsec-h">Tasks <span className="muted">(sample — Genesis will generate)</span></div>
                {tasks.map((t) => <div key={t.id} className={`task-row ${t.status}`}><span className="task-dot" /><span className="task-t">{t.title}</span><span className="task-st">{t.status}</span></div>)}
              </div>
              <div className="bsec"><div className="bsec-h">QA test cases</div>
                {qa.map((q, i) => <div key={i} className="qa-row">✓ {q}</div>)}
              </div>
              <div className="bsec"><div className="bsec-h">Priority &amp; direction</div>
                <div className="actions-row2">
                  {['P0', 'P1', 'P2'].map((p, i) => <button key={p} className={`btn-out ${prioCls(f.priority) === p.toLowerCase() ? 'on' : ''}`} onClick={() => act.prioritize(f.feature_id, i === 0 ? 0 : i === 1 ? 2 : 3)}>{p}</button>)}
                  <button className="btn-black" onClick={() => { act.markReady(f.feature_id); close() }}>Mark ready</button>
                </div>
              </div>
            </div>
          </>
        )}
      </aside>
    </>
  )
}
const BoardIcon = () => (<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="7" height="18" rx="1" /><rect x="14" y="3" width="7" height="11" rx="1" /></svg>)
const Bolt = () => (<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M13 2 4 14h6l-1 8 9-12h-6l1-8z" /></svg>)
const Home = () => (<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 11l9-8 9 8" /><path d="M5 10v10h14V10" /></svg>)
