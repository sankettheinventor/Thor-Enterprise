import React, { useCallback, useEffect, useState } from 'react'
import { get, post } from './api.js'
import { signCard } from './sign.js'

const TABS = ['Direct', 'Watch', 'Decide', 'Audit']
const C = { bg: '#0b0d10', card: '#14181d', line: '#232a31', ink: '#e7eaee', ink3: '#8b95a1',
            ok: '#3fb950', warn: '#d29922', bad: '#f85149', brand: '#388bfd' }

export default function App() {
  const [tab, setTab] = useState('Watch')
  const [connected, setConnected] = useState(true) // T7: fail-closed — signing disabled when stale
  const [data, setData] = useState({ summary: null, kanban: null, cards: [], audit: [], lies: [] })
  const [toast, setToast] = useState(null)

  const refresh = useCallback(async () => {
    try {
      const [summary, kanban, cards, audit, lies] = await Promise.all([
        get('/state/summary'), get('/kanban'), get('/cards'), get('/audit/feed'), get('/lies'),
      ])
      setData({ summary, kanban, cards: cards.cards || cards || [], audit: audit.events || audit || [], lies: lies.lies || lies || [] })
      setConnected(true)
    } catch {
      setConnected(false) // disconnected → the picture may be stale → signing is disabled
    }
  }, [])

  useEffect(() => {
    refresh()
    // Real-time sync: subscribe to the Manager's SSE stream — the laptop AND the phone re-sync the
    // instant the ledger advances. A dropped stream => fail-closed (signing disabled until reconnect).
    let es
    try {
      es = new EventSource('/stream')
      es.addEventListener('hello', () => setConnected(true))
      es.onmessage = () => refresh() // ledger advanced -> pull the new truth
      es.onerror = () => setConnected(false)
    } catch {
      /* EventSource unavailable -> the polling heartbeat below carries it */
    }
    const t = setInterval(refresh, 8000) // heartbeat fallback if SSE is blocked by a proxy
    return () => {
      if (es) es.close()
      clearInterval(t)
    }
  }, [refresh])

  const sign = async (cardId) => {
    if (!connected) return
    try {
      const r = await signCard(cardId)
      setToast(r.verified ? `Signed — ${cardId}` : `Rejected: ${r.reason || 'unknown'}`)
      refresh()
    } catch (e) {
      setToast('Signing failed: ' + e.message)
    }
    setTimeout(() => setToast(null), 4000)
  }

  return (
    <div style={{ maxWidth: 980, margin: '0 auto', padding: 'clamp(12px, 4vw, 20px)',
      paddingTop: 'calc(env(safe-area-inset-top, 0px) + 14px)', minHeight: '100vh' }}>
      <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18 }}>
        <div style={{ fontWeight: 700, fontSize: 20 }}>THOR · CEO Cockpit</div>
        <span style={{ fontSize: 12, padding: '4px 10px', borderRadius: 20,
          background: connected ? '#11301a' : '#3a1413', color: connected ? C.ok : C.bad }}>
          {connected ? '● live · sign enabled' : '○ DISCONNECTED — data may be stale; signing disabled'}
        </span>
      </header>

      <nav style={{ display: 'flex', gap: 8, marginBottom: 18 }}>
        {TABS.map((t) => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: '8px 16px', borderRadius: 8, cursor: 'pointer', border: `1px solid ${C.line}`,
            background: tab === t ? C.brand : C.card, color: tab === t ? '#fff' : C.ink }}>{t}</button>
        ))}
      </nav>

      {tab === 'Direct' && <Direct onDone={refresh} setToast={setToast} />}
      {tab === 'Watch' && <Watch data={data} />}
      {tab === 'Decide' && <Decide cards={data.cards} connected={connected} onSign={sign} />}
      {tab === 'Audit' && <Audit audit={data.audit} lies={data.lies} />}

      {toast && <div style={{ position: 'fixed', bottom: 24, left: '50%', transform: 'translateX(-50%)',
        background: C.card, border: `1px solid ${C.line}`, padding: '10px 18px', borderRadius: 10 }}>{toast}</div>}
    </div>
  )
}

function Panel({ title, sub, children }) {
  return (
    <section style={{ background: C.card, border: `1px solid ${C.line}`, borderRadius: 12, padding: 18, marginBottom: 14 }}>
      <div style={{ fontWeight: 600 }}>{title}</div>
      {sub && <div style={{ color: C.ink3, fontSize: 13, marginTop: 4, marginBottom: 10 }}>{sub}</div>}
      {children}
    </section>
  )
}

function Direct({ onDone, setToast }) {
  const [title, setTitle] = useState('')
  const submit = async () => {
    if (!title.trim()) return
    const r = await post('/task', { title })
    setToast(r.feature_id ? `Assigned — ${r.feature_id}` : 'Assign failed')
    setTitle('')
    onDone()
  }
  return (
    <Panel title="Direct" sub="Assign a feature to the governed worker.">
      <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Feature title"
        style={{ width: '100%', padding: 10, borderRadius: 8, border: `1px solid ${C.line}`, background: C.bg, color: C.ink, marginBottom: 10 }} />
      <button onClick={submit} style={{ padding: '8px 16px', borderRadius: 8, background: C.brand, color: '#fff', border: 'none', cursor: 'pointer' }}>Assign</button>
    </Panel>
  )
}

function Watch({ data }) {
  const k = data.kanban || {}
  const cols = [['Backlog', k.backlog], ['Building', k.building], ['QA', k.in_qa], ['Awaiting sign', k.awaiting_signature], ['Merged', k.done]]
  return (
    <Panel title="Watch" sub="The line, live — counts from the Manager's kanban (not the cook's claim).">
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        {cols.map(([name, ids]) => (
          <div key={name} style={{ flex: '1 1 150px', background: C.bg, border: `1px solid ${C.line}`, borderRadius: 10, padding: 12 }}>
            <div style={{ fontSize: 12, color: C.ink3 }}>{name}</div>
            <div style={{ fontSize: 24, fontWeight: 700 }}>{(ids || []).length}</div>
          </div>
        ))}
      </div>
    </Panel>
  )
}

function Decide({ cards, connected, onSign }) {
  const open = (cards || []).filter((c) => (c.status || 'open') === 'open')
  return (
    <Panel title="Decide" sub="The line paused and needs your signature. Ed25519 — signed in your browser with your key.">
      {open.length === 0 && <div style={{ color: C.ink3 }}>Nothing waiting — the cooks are within scope.</div>}
      {open.map((c) => (
        <div key={c.card_id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          padding: '10px 0', borderTop: `1px solid ${C.line}` }}>
          <div><b>{c.type || 'card'}</b> · {c.feature_id} <span style={{ color: C.ink3, fontSize: 12 }}>({c.card_id})</span></div>
          <button disabled={!connected} onClick={() => onSign(c.card_id)} style={{
            padding: '6px 14px', borderRadius: 8, border: 'none', cursor: connected ? 'pointer' : 'not-allowed',
            background: connected ? C.ok : C.line, color: '#fff', opacity: connected ? 1 : 0.5 }}>
            {connected ? 'Sign' : 'Signing disabled'}
          </button>
        </div>
      ))}
    </Panel>
  )
}

function Audit({ audit, lies }) {
  return (
    <>
      <Panel title="Lies caught" sub="Fabricated claims the verdict caught from reality.">
        {(lies || []).length === 0 ? <div style={{ color: C.ink3 }}>None.</div>
          : lies.map((l, i) => <div key={i} style={{ padding: '6px 0', color: C.warn }}>{l.message || l.signals?.[0] || JSON.stringify(l)}</div>)}
      </Panel>
      <Panel title="Audit feed" sub="Every signed, hash-chained event from the Manager's ledger.">
        <div style={{ maxHeight: 320, overflow: 'auto' }}>
          {(audit || []).slice(-60).reverse().map((e, i) => (
            <div key={i} style={{ display: 'flex', gap: 10, padding: '5px 0', borderTop: `1px solid ${C.line}`, fontSize: 13 }}>
              <span style={{ color: C.ink3, minWidth: 32 }}>#{e.seq}</span>
              <span style={{ color: C.brand }}>{e.event_type}</span>
              <span style={{ color: C.ink3 }}>{e.feature_id || e.room_id || ''}</span>
            </div>
          ))}
        </div>
      </Panel>
    </>
  )
}
