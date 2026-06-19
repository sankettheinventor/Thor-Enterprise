import React, { useCallback, useEffect, useState } from 'react'
import { del, get, post } from './api.js'
import { rejectCard, signCard } from './sign.js'
import { enablePush, pushSupported } from './push.js'

// our SDLC statuses -> board columns
const COLUMNS = [
  { key: 'backlog', label: 'Backlog', dot: 'var(--ink-4)', has: (s) => ['backlog', 'ready'].includes(s) },
  { key: 'building', label: 'Building', dot: 'var(--tag-feature)', has: (s) => ['building', 'in_qa'].includes(s) },
  { key: 'sign', label: 'Your call', dot: 'var(--warn)', has: (s) => s === 'awaiting_signature' },
  { key: 'done', label: 'Shipped', dot: 'var(--ok)', has: (s) => s === 'done' },
]
const STATUS_LABEL = { backlog: 'Backlog', ready: 'Ready', building: 'Building', in_qa: 'QA', awaiting_signature: 'Awaiting you', done: 'Shipped' }
const PRIOS = [['P0', 0], ['P1', 1], ['P2', 2], ['P3', 3]]
const isLive = (s) => ['building', 'in_qa'].includes(s)

export default function App() {
  const [connected, setConnected] = useState(true)
  const [healthOpen, setHealthOpen] = useState(false)
  const [sel, setSel] = useState(null)        // selected feature_id
  const [tab, setTab] = useState('overview')
  const [search, setSearch] = useState('')
  const [prio, setPrio] = useState(new Set())
  const [toasts, setToasts] = useState([])
  const [d, setD] = useState({ features: [], rooms: [], activity: {}, audit: [], bugs: [], cards: [], health: {}, lies: {} })

  const refresh = useCallback(async () => {
    try {
      const [progress, rooms, activity, audit, bugs, cards, health, lies] = await Promise.all([
        get('/progress'), get('/rooms/live'), get('/rooms/activity'), get('/audit/feed'),
        get('/bugs'), get('/cards'), get('/health/system'), get('/lies'),
      ])
      setD({
        features: progress.features || [], rooms: rooms.rooms || rooms || [], activity: activity || {},
        audit: audit.events || audit || [], bugs: bugs.bugs || [], cards: cards.cards || cards || [],
        health: health || {}, lies: lies || {},
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

  const toast = (msg) => { const id = Math.random(); setToasts((t) => [...t, { id, msg }]); setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3500) }

  // helpers
  const roomFor = (fid) => d.rooms.find((r) => r.feature_id === fid)
  const filesFor = (fid) => { const r = roomFor(fid); return (r && d.activity[r.room_id]) || [] }
  const cardFor = (fid) => d.cards.find((c) => c.feature_id === fid && (c.status || 'open') === 'open')

  const act = {
    prioritize: async (fid, p) => { await post('/commands/prioritize', { feature_id: fid, priority: p }); toast(`Priority → P${p}`); refresh() },
    markReady: async (fid) => { await post('/commands/mark_ready', { feature_id: fid }); toast('Marked ready'); refresh() },
    stop: async (fid) => { await post(`/features/${fid}/stop`); toast(`Stopped ${fid}`); refresh() },
    remove: async (fid) => { if (!window.confirm(`Remove ${fid}? Recorded in the ledger.`)) return; await del(`/features/${fid}`); setSel(null); toast(`Removed ${fid}`); refresh() },
    sign: async (fid) => { const c = cardFor(fid); if (!c || !connected) return; const r = await signCard(c.card_id); toast(r.verified ? `Signed ${fid}` : `Rejected: ${r.reason || '?'}`); refresh() },
    reject: async (fid) => { const c = cardFor(fid); if (!c || !connected) return; const r = await rejectCard(c.card_id); toast(r.verified ? `Declined ${fid}` : `Rejected: ${r.reason || '?'}`); refresh() },
    newTask: async () => { const t = window.prompt('New task — feature title:'); if (t && t.trim()) { const r = await post('/features', { title: t.trim() }); toast(r.feature_id ? `Created ${r.feature_id}` : 'Failed'); refresh() } },
  }

  // filter
  const visible = d.features.filter((f) => {
    if (prio.size && !prio.has(f.priority)) return false
    if (search.trim()) { const q = search.toLowerCase(); if (!`${f.feature_id} ${f.title}`.toLowerCase().includes(q)) return false }
    return true
  })

  const h = d.health || {}; const alarms = h.sentinel?.alarms ?? 0; const halted = h.sentinel?.halted
  const healthClass = halted ? 'alert' : alarms ? 'warn' : ''
  const shipped = d.features.filter((f) => f.status === 'done').length
  const live = d.features.filter((f) => isLive(f.status)).length
  const openCards = d.cards.filter((c) => (c.status || 'open') === 'open').length

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand"><div className="brand-logo">T</div><div className="brand-name">THOR</div></div>
        <div className="side-label">Workspace</div>
        <div className="nav-item active">Task Board</div>
        <div className="nav-item">Your call<span className="nav-count">{d.cards.filter((c) => (c.status || 'open') === 'open').length}</span></div>
        <div className="nav-item">Bugs<span className="nav-count">{d.bugs.length}</span></div>
        {pushSupported() && <div className="nav-item" onClick={async () => { const r = await enablePush(); toast(r.ok ? 'Notifications on' : `Push: ${r.reason}`) }}>🔔 Notifications</div>}
        <div className="side-foot"><div className="side-avatar">S</div><div style={{ fontWeight: 500 }}>You</div></div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div className="brand"><div className="brand-logo">T</div><div className="brand-name">THOR</div></div>
          <div className="topbar-actions">
            {openCards > 0 && <span className="topbar-pill">Your call · {openCards}</span>}
            {pushSupported() && <button className="topbar-icon" aria-label="Notifications" onClick={async () => { const r = await enablePush(); toast(r.ok ? 'Notifications on' : `Push: ${r.reason}`) }}>🔔</button>}
            <button className="btn btn-primary" onClick={act.newTask}>+ New</button>
          </div>
        </header>
        <div className={`health ${healthClass}`} onClick={() => setHealthOpen((v) => !v)}>
          <div className="health-dot" />
          <div className="health-mid truncate">
            <strong>{halted ? 'HALTED — a governor failed.' : alarms ? `${alarms} alarm — review.` : 'All systems nominal.'}</strong>
            <span className="muted"> THOR is governing · {live} live · {connected ? 'synced' : 'disconnected'}</span>
          </div>
          <div className="health-meta">{connected ? 'live' : 'stale'}</div>
        </div>
        <div className={`health-drawer ${healthOpen ? 'open' : ''}`}>
          <div className="health-grid">
            <Meter name="Sentinel" pill={halted ? 'halted' : 'alive'} warn={halted} sub={`fail-closed: ${h.sentinel?.fail_closed ? 'yes' : 'no'}`} />
            <Meter name="Alarms" pill={`${alarms}`} warn={!!alarms} sub="canary checks" />
            <Meter name="Auditor" pill={(h.selfaudit?.model || 'deterministic').slice(0, 10)} sub={`frontier $: ${h.selfaudit?.frontier_calls ?? 0}`} />
            <Meter name="Meta-trust" pill={h.meta_trust != null ? `${Math.round(h.meta_trust * 100)}%` : '—'} sub="self-audit" />
            <Meter name="Your call" pill={`${d.cards.filter((c) => (c.status || 'open') === 'open').length}`} sub="cards waiting" />
            <Meter name="Live rooms" pill={`${d.rooms.length}`} sub="sealed rooms" />
          </div>
        </div>

        <div className="board-head">
          <div className="board-title">Task Board <span className="muted">· {d.features.length} tasks · {shipped} shipped</span></div>
          <div className="board-actions">
            {!connected && <span className="dpill" style={{ color: 'var(--alert)' }}>signing disabled</span>}
            <button className="btn btn-primary" onClick={act.newTask}>+ New task</button>
          </div>
        </div>

        <div className="filter-bar">
          {PRIOS.map(([lbl, p]) => (
            <button key={p} className={`filter-pill ${prio.has(p) ? 'active' : ''}`} onClick={() => setPrio((s) => { const n = new Set(s); n.has(p) ? n.delete(p) : n.add(p); return n })}>{lbl}</button>
          ))}
          <div className="filter-search">
            <input placeholder="Search tasks…" value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
        </div>

        <div className="board">
          {COLUMNS.map((col) => {
            const items = visible.filter((f) => col.has(f.status))
            const liveN = items.filter((f) => isLive(f.status)).length
            return (
              <div key={col.key} className="column">
                <div className="column-head">
                  <div className="column-title"><span className="column-dot" style={{ background: col.dot }} />{col.label}</div>
                  <span className={`column-count ${liveN ? 'live' : ''}`}>{liveN ? `${liveN} live` : items.length}</span>
                </div>
                <div className="column-body">
                  {items.length === 0
                    ? <div className="column-empty">{search || prio.size ? 'No match' : col.key === 'backlog' ? 'Assign a task' : 'Empty'}</div>
                    : items.map((f) => <Card key={f.feature_id} f={f} files={filesFor(f.feature_id)} connected={connected} act={act} open={(id) => { setSel(id); setTab('overview') }} />)}
                </div>
              </div>
            )
          })}
        </div>
      </main>

      <Drawer fid={sel} d={d} tab={tab} setTab={setTab} connected={connected} act={act}
        roomFor={roomFor} filesFor={filesFor} cardFor={cardFor} close={() => setSel(null)} />

      <div className="toast-wrap">{toasts.map((t) => <div key={t.id} className="toast">{t.msg}</div>)}</div>
    </div>
  )
}

const Meter = ({ name, pill, sub, warn }) => (
  <div className="meter"><div className="meter-head"><span>{name}</span><span className={`meter-pill ${warn ? 'warn' : ''}`}>{pill}</span></div><div className="meter-sub truncate">{sub}</div></div>
)
const prioClass = (p) => `prio p${p ?? 3}`
const ownerOf = (f) => (isLive(f.status) ? 'claude' : 'human')
const avChar = (o) => (o === 'claude' ? 'C' : o === 'cto' ? '◆' : 'S')

function Card({ f, files, connected, act, open }) {
  const live = isLive(f.status)
  const curFile = live ? (files.find((a) => a.decision === 'allow') || files[0])?.file : null
  const alarm = f.open_bugs > 0 && live
  return (
    <div className={`card ${live ? 'live' : ''} ${f.status === 'done' ? 'done' : ''} ${alarm ? 'alarm' : ''}`} onClick={() => open(f.feature_id)}>
      <div className="card-top">
        <span className="tag feature">feature</span>
        <span className={prioClass(f.priority)}>P{f.priority ?? 3}</span>
      </div>
      <div className="card-title clamp-2">{f.title}</div>
      {live && (
        <>
          <div className="progress"><div className="progress-fill" style={{ width: `${f.progress}%` }} /></div>
          <div className="live-bar"><span className="live-bar-dot" /><span className="live-bar-file" title={curFile || ''}>{curFile || STATUS_LABEL[f.status]}</span></div>
        </>
      )}
      {alarm && <div className="card-alert"><span className="card-alert-ico">!</span><span>{f.open_bugs} open bug — review</span></div>}
      {f.status !== 'done' && (
        <div className="card-foot">
          <div className={`avatar ${ownerOf(f)}`}>{avChar(ownerOf(f))}</div>
          <span className="truncate">{f.feature_id}</span>
          <span className="card-est">{STATUS_LABEL[f.status]}</span>
        </div>
      )}
      {f.status === 'done' && <div className="card-done-foot">✓ shipped</div>}
      {live && (
        <div className="live-actions">
          <button className="live-btn stop" onClick={(e) => { e.stopPropagation(); act.stop(f.feature_id) }}>Stop</button>
          <button className="live-btn" onClick={(e) => { e.stopPropagation(); open(f.feature_id) }}>Open</button>
        </div>
      )}
    </div>
  )
}

function Drawer({ fid, d, tab, setTab, connected, act, roomFor, filesFor, cardFor, close }) {
  const f = d.features.find((x) => x.feature_id === fid)
  const bugs = (d.bugs || []).filter((b) => b.feature_id === fid)
  const files = fid ? filesFor(fid) : []
  const room = fid ? roomFor(fid) : null
  const card = fid ? cardFor(fid) : null
  const activity = (d.audit || []).filter((e) => e.feature_id === fid)
  const gov = files.filter((a) => a.decision)
  const allows = gov.filter((a) => a.decision === 'allow').length
  const denies = gov.filter((a) => a.decision === 'deny').length

  const Tab = ({ id, label, n }) => (
    <div className={`dtab ${tab === id ? 'active' : ''}`} onClick={() => setTab(id)}>{label}{n != null && <span className="tc">{n}</span>}</div>
  )

  return (
    <>
      <div className={`scrim ${f ? 'open' : ''}`} onClick={close} />
      <aside className={`drawer ${f ? 'open' : ''}`} role="dialog" aria-hidden={!f}>
        {f && (
          <>
            <div className="drawer-head">
              <div className="drawer-crumb"><span>Task Board</span><span>/</span><span>{STATUS_LABEL[f.status]}</span><span>{f.feature_id}</span>
                <button className="drawer-close" onClick={close}>✕</button>
              </div>
              <div className="drawer-title break">{f.title}</div>
              <div className="drawer-meta">
                <span className="dpill"><span className="tag feature" style={{ padding: '1px 5px', fontSize: 9.5 }}>feature</span></span>
                <span className="dpill"><span className={prioClass(f.priority)} style={{ margin: 0 }}>P{f.priority ?? 3}</span></span>
                <span className="dpill"><span className="label">status</span>{STATUS_LABEL[f.status]}</span>
                {f.open_bugs ? <span className="dpill" style={{ background: 'var(--alert-tint)', color: 'var(--alert)' }}>{f.open_bugs} bug</span> : null}
              </div>
            </div>

            <div className="drawer-tabs">
              <Tab id="overview" label="Overview" />
              <Tab id="activity" label="Activity" n={activity.length} />
              <Tab id="governance" label="Governance" n={gov.length} />
              <Tab id="files" label="Files" n={files.length} />
            </div>

            <div className="drawer-body">
              {tab === 'overview' && (
                <>
                  <div className="psec">
                    <div className="plabel">SDLC progress</div>
                    <div className="progress" style={{ height: 6 }}><div className={`progress-fill ${f.status === 'done' ? 'done' : ''}`} style={{ width: `${f.progress}%` }} /></div>
                    <div className="meter-sub" style={{ marginTop: 6 }}>{f.progress}% · {STATUS_LABEL[f.status]}</div>
                  </div>
                  <div className="psec">
                    <div className="plabel">Properties</div>
                    <dl className="pprops">
                      <dt>Task ID</dt><dd className="mono">{f.feature_id}</dd>
                      <dt>Status</dt><dd>{STATUS_LABEL[f.status]}</dd>
                      <dt>Priority</dt><dd>P{f.priority ?? 3}</dd>
                      {room && <><dt>Room</dt><dd className="mono break">{room.room_id}{room.address ? ` · ${room.address}` : ''}</dd></>}
                      <dt>Open bugs</dt><dd>{f.open_bugs || 0}</dd>
                    </dl>
                  </div>
                  <div className="psec">
                    <div className="plabel">Actions</div>
                    <div className="actions-row">
                      {card && <button className="btn btn-ok" disabled={!connected} onClick={() => { act.sign(fid); close() }}>Sign</button>}
                      {card && <button className="btn btn-bad" disabled={!connected} onClick={() => { act.reject(fid); close() }}>Reject</button>}
                      {PRIOS.map(([lbl, p]) => <button key={p} className="btn" onClick={() => act.prioritize(fid, p)}>{lbl}</button>)}
                      <button className="btn" onClick={() => act.markReady(fid)}>Mark ready</button>
                      {isLive(f.status) && <button className="btn btn-bad" onClick={() => act.stop(fid)}>Stop work</button>}
                      <button className="btn btn-bad" onClick={() => act.remove(fid)}>Remove</button>
                    </div>
                  </div>
                  <div className="psec">
                    <div className="plabel">Bugs ({bugs.length})</div>
                    {bugs.length === 0 ? <div className="muted">None.</div> : bugs.map((b) => <div key={b.bug_id} className="file-row break"><span style={{ flex: 1 }}>{b.description}</span><span className={`file-act ${b.status === 'open' ? 'block' : 'read'}`}>{b.status}</span></div>)}
                  </div>
                </>
              )}

              {tab === 'activity' && (activity.length === 0
                ? <div className="empty">No activity yet.</div>
                : activity.slice(-60).reverse().map((e, i) => (
                  <div key={i} className="gov-row"><span className="mono" style={{ color: 'var(--ink-4)', fontSize: 11 }}>#{e.seq}</span><span><b>{e.event_type}</b> <span className="muted">{e.room_id || ''}</span></span></div>
                )))}

              {tab === 'governance' && (gov.length === 0
                ? <div className="empty">No governance events yet.</div>
                : <>
                  <div className="gov-stats">
                    <div className="gstat"><div className="gstat-v ok">{allows}</div><div className="gstat-l">Allowed</div></div>
                    <div className="gstat"><div className="gstat-v block">{denies}</div><div className="gstat-l">Denied</div></div>
                    <div className="gstat"><div className="gstat-v">{gov.length}</div><div className="gstat-l">Total</div></div>
                  </div>
                  {gov.map((a, i) => (
                    <div key={i} className="gov-row"><span className={`gverb ${a.decision}`}>{a.decision}</span><span className="break"><b className="mono">{a.file || a.tool}</b> {a.reason ? <span className="muted">· {a.reason}</span> : ''}</span></div>
                  ))}
                </>)}

              {tab === 'files' && (files.length === 0
                ? <div className="empty">No files touched yet.</div>
                : files.map((a, i) => (
                  <div key={i} className="file-row"><span className="file-path" title={a.file || ''}>{a.file || a.tool}</span><span className={`file-act ${a.decision || 'read'}`}>{a.decision || 'read'}</span></div>
                )))}
            </div>
          </>
        )}
      </aside>
    </>
  )
}
