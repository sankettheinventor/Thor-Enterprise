import React, { useCallback, useEffect, useState } from 'react'
import { del, get, post } from './api.js'
import { rejectCard, signCard } from './sign.js'
import { enablePush, pushSupported } from './push.js'

const TABS = ['Watch', 'Rooms', 'Decide', 'Audit', 'Direct']
const LADDER = ['backlog', 'ready', 'building', 'in_qa', 'awaiting_signature', 'done']
const STAGE_LABEL = { backlog: 'Backlog', ready: 'Ready', building: 'Build', in_qa: 'QA', awaiting_signature: 'Sign', done: 'Done' }
const PRIOS = [['P0', 0], ['P1', 1], ['P2', 2], ['P3', 3]]

export default function App() {
  const [tab, setTab] = useState('Watch')
  const [connected, setConnected] = useState(true)
  const [sel, setSel] = useState(null) // {kind:'feature'|'room'|'card', id}
  const [toast, setToast] = useState(null)
  const [data, setData] = useState({ kanban: {}, cards: [], audit: [], lies: {}, rooms: [], cost: {},
    findings: [], health: {}, activity: {}, progress: [], bugs: [] })

  const refresh = useCallback(async () => {
    try {
      const r = await Promise.all([
        get('/kanban'), get('/cards'), get('/audit/feed'), get('/lies'), get('/rooms/live'),
        get('/cost'), get('/findings'), get('/health/system'), get('/rooms/activity'), get('/progress'), get('/bugs'),
      ])
      const [kanban, cards, audit, lies, rooms, cost, findings, health, activity, progress, bugs] = r
      setData({
        kanban: kanban || {}, cards: cards.cards || cards || [], audit: audit.events || audit || [],
        lies: lies || {}, rooms: rooms.rooms || rooms || [], cost: cost || {},
        findings: findings.findings || findings || [], health: health || {}, activity: activity || {},
        progress: progress.features || [], bugs: bugs.bugs || [],
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

  const flash = (m) => { setToast(m); setTimeout(() => setToast(null), 3500) }

  const act = {
    sign: async (id) => { if (!connected) return; const r = await signCard(id); flash(r.verified ? `Signed — ${id}` : `Rejected: ${r.reason || 'unknown'}`); refresh() },
    reject: async (id) => { if (!connected) return; const r = await rejectCard(id); flash(r.verified ? `Declined — ${id}` : `Rejected: ${r.reason || 'unknown'}`); refresh() },
    prioritize: async (fid, p) => { await post(`/commands/prioritize`, { feature_id: fid, priority: p }); flash(`Priority → P${p}`); refresh() },
    markReady: async (fid) => { await post(`/commands/mark_ready`, { feature_id: fid }); flash('Marked ready'); refresh() },
    remove: async (fid) => { if (!window.confirm(`Remove ${fid}? This is recorded in the ledger.`)) return; await del(`/features/${fid}`); setSel(null); flash(`Removed ${fid}`); refresh() },
    assign: async (title) => { const r = await post('/features', { title }); flash(r.feature_id ? `Assigned — ${r.feature_id}` : 'Assign failed'); refresh(); return r },
  }

  return (
    <div className="app">
      <header className="between" style={{ marginBottom: 16 }}>
        <div className="h1">THOR · Cockpit</div>
        <span className={`badge ${connected ? 'ok' : 'bad'}`}>
          <span className="dot" style={{ background: connected ? 'var(--ok)' : 'var(--bad)' }} />
          {connected ? 'live · sign enabled' : 'disconnected · signing off'}
        </span>
      </header>

      <nav className="tabs">
        {TABS.map((t) => <button key={t} className={`tab ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>{t}</button>)}
      </nav>

      {tab === 'Watch' && <Watch data={data} open={setSel} />}
      {tab === 'Rooms' && <Rooms data={data} open={setSel} />}
      {tab === 'Decide' && <Decide cards={data.cards} connected={connected} act={act} open={setSel} />}
      {tab === 'Audit' && <Audit data={data} />}
      {tab === 'Direct' && <Direct data={data} act={act} open={setSel} flash={flash} />}

      <Drawer sel={sel} data={data} connected={connected} act={act} close={() => setSel(null)} />
      {toast && <div className="toast">{toast}</div>}
    </div>
  )
}

/* ---------- small primitives ---------- */
function Panel({ title, sub, right, children }) {
  return (
    <section className="card">
      <div className="panel-h"><div className="h2">{title}</div>{right}</div>
      {sub && <div className="panel-sub">{sub}</div>}
      {children}
    </section>
  )
}
const Empty = ({ ico = '✓', children }) => <div className="empty"><div className="ico">{ico}</div><div style={{ marginTop: 6 }}>{children}</div></div>
const Stat = ({ label, value, tone }) => (
  <div className="stat"><div className="label truncate">{label}</div><div className={`v sm`} style={{ color: tone }}>{String(value)}</div></div>
)
function Timeline({ status }) {
  const cur = Math.max(0, LADDER.indexOf(status))
  return (
    <div className="timeline">
      {LADDER.map((s, i) => (
        <div key={s} className={`tl-step ${i < cur ? 'on' : ''} ${i === cur ? 'cur' : ''}`}>
          <div className="tl-bar" /><div className="tl-node">{i < cur ? '✓' : i + 1}</div>
          <div className="tl-label">{STAGE_LABEL[s]}</div>
        </div>
      ))}
    </div>
  )
}
const prioBadge = (p) => <span className={`badge ${p === 0 ? 'bad' : p === 1 ? 'warn' : ''}`}>P{p ?? 3}</span>

/* ---------- tabs ---------- */
function Watch({ data, open }) {
  const k = data.kanban || {}
  const cols = [['Backlog', k.backlog], ['Build', k.building], ['QA', k.in_qa], ['Sign', k.awaiting_signature], ['Merged', k.done]]
  const h = data.health || {}; const sa = h.selfaudit || h.self_audit || {}; const cost = data.cost || {}
  return (
    <>
      <Panel title="The line" sub="Counts from the Manager's kanban — reality, not the cook's claim.">
        <div className="grid">{cols.map(([n, ids]) => <div key={n} className="stat"><div className="label">{n}</div><div className="v">{(ids || []).length}</div></div>)}</div>
      </Panel>
      <Panel title="Features" sub="Tap a feature to open it. Progress is event-sourced from the SDLC.">
        {data.progress.length === 0 ? <Empty ico="◌">No features yet — assign one from Direct.</Empty>
          : data.progress.map((f) => (
            <div key={f.feature_id} className="list-row click" onClick={() => open({ kind: 'feature', id: f.feature_id })}>
              <div style={{ minWidth: 0, flex: 1 }}>
                <div className="row" style={{ gap: 8 }}>{prioBadge(f.priority)}<b className="truncate" title={f.title}>{f.title}</b></div>
                <div className="progress" style={{ marginTop: 6 }}><i className={f.status === 'done' ? 'done' : ''} style={{ width: `${f.progress}%` }} /></div>
              </div>
              <div style={{ textAlign: 'right', flex: 'none' }}>
                <span className="badge">{STAGE_LABEL[f.status] || f.status}</span>
                {f.open_bugs ? <div className="badge bad" style={{ marginTop: 4 }}>{f.open_bugs} bug</div> : null}
              </div>
            </div>
          ))}
      </Panel>
      <Panel title="System health" sub="Governance alive + fail-closed; the auditor runs at zero frontier cost.">
        <div className="grid">
          <Stat label="Sentinel" value={h.sentinel?.halted ? 'HALTED' : 'alive'} tone={h.sentinel?.halted ? 'var(--bad)' : 'var(--ok)'} />
          <Stat label="Fail-closed" value={h.sentinel?.fail_closed ? 'yes' : 'no'} />
          <Stat label="Alarms" value={h.sentinel?.alarms ?? 0} tone={(h.sentinel?.alarms ?? 0) ? 'var(--warn)' : undefined} />
          <Stat label="Auditor" value={sa.model || 'deterministic'} />
          <Stat label="Frontier $" value={sa.frontier_calls ?? 0} tone={(sa.frontier_calls ?? 0) ? 'var(--bad)' : 'var(--ok)'} />
          <Stat label="Cost" value={`${cost.spent ?? 0}/${cost.cap ?? '∞'}`} />
        </div>
      </Panel>
    </>
  )
}

function Rooms({ data, open }) {
  const rooms = data.rooms || []; const activity = data.activity || {}
  return (
    <>
      <Panel title="Live rooms" sub="Sealed rooms the cooks are working in. Tap to inspect.">
        {rooms.length === 0 ? <Empty ico="□">No active rooms.</Empty>
          : rooms.map((r) => (
            <div key={r.room_id} className="list-row click" onClick={() => open({ kind: 'room', id: r.room_id })}>
              <b className="truncate" style={{ flex: 1 }} title={r.feature_id}>{r.feature_id}</b>
              <span className="badge brand">{r.stage}</span>
              <span className="muted mono truncate" style={{ maxWidth: 130 }} title={r.address || ''}>{r.address || r.status || ''}</span>
            </div>
          ))}
      </Panel>
      <Panel title="File activity" sub="Exactly which file each cook writes — and what the Leash allowed or DENIED.">
        {Object.keys(activity).length === 0 ? <Empty ico="↳">No file actions yet.</Empty>
          : Object.entries(activity).map(([rid, items]) => (
            <div key={rid} style={{ marginBottom: 12 }}>
              <div className="label truncate" title={rid} style={{ marginBottom: 4 }}>{rid}</div>
              {items.map((a, i) => (
                <div key={i} className="list-row" style={{ padding: '5px 0' }}>
                  <span className="mono truncate" style={{ flex: 1 }} title={a.file || ''}>{a.file || a.tool}</span>
                  <span className={`badge ${a.decision === 'allow' ? 'ok' : a.decision === 'deny' ? 'bad' : 'warn'}`}>{a.decision}</span>
                </div>
              ))}
            </div>
          ))}
      </Panel>
    </>
  )
}

function Decide({ cards, connected, act, open }) {
  const list = (cards || []).filter((c) => (c.status || 'open') === 'open')
  return (
    <Panel title="Decide" sub="The line paused for your signature. Ed25519 — signed in your browser with your key.">
      {list.length === 0 ? <Empty>Nothing waiting — the cooks are within scope.</Empty>
        : list.map((c) => (
          <div key={c.card_id} className="list-row">
            <div style={{ minWidth: 0, flex: 1, cursor: 'pointer' }} onClick={() => open({ kind: 'card', id: c.card_id })}>
              <b>{c.type || 'card'}</b> · <span className="dim truncate">{c.feature_id}</span>
              <div className="muted mono" style={{ fontSize: 11 }}>{c.card_id}</div>
            </div>
            <button className="btn btn-ok btn-sm" disabled={!connected} onClick={() => act.sign(c.card_id)}>{connected ? 'Sign' : 'Off'}</button>
            <button className="btn btn-bad btn-sm" disabled={!connected} onClick={() => act.reject(c.card_id)}>Reject</button>
          </div>
        ))}
    </Panel>
  )
}

function Audit({ data }) {
  const lies = data.lies || {}; const recent = lies.recent || []; const bugs = data.bugs || []
  const findings = data.findings || []; const audit = data.audit || []
  return (
    <>
      <Panel title="Lies caught" right={lies.total ? <span className="badge warn">{lies.total}</span> : null} sub="Fabricated claims the verdict caught from reality.">
        {recent.length === 0 ? <Empty>None — claims have matched reality.</Empty>
          : recent.map((l, i) => <div key={i} className="list-row"><b className="warn" style={{ color: 'var(--warn)' }}>{l.feature_id || l.container}</b><span className="muted clamp-2" style={{ flex: 1 }}>{(l.signals || [])[0] || ''}</span></div>)}
      </Panel>
      <Panel title="New bugs" right={bugs.length ? <span className="badge bad">{bugs.length}</span> : null} sub="Every bug QA + the checker surfaced.">
        {bugs.length === 0 ? <Empty>No bugs.</Empty>
          : bugs.map((b) => (
            <div key={b.bug_id} className="list-row">
              <span className="dot" style={{ background: b.status === 'open' ? 'var(--bad)' : 'var(--ink-3)' }} />
              <b className="truncate" style={{ flex: 'none', maxWidth: 90 }} title={b.feature_id}>{b.feature_id}</b>
              <span className="badge">{b.source}</span>
              <span className="muted clamp-2" style={{ flex: 1, minWidth: 0 }} title={b.description}>{b.description}</span>
            </div>
          ))}
      </Panel>
      <Panel title="Self-audit findings" sub="What the background inspector (Qwen) flagged.">
        {findings.length === 0 ? <Empty>No open findings.</Empty>
          : findings.map((f, i) => <div key={i} className="list-row break">{f.description || JSON.stringify(f)}</div>)}
      </Panel>
      <Panel title="Audit feed" sub="Every signed, hash-chained event from the ledger.">
        <div style={{ maxHeight: 340, overflowY: 'auto' }}>
          {audit.slice(-80).reverse().map((e, i) => (
            <div key={i} className="list-row" style={{ padding: '5px 0' }}>
              <span className="muted mono" style={{ minWidth: 34 }}>#{e.seq}</span>
              <span className="badge brand truncate" style={{ maxWidth: 160 }}>{e.event_type}</span>
              <span className="muted truncate" style={{ flex: 1 }}>{e.feature_id || e.room_id || ''}</span>
            </div>
          ))}
        </div>
      </Panel>
    </>
  )
}

function Direct({ data, act, open, flash }) {
  const [title, setTitle] = useState('')
  const turnOnPush = async () => { const r = await enablePush(); flash(r.ok ? 'Notifications on — THOR will buzz you when a card needs signing' : `Push: ${r.reason}`) }
  return (
    <>
      <Panel title="Assign a feature" sub="Hand a feature to the governed worker.">
        <div className="row wrap">
          <input className="field" style={{ flex: '1 1 220px' }} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Feature title" onKeyDown={(e) => e.key === 'Enter' && title.trim() && (act.assign(title), setTitle(''))} />
          <button className="btn btn-primary" disabled={!title.trim()} onClick={() => { act.assign(title); setTitle('') }}>Assign</button>
        </div>
      </Panel>
      <Panel title="Backlog" sub="Tap to open · edit priority · remove. Bounded by the phone command allowlist.">
        {data.progress.length === 0 ? <Empty ico="◌">Nothing in the backlog.</Empty>
          : data.progress.map((f) => (
            <div key={f.feature_id} className="list-row click" onClick={() => open({ kind: 'feature', id: f.feature_id })}>
              {prioBadge(f.priority)}<b className="truncate" style={{ flex: 1 }} title={f.title}>{f.title}</b>
              <span className="badge">{STAGE_LABEL[f.status] || f.status}</span>
            </div>
          ))}
      </Panel>
      <Panel title="Notifications" sub="A THOR notification on this phone when a card needs signing — even with the app closed.">
        <button className="btn btn-ok" disabled={!pushSupported()} onClick={turnOnPush}>{pushSupported() ? '🔔 Enable notifications' : 'Push not supported here'}</button>
      </Panel>
    </>
  )
}

/* ---------- right-side drawer ---------- */
function Drawer({ sel, data, connected, act, close }) {
  const f = sel?.kind === 'feature' ? data.progress.find((x) => x.feature_id === sel.id) : null
  const room = sel?.kind === 'room' ? data.rooms.find((x) => x.room_id === sel.id) : null
  const card = sel?.kind === 'card' ? data.cards.find((x) => x.card_id === sel.id) : null
  const fid = f?.feature_id || room?.feature_id || card?.feature_id
  const bugs = (data.bugs || []).filter((b) => b.feature_id === fid)
  const roomsFor = (data.rooms || []).filter((r) => r.feature_id === fid)
  const files = roomsFor.flatMap((r) => (data.activity?.[r.room_id] || []))
  const title = f?.title || room?.room_id || card?.type || sel?.id || ''

  return (
    <>
      <div className={`scrim ${sel ? 'open' : ''}`} onClick={close} />
      <aside className={`drawer ${sel ? 'open' : ''}`} role="dialog" aria-hidden={!sel}>
        {sel && (
          <>
            <div className="drawer-h">
              <div style={{ minWidth: 0 }}>
                <div className="label">{sel.kind}</div>
                <div className="h1 break">{title}</div>
                {fid && <div className="row" style={{ gap: 8, marginTop: 6 }}>{f && prioBadge(f.priority)}<span className="badge">{STAGE_LABEL[f?.status] || f?.status || room?.stage || card?.status}</span></div>}
              </div>
              <button className="btn btn-ghost btn-icon" onClick={close} aria-label="Close">✕</button>
            </div>
            <div className="drawer-body">
              {f && <section><div className="label" style={{ marginBottom: 8 }}>SDLC progress</div><Timeline status={f.status} /></section>}

              {f && (
                <section>
                  <div className="label" style={{ marginBottom: 8 }}>Actions</div>
                  <div className="row wrap">
                    {PRIOS.map(([lbl, p]) => <button key={p} className="btn btn-sm" onClick={() => act.prioritize(f.feature_id, p)}>{lbl}</button>)}
                    <button className="btn btn-sm" onClick={() => act.markReady(f.feature_id)}>Mark ready</button>
                    <button className="btn btn-sm btn-bad" onClick={() => act.remove(f.feature_id)}>Remove</button>
                  </div>
                </section>
              )}

              {card && (
                <section>
                  <div className="label" style={{ marginBottom: 8 }}>Decision</div>
                  <div className="row">
                    <button className="btn btn-ok" disabled={!connected} onClick={() => { act.sign(card.card_id); close() }}>Sign</button>
                    <button className="btn btn-bad" disabled={!connected} onClick={() => { act.reject(card.card_id); close() }}>Reject</button>
                  </div>
                  <pre className="mono break" style={{ marginTop: 10, color: 'var(--ink-3)', whiteSpace: 'pre-wrap' }}>{JSON.stringify(card.payload || {}, null, 1).slice(0, 600)}</pre>
                </section>
              )}

              <section>
                <div className="label" style={{ marginBottom: 8 }}>Bugs ({bugs.length})</div>
                {bugs.length === 0 ? <div className="muted">None.</div>
                  : bugs.map((b) => <div key={b.bug_id} className="list-row break"><span className="dot" style={{ background: b.status === 'open' ? 'var(--bad)' : 'var(--ink-3)' }} /><span style={{ flex: 1 }}>{b.description}</span></div>)}
              </section>

              <section>
                <div className="label" style={{ marginBottom: 8 }}>File activity ({files.length})</div>
                {files.length === 0 ? <div className="muted">No file actions recorded.</div>
                  : files.slice(0, 30).map((a, i) => (
                    <div key={i} className="list-row" style={{ padding: '5px 0' }}>
                      <span className="mono truncate" style={{ flex: 1 }} title={a.file || ''}>{a.file || a.tool}</span>
                      <span className={`badge ${a.decision === 'allow' ? 'ok' : a.decision === 'deny' ? 'bad' : 'warn'}`}>{a.decision}</span>
                    </div>
                  ))}
              </section>
            </div>
          </>
        )}
      </aside>
    </>
  )
}
