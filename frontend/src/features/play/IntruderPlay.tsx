import { useEffect, useState } from 'react'
import {
  AlertTriangle,
  CheckCircle,
  FileText,
  FolderOpen,
  KeyRound,
  LockKeyhole,
  LogIn,
  RefreshCw,
  Server,
} from 'lucide-react'

const API = import.meta.env.VITE_API_BASE_URL ?? ''
const WS = (
  import.meta.env.VITE_WS_BASE_URL ??
  (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host
).replace(/\/$/, '')

type Entry = { id: string; name: string; type: string; host_id: string; path: string }
type DiscoveredCred = { username: string; password: string; sourceFile: string }

type FictionalHost = { hostname: string; role: string; status: string }
type LoginResponse = {
  mode: string
  result: string
  username: string
  matched_decoy_id?: string
  matched_decoy_name?: string
  event?: any
  alert?: any
  fictional_dashboard?: {
    title: string
    warning: string
    hosts: FictionalHost[]
  }
  notice: string
}

export function IntruderPlay() {
  const [entries, setEntries] = useState<Entry[]>([])
  const [selected, setSelected] = useState('')
  const [actor, setActor] = useState('play-actor')
  const [preview, setPreview] = useState('')
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [securityEvents, setSecurityEvents] = useState<string[]>([])
  const [terminalLines, setTerminalLines] = useState<string[]>([
    'MirageNet simulated terminal v1.0',
    'Type a safe action below: help, list, clear, status',
  ])
  const [terminalInput, setTerminalInput] = useState('')

  // Honey login state
  const [loginUsername, setLoginUsername] = useState('')
  const [loginPassword, setLoginPassword] = useState('')
  const [loginBusy, setLoginBusy] = useState(false)
  const [loginError, setLoginError] = useState('')
  const [loginResult, setLoginResult] = useState<LoginResponse | null>(null)
  const [discoveredCreds, setDiscoveredCreds] = useState<DiscoveredCred[]>([])

  useEffect(() => {
    const ws = new WebSocket(`${WS}/ws/alerts`)
    ws.onmessage = (e) => {
      try {
        const d = JSON.parse(e.data)
        setSecurityEvents((old) => [
          `${new Date().toLocaleTimeString()} · ${
            d.type === 'alert' ? 'ALERT' : 'EVENT'
          } · ${d.alert?.title ?? d.event?.event_type ?? 'signal'} · ${
            d.alert?.severity ?? d.event?.host_id ?? ''
          }`,
          ...old,
        ].slice(0, 15))
      } catch {}
    }
    ws.onopen = () =>
      setSecurityEvents((old) => ['Connected to live simulator stream', ...old].slice(0, 15))
    ws.onclose = () =>
      setSecurityEvents((old) => ['WebSocket disconnected', ...old].slice(0, 15))
    return () => ws.close()
  }, [])

  async function load() {
    const r = await fetch(`${API}/api/play/filesystem`)
    const d = await r.json()
    if (!r.ok) throw new Error(d.detail ?? 'Could not load files')
    setEntries(d.entries)
    if (!selected && d.entries[0]) setSelected(d.entries[0].id)
  }

  useEffect(() => {
    void load().catch((e) => setError(String(e)))
  }, [])

  // Inspect preview text for credentials found in notes
  function scanPreviewForCredentials(text: string, fileName: string) {
    const found: DiscoveredCred[] = []

    // Pattern 1: Username: <user>\nPassword: <pass>
    const m1 = text.match(/username\s*[:=]\s*([^\r\n]+)[\r\n]+\s*password\s*[:=]\s*([^\r\n]+)/i)
    if (m1) {
      found.push({ username: m1[1].trim(), password: m1[2].trim(), sourceFile: fileName })
    }

    // Pattern 2: CSV rows like https://...,user,pass
    for (const line of text.split('\n')) {
      const parts = line.split(',').map((p) => p.trim())
      if (parts.length >= 3 && parts[0].startsWith('http') && !parts[0].toLowerCase().includes('url')) {
        found.push({ username: parts[1], password: parts[2], sourceFile: fileName })
      }
    }

    if (found.length > 0) {
      setDiscoveredCreds((prev) => {
        const existingUsers = new Set(prev.map((c) => c.username))
        const newOnes = found.filter((c) => !existingUsers.has(c.username))
        return [...newOnes, ...prev]
      })
      // Pre-fill the login input if currently empty
      if (!loginUsername) {
        setLoginUsername(found[0].username)
        setLoginPassword(found[0].password)
      }
    }
  }

  async function read() {
    if (!selected) return
    setBusy(true)
    const entry = entries.find((e) => e.id === selected)
    setTerminalLines((old) => [
      ...old,
      `operator@mirage:${entry?.path ?? '/'}$ read ${entry?.name ?? selected}`,
    ])
    setError('')
    try {
      const r = await fetch(`${API}/api/play/read`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decoy_id: selected, actor_id: actor }),
      })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail ?? 'Read failed')
      setPreview(d.preview)
      setNotice(d.notice)
      scanPreviewForCredentials(d.preview, entry?.name ?? 'credential_note')
      setTerminalLines((old) => [
        ...old,
        `[sensor] file_read emitted · host=${entry?.host_id ?? 'unknown'}`,
        `[monitor] ${d.notice ?? 'alert pipeline updated'}`,
      ])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Read failed')
    } finally {
      setBusy(false)
    }
  }

  async function submitHoneyLogin() {
    if (!loginUsername.trim() || !loginPassword.trim()) return
    setLoginBusy(true)
    setLoginError('')
    setLoginResult(null)
    setTerminalLines((old) => [
      ...old,
      `operator@mirage:~$ login WEB-01 [user=${loginUsername.trim()}]`,
    ])

    try {
      const r = await fetch(`${API}/api/play/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: loginUsername.trim(),
          password: loginPassword.trim(),
          actor_id: actor,
        }),
      })
      const d: LoginResponse = await r.json()
      if (!r.ok) throw new Error(d.notice ?? 'Honey login request failed')

      setLoginResult(d)
      if (d.mode === 'honey-credential-match') {
        const alertId = d.alert?.id ?? 'n/a'
        setTerminalLines((old) => [
          ...old,
          `[HONEY-LOGIN HIT] Access granted to fictional admin dashboard!`,
          `[ALERT] High-confidence alert triggered: ${alertId} (severity: ${d.alert?.severity ?? 'high'})`,
          `[STITCH] Actor session stitched via credential ${loginUsername.trim()}`,
        ])
        setSecurityEvents((old) => [
          `${new Date().toLocaleTimeString()} · ALERT · Honey Credential Login: ${loginUsername.trim()} · high`,
          ...old,
        ].slice(0, 15))
      } else {
        setTerminalLines((old) => [
          ...old,
          `[HONEY-LOGIN MISS] Rejected. Fictional credential not found in any deployed decoy.`,
          `[EVENT] Low-severity telemetry event logged for actor ${actor}`,
        ])
        setSecurityEvents((old) => [
          `${new Date().toLocaleTimeString()} · EVENT · failed_honey_login · low`,
          ...old,
        ].slice(0, 15))
      }
    } catch (e) {
      setLoginError(e instanceof Error ? e.message : 'Login failed')
    } finally {
      setLoginBusy(false)
    }
  }

  function runTerminal() {
    const cmd = terminalInput.trim().toLowerCase()
    setTerminalLines((old) =>
      [
        ...old,
        `operator@mirage:~$ ${terminalInput}`,
        cmd === 'help'
          ? 'Allowed demo commands: help, list, clear, status, login'
          : cmd === 'list'
          ? entries.map((e) => `${e.host_id.padEnd(8)} ${e.path}${e.name}`).join('\n')
          : cmd === 'status'
          ? 'Sandbox active · Command execution disabled · Deployed lures online'
          : cmd === 'clear'
          ? ''
          : `Command not executed. This terminal is a safe sandbox. Use UI actions to read lures or authenticate.`,
      ].filter(Boolean)
    )
    setTerminalInput('')
  }

  function resetPlay() {
    setSelected('')
    setPreview('')
    setNotice('')
    setError('')
    setActor('play-actor')
    setLoginUsername('')
    setLoginPassword('')
    setLoginResult(null)
    setLoginError('')
    setDiscoveredCreds([])
    setTerminalLines([
      'MirageNet simulated terminal v1.0',
      'Workspace reset. No host state was changed.',
    ])
    void load()
  }

  return (
    <div className="panel play-panel">
      <div className="panel-title">
        <div className="panel-title-icon">
          <FolderOpen size={17} />
        </div>
        <div className="panel-title-copy">
          <h2>Fictional intruder workspace</h2>
          <p>Read-only interaction with deployed synthetic decoys. This is not a shell or real filesystem.</p>
        </div>
        <span className="source-chip">SANDBOX</span>
        <button className="button-secondary play-reset" onClick={resetPlay}>
          <RefreshCw size={13} /> Reset
        </button>
      </div>

      <div className="play-warning">
        <LockKeyhole size={15} />
        <span>No command execution, real host access, network actions, or real credentials.</span>
      </div>

      <div className="play-guided-hint" role="note">
        <strong>Guided workflow for judge</strong>
        <span>
          1. Select a credential note file below (e.g. <code>chrome_passwords_backup.txt</code> on <code>WS-01</code>).<br />
          2. Click <strong>Read selected artifact</strong> to inspect the synthetic note.<br />
          3. Use the discovered credential in the <strong>Admin Portal Login</strong> card to trigger a honey-credential alert!
        </span>
      </div>

      <div className="play-layout">
        {/* Left: Simulated Filesystem */}
        <section className="play-file-list">
          <div className="play-section-label">
            SIMULATED FILESYSTEM{' '}
            <button className="icon-button" onClick={() => void load()} aria-label="Refresh files">
              <RefreshCw size={13} />
            </button>
          </div>
          {entries.length === 0 ? (
            <p className="muted-copy">No deployed decoys. Forge and deploy artifacts in Decoy Lab first.</p>
          ) : (
            entries.map((e) => (
              <button
                className={`play-file ${selected === e.id ? 'selected' : ''}`}
                key={e.id}
                onClick={() => setSelected(e.id)}
              >
                <FileText size={15} />
                <span>
                  <strong>{e.name}</strong>
                  <small>{e.host_id} · {e.type}</small>
                </span>
              </button>
            ))
          )}
        </section>

        {/* Right: Controlled Actions & Honey Login */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', minWidth: 0 }}>
          {/* File Reader Action */}
          <section className="play-reader">
            <div className="play-section-label">1. CONTROLLED READ ACTION</div>
            <label>
              Simulated actor ID
              <input value={actor} onChange={(e) => setActor(e.target.value)} maxLength={80} />
            </label>
            <div className="play-selected-path">
              {entries.find((e) => e.id === selected)?.path ?? 'Select a deployed synthetic file'}
            </div>
            <button className="button-primary" disabled={!selected || busy} onClick={() => void read()}>
              <FileText size={14} />
              {busy ? 'Reading…' : 'Read selected artifact'}
            </button>
            {error && <div className="inline-error">{error}</div>}
            {preview && (
              <div className="play-preview">
                <div className="play-section-label">SYNTHETIC CONTENT PREVIEW</div>
                <pre>{preview}</pre>
                <p>{notice}</p>
              </div>
            )}
          </section>

          {/* Honey Credential Login Action */}
          <section className="play-reader" style={{ borderLeft: '3px solid #55e6c1' }}>
            <div className="play-section-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <LogIn size={13} color="#55e6c1" />
              <span>2. LOGIN TO ADMIN PORTAL (WEB-01 HONEY LURE)</span>
            </div>
            <p className="muted-copy" style={{ fontSize: '9px', margin: '4px 0 10px', lineHeight: 1.5 }}>
              Use credentials discovered in synthetic notes to attempt authentication on WEB-01. Only credentials
              belonging to deployed decoys trigger high-confidence alerts and open the fictional admin portal.
            </p>

            {discoveredCreds.length > 0 && (
              <div style={{ marginBottom: '10px', background: '#0e1f1c', border: '1px solid #1f4d42', borderRadius: '5px', padding: '8px' }}>
                <div style={{ font: '9px var(--mono)', color: '#55e6c1', marginBottom: '6px' }}>
                  DISCOVERED HONEY CREDENTIALS IN NOTES:
                </div>
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                  {discoveredCreds.map((c, i) => (
                    <button
                      key={i}
                      type="button"
                      className="button-secondary"
                      style={{ fontSize: '8px', padding: '4px 7px' }}
                      onClick={() => {
                        setLoginUsername(c.username)
                        setLoginPassword(c.password)
                      }}
                    >
                      <KeyRound size={11} />
                      {c.username} ({c.sourceFile})
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '9px', marginBottom: '10px' }}>
              <label>
                Username
                <input
                  value={loginUsername}
                  onChange={(e) => setLoginUsername(e.target.value)}
                  placeholder="e.g. nw_admin or admin_recovery_01"
                />
              </label>
              <label>
                Password
                <input
                  type="password"
                  value={loginPassword}
                  onChange={(e) => setLoginPassword(e.target.value)}
                  placeholder="e.g. FakePass123!"
                />
              </label>
            </div>

            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              <button
                className="button-primary"
                disabled={!loginUsername.trim() || !loginPassword.trim() || loginBusy}
                onClick={() => void submitHoneyLogin()}
              >
                <LogIn size={14} />
                {loginBusy ? 'Verifying lure credentials…' : 'Login to admin portal'}
              </button>
            </div>

            {loginError && <div className="inline-error" style={{ marginTop: '8px' }}>{loginError}</div>}

            {/* Honey Login Result: Decoy Dashboard or Generic Denial */}
            {loginResult && (
              <div style={{ marginTop: '12px' }}>
                {loginResult.mode === 'honey-credential-match' ? (
                  <div style={{ background: '#10241e', border: '1px solid #2f6b59', borderRadius: '7px', padding: '12px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#55e6c1', fontWeight: 600, fontSize: '11px', marginBottom: '6px' }}>
                      <CheckCircle size={16} />
                      <span>HONEY-CREDENTIAL MATCH · ACCESS GRANTED TO FICTIONAL DASHBOARD</span>
                    </div>
                    <p style={{ color: '#8ee5ce', fontSize: '9px', margin: '0 0 10px', lineHeight: 1.5 }}>
                      Alert created: <strong>{loginResult.alert?.id}</strong> (Severity: <strong>{loginResult.alert?.severity ?? 'high'}</strong>).
                      Session stitched for actor <code>{actor}</code>.
                    </p>
                    <div style={{ background: '#0a1618', border: '1px solid #1c3c35', borderRadius: '6px', padding: '10px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', font: '9px var(--mono)', color: '#8ba6b7', marginBottom: '8px' }}>
                        <Server size={12} color="#55e6c1" />
                        <span>FICTIONAL SIMULATOR HOSTS (WEB-01 MANAGEMENT PORTAL)</span>
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))', gap: '6px' }}>
                        {loginResult.fictional_dashboard?.hosts?.map((h) => (
                          <div key={h.hostname} style={{ background: '#0e1e1d', border: '1px solid #254d43', borderRadius: '5px', padding: '6px 8px' }}>
                            <div style={{ font: '10px var(--mono)', color: '#e7eef5', fontWeight: 600 }}>{h.hostname}</div>
                            <div style={{ fontSize: '8px', color: '#7c90a2', margin: '2px 0' }}>{h.role}</div>
                            <div style={{ fontSize: '8px', color: '#55e6c1' }}>{h.status}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div style={{ background: '#251518', border: '1px solid #5a262e', borderRadius: '7px', padding: '12px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#ff6471', fontWeight: 600, fontSize: '11px', marginBottom: '6px' }}>
                      <AlertTriangle size={16} />
                      <span>ACCESS DENIED · FICTIONAL LURE REJECTED</span>
                    </div>
                    <p style={{ color: '#ff9da6', fontSize: '9px', margin: 0, lineHeight: 1.5 }}>
                      {loginResult.notice}
                    </p>
                  </div>
                )}
              </div>
            )}
          </section>

          {/* Terminal */}
          <section className="play-terminal">
            <div className="play-section-label">SIMULATED TERMINAL · NO COMMAND EXECUTION</div>
            <pre>{terminalLines.join('\n')}</pre>
            <form
              onSubmit={(e) => {
                e.preventDefault()
                runTerminal()
              }}
            >
              <input
                value={terminalInput}
                onChange={(e) => setTerminalInput(e.target.value)}
                placeholder="help / list / status / clear"
                aria-label="Safe simulated terminal input"
              />
              <button className="button-secondary" type="submit">
                Run safe action
              </button>
            </form>
          </section>
        </div>
      </div>

      <aside className="panel play-security-monitor" style={{ marginTop: '14px' }}>
        <div className="panel-title">
          <div className="panel-title-icon">
            <LockKeyhole size={16} />
          </div>
          <div className="panel-title-copy">
            <h2>Live security monitor</h2>
            <p>Sensor events and alerts streamed from this simulator</p>
          </div>
          <span className="source-chip">LIVE</span>
        </div>
        {securityEvents.length ? (
          securityEvents.map((item, i) => (
            <div className="monitor-event" key={`${item}-${i}`}>
              {item}
            </div>
          ))
        ) : (
          <p className="muted-copy">Waiting for simulated activity… Read a decoy or login to generate live telemetry.</p>
        )}
      </aside>
    </div>
  )
}
