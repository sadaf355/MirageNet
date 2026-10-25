import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import {
  Activity, AlertTriangle, ArrowDownRight, ArrowUpRight, Bell, ChevronDown,
  CircleHelp, Command, Database, FileSearch, Fingerprint, Gauge, GitBranch,
  LayoutDashboard, LockKeyhole, Network as NetworkIcon, Radio, Search, Settings2,
  Shield, ShieldAlert, Sparkles, TerminalSquare
} from 'lucide-react'
import { api, type Alert, type Host, type Network, type Overview } from '../services/api'
import { NetworkCanvas } from '../features/network/NetworkCanvas'
import { DecoyLab } from '../features/decoys/DecoyLab'
import { LiveAlerts } from '../features/alerts/LiveAlerts'
import { Incidents } from '../features/incidents/Incidents'
import { EvaluationLab } from '../features/evaluation/EvaluationLab'
import { IntruderPlay } from '../features/play/IntruderPlay'
const WelcomeSplash = lazy(() => import('../features/hero/WelcomeSplash'))

type Page = 'Overview' | 'Live Network' | 'Decoy Lab' | 'Live Alerts' | 'Incidents' | 'Intruder Play' | 'Evaluation Lab' | 'Settings'
const nav: {label: Page; icon: typeof LayoutDashboard; tag?: string}[] = [
  {label:'Overview',icon:LayoutDashboard},
  {label:'Live Network',icon:NetworkIcon},
  {label:'Decoy Lab',icon:Fingerprint},
  {label:'Live Alerts',icon:Bell},
  {label:'Incidents',icon:FileSearch},
  {label:'Intruder Play',icon:TerminalSquare,tag:'LAB'},
  {label:'Evaluation Lab',icon:Gauge},
  {label:'Settings',icon:Settings2},
]
const fallbackOverview: Overview = {hosts_online:0,hosts_total:7,decoys_deployed:0,decoys_total:0,open_alerts:0,active_incidents:0,detection_rate:null,system_status:'connecting',environment:'SIMULATION'}
const severityColor = (severity: string) => severity === 'high' ? 'red' : severity === 'medium' ? 'amber' : 'mint'
const formatTime = (value: string) => { const d = new Date(value); return Number.isNaN(d.getTime()) ? '—' : d.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}) }

export default function App() {
  const [page, setPage] = useState<Page>('Overview')
  const [showWelcome, setShowWelcome] = useState(() => { try { return sessionStorage.getItem('miragenet-welcome-dismissed') !== '1' } catch { return true } })
  const dismissWelcome = () => { try { sessionStorage.setItem('miragenet-welcome-dismissed', '1') } catch { /* storage may be unavailable */ } setShowWelcome(false) }
  const [network, setNetwork] = useState<Network | null>(null)
  const [overview, setOverview] = useState<Overview>(fallbackOverview)
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [apiState, setApiState] = useState<'connecting'|'online'|'offline'>('connecting')
  const [search, setSearch] = useState('')
  const [lastUpdated, setLastUpdated] = useState('—')
  const [demoBusy, setDemoBusy] = useState(false)
  const [demoStep, setDemoStep] = useState('')
  const [demoMessage, setDemoMessage] = useState('')
  const [selectedHost, setSelectedHost] = useState<{id:string;hostname:string;role:string;zone:string}|null>(null)
  const [selectedEdge, setSelectedEdge] = useState<{source:string;target:string}|null>(null)
  const [hostDecoys, setHostDecoys] = useState<Array<{id:string;name:string;type:string;status:string;host_id?:string}>>([])
  const [hostAlerts, setHostAlerts] = useState<Alert[]>([])
  const selectHost = (host:{id:string;hostname:string;role:string;zone:string}) => { setSelectedHost(host); setSelectedEdge(null); void Promise.all([api.decoys(),api.alerts()]).then(([ds,as])=>{setHostDecoys(ds.filter(d=>d.host_id===host.hostname||d.host_id===host.id));setHostAlerts(as.filter(a=>a.host_id===host.hostname||a.host_id===host.id))}).catch(()=>{setHostDecoys([]);setHostAlerts([])}) }
  const reduceMotion = useReducedMotion()
  const runFullDemo = async () => {
    const order = ['insider-data-theft','credential-lateral-movement','slow-scan-theft','benign-backup-noise']
    setDemoBusy(true); setDemoMessage('');
    try { for (let i=0;i<order.length;i++) { setDemoStep(`${i+1}/4 · ${order[i].replaceAll('-', ' ')}`); const apiBase=import.meta.env.VITE_API_BASE_URL??''; const r=await fetch(`${apiBase}/api/scenarios/${order[i]}/run`, {method:'POST'}); if (!r.ok) { const d=await r.json().catch(()=>({})); throw new Error(d.detail ?? `Scenario ${order[i]} failed (${r.status})`) } await r.json(); await new Promise(resolve=>window.setTimeout(resolve, reduceMotion?0:650)); } setDemoMessage('All four synthetic scenarios completed. Refreshing live data…'); const [summary, topology, recentAlerts] = await Promise.all([api.overview(),api.network(),api.alerts()]); setOverview(summary); setNetwork(topology); setAlerts(recentAlerts); setPage('Evaluation Lab'); } catch(e) { setDemoMessage(e instanceof Error?e.message:'Demo run failed'); } finally { setDemoBusy(false); setDemoStep(''); }
  }

  useEffect(() => {
    let alive = true
    const load = async () => {
      try {
        const [health, summary, topology, recentAlerts] = await Promise.all([api.health(), api.overview(), api.network(), api.alerts()])
        if (!alive) return
        setApiState(health.status === 'ok' ? 'online' : 'offline')
        setOverview(summary); setNetwork(topology); setAlerts(recentAlerts)
        setLastUpdated(new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}))
      } catch { if (alive) setApiState('offline') }
    }
    void load()
    const interval = window.setInterval(() => void load(), 15000)
    return () => { alive = false; window.clearInterval(interval) }
  }, [])

  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const defaultWs = `${protocol}//${window.location.host}`
    const wsBase = (import.meta.env.VITE_WS_BASE_URL ?? defaultWs).replace(/\/$/, '')
    const socket = new WebSocket(`${wsBase}/ws/alerts`)
    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data)
        if (payload.type === 'alert' && payload.alert) setAlerts((prev) => [payload.alert as Alert, ...prev].slice(0, 25))
      } catch { /* Ignore malformed messages from the stream. */ }
    }
    return () => socket.close()
  }, [])

  const filteredHosts = useMemo(() => (network?.nodes ?? []).filter((host) =>
    `${host.hostname} ${host.role} ${host.zone}`.toLowerCase().includes(search.toLowerCase())), [network, search])
  if (showWelcome) return <Suspense fallback={<div className="welcome-loading">Loading MirageNet experience…</div>}><WelcomeSplash onEnter={dismissWelcome} /></Suspense>
  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><Shield size={21}/><span /></div><div><div className="brand-name">mirage<span>net</span></div><div className="brand-caption">DECEPTION OPERATIONS</div></div></div>
      <div className="workspace-switch"><div className="workspace-icon"><Command size={15}/></div><div className="workspace-copy"><strong>ORCA SECURITY LAB</strong><span>Local simulation</span></div><ChevronDown size={14} className="muted-icon"/></div>
      <div className="nav-label">WORKSPACE</div>
      <nav className="primary-nav">{nav.map(item => <button key={item.label} className={`nav-item ${page===item.label?'active':''}`} onClick={()=>setPage(item.label)}><item.icon size={17}/><span>{item.label}</span>{item.tag && <small>{item.tag}</small>}{item.label==='Live Alerts' && alerts.length>0 && <i className="nav-count">{alerts.length}</i>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="system-card"><div className="system-card-head"><span className={`status-dot ${apiState==='online'?'good':apiState==='offline'?'bad':'pending'}`}/><span>API CONNECTION</span><strong>{apiState.toUpperCase()}</strong></div><p>{apiState==='online'?'Backend responding normally':apiState==='offline'?'Start the FastAPI server':'Checking local service…'}</p><div className="system-line"><span>Environment</span><b>SIMULATED</b></div><div className="system-line"><span>Telemetry</span><b>LOCAL ONLY</b></div></div><button className="nav-item bottom-item" onClick={()=>setPage('Evaluation Lab')}><Settings2 size={17}/><span>System settings</span></button><div className="profile"><div className="avatar">OL</div><div className="profile-copy"><strong>Operator Local</strong><span>Security analyst</span></div><CircleHelp size={16} className="muted-icon"/></div></div>
    </aside>
    <main className="main-area">
      <header className="topbar"><div className="breadcrumbs"><span>MirageNet</span><span className="crumb-slash">/</span><strong>{page}</strong></div><div className="topbar-right"><div className="env-pill"><span className="status-dot good"/>SANDBOX ENVIRONMENT</div><div className="topbar-divider"/><button className="icon-button" aria-label="Notifications" onClick={()=>setPage('Live Alerts')}><Bell size={17}/>{alerts.length>0&&<i/>}</button><div className="top-avatar">OL</div></div></header>
      <div className="content">
        {demoBusy && <div className="demo-progress"><span className="status-dot good"/> FULL DEMO IN PROGRESS <strong>{demoStep}</strong></div>}
        {demoMessage && <div className="demo-message">{demoMessage}</div>}
        <div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-mark"/> SECURITY POSTURE <span className="eyebrow-divider">/</span> {page.toUpperCase()}</div><h1>{page==='Overview'?'Command overview':page}</h1><p>{page==='Overview'?'A live operational picture of your synthetic deception environment.':page==='Live Network'?'Explore simulated trust paths, critical hosts, and future decoy placement.':page==='Decoy Lab'?'Forge high-enticement synthetic artifacts and track their deployment.':page==='Live Alerts'?'Review detection signals as the simulation emits correlated evidence.':page==='Incidents'?'Reconstruct the intruder journey from verified simulator evidence.':page==='Intruder Play'?'Safely explore a fictional environment through controlled simulator actions.':page==='Settings'?'Inspect service health and accessibility preferences.':'Measure detection quality against repeatable attack and benign scenarios.'}</p></div><div className="heading-actions"><div className="updated-label"><span className={`status-dot ${apiState==='online'?'good':'pending'}`}/>Updated {lastUpdated}</div><button className="button-primary run-demo-button" disabled={demoBusy} onClick={()=>void runFullDemo()}><Sparkles size={15}/>{demoBusy?'Running demo…':'Run simulation'}</button><button className="button-secondary" onClick={async()=>{if(!window.confirm("Reset all simulated events, alerts and incidents, then deploy a fresh 60-decoy demo state?"))return;try{await api.resetDemo();const [summary,topology,recentAlerts]=await Promise.all([api.overview(),api.network(),api.alerts()]);setOverview(summary);setNetwork(topology);setAlerts(recentAlerts);setDemoMessage("Demo reset complete: 60 fresh synthetic decoys deployed.");}catch(e){setDemoMessage(e instanceof Error?e.message:"Reset failed");}}}><Activity size={15}/> Reset demo</button>
            <button className="button-secondary" onClick={()=>window.location.reload()}><Activity size={15}/> Refresh view</button></div></div>
        <AnimatePresence mode="wait"><motion.div key={page} className="page-transition" initial={reduceMotion?false:{opacity:0,y:8}} animate={{opacity:1,y:0}} exit={reduceMotion?undefined:{opacity:0,y:-4}} transition={{duration:reduceMotion?0:.22}}>{page==='Overview' && <OverviewPage overview={overview} network={network} alerts={alerts} onNavigate={setPage} />}
        {page==='Live Network' && <section className="panel network-panel"><PanelTitle icon={NetworkIcon} title="Simulated network topology" subtitle="7 hosts · 7 trust edges · all routes are sandbox-only"/><div className="network-toolbar"><div className="search-field"><Search size={15}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Filter hosts, roles, zones…"/></div><div className="legend"><span><i className="legend-dot mint"/> Online</span><span><i className="legend-dot amber"/> Critical asset</span><span><i className="legend-dot red"/> Threat activity</span></div></div><NetworkCanvas network={network} filter={search} onHostSelect={selectHost} onEdgeSelect={edge=>{setSelectedEdge(edge);setSelectedHost(null)}}/>{(selectedHost||selectedEdge)&&<div className="network-inspector"><button className="inspector-close" onClick={()=>{setSelectedHost(null);setSelectedEdge(null)}}>Close ×</button>{selectedHost&&<><strong>{selectedHost.hostname}</strong><span>{selectedHost.role} · {selectedHost.zone}</span><p>Host selected from the simulated topology. Inventory and alert matches below are filtered from the current API data.</p><div className="inspector-lists"><div><b>DECOYS ({hostDecoys.length})</b>{hostDecoys.length?hostDecoys.map(d=><small key={d.id}>{d.name} · {d.status}</small>):<small>No matching decoys returned for this host.</small>}</div><div><b>RECENT ALERTS ({hostAlerts.length})</b>{hostAlerts.length?hostAlerts.slice(0,4).map(a=><small key={a.id}>{a.title} · {a.severity}</small>):<small>No matching alerts returned for this host.</small>}</div></div><button className="button-secondary" onClick={()=>setPage('Decoy Lab')}>Open decoys</button><button className="button-secondary" onClick={()=>setPage('Live Alerts')}>View events</button></>}{selectedEdge&&<><strong>{selectedEdge.source} → {selectedEdge.target}</strong><span>Simulated trust edge</span><p>Evidence: configured topology relation only. This edge represents simulator reachability, not observed packet traffic.</p><button className="button-secondary" onClick={()=>setPage('Incidents')}>Inspect incident evidence</button></>}</div>}<div className="host-table">{filteredHosts.map(h=><HostRow key={h.id} host={h}/>)}</div></section>}
        {page==='Decoy Lab' && <DecoyLab />}
        {page==='Live Alerts' && <LiveAlerts alerts={alerts} onAlert={(a)=>setAlerts(prev=>[a,...prev.filter(x=>x.id!==a.id)].slice(0,25))}/>}
        {page==='Incidents' && <Incidents />}
        {page==='Intruder Play' && <IntruderPlay />}
        {page==='Evaluation Lab' && <EvaluationLab />}
        {page==='Settings' && <SettingsPage apiState={apiState} lastUpdated={lastUpdated} overview={overview} />}</motion.div></AnimatePresence>
        <footer className="footer"><span> MIRAGENET <i>●</i> BUILD 0.5.0 · PHASE 5 EVALUATION</span><span><LockKeyhole size={12}/> SYNTHETIC DATA ONLY</span></footer>
      </div>
    </main>
  </div>
}

function PanelTitle({icon:Icon,title,subtitle,action}:{icon:typeof Activity;title:string;subtitle:string;action?:string}) {
  return <div className="panel-title"><div className="panel-title-icon"><Icon size={17}/></div><div className="panel-title-copy"><h2>{title}</h2><p>{subtitle}</p></div>{action&&<button className="text-action">{action} <ArrowUpRight size={13}/></button>}</div>
}
function OverviewPage({overview,network,alerts,onNavigate}:{overview:Overview;network:Network|null;alerts:Alert[];onNavigate:(p:Page)=>void}) {
  const stats=[{label:'HOSTS ONLINE',value:`${overview.hosts_online}/${overview.hosts_total||7}`,icon:NetworkIcon,trend:'Network footprint',color:'mint',note:'All seeded hosts monitored'},{label:'ACTIVE DECOYS',value:String(overview.decoys_deployed),icon:Fingerprint,trend:'Deception coverage',color:'blue',note:'Synthetic decoys in inventory'},{label:'OPEN ALERTS',value:String(overview.open_alerts),icon:ShieldAlert,trend:'Sensor pipeline active',color:'red',note:'Awaiting simulated touches'},{label:'ACTIVE INCIDENTS',value:String(overview.active_incidents),icon:GitBranch,trend:'Session-correlated',color:'amber',note:'No incident runs yet'}]
  return <>
    <div className="stat-grid">{stats.map((s,i)=><div className="stat-card" key={s.label}><div className="stat-top"><span>{s.label}</span><div className={`stat-icon ${s.color}`}><s.icon size={16}/></div></div><div className="stat-value">{s.value}</div><div className="stat-foot"><span className={`trend ${i===0?'positive':''}`}>{i===0?<ArrowUpRight size={13}/>:<ArrowDownRight size={13}/>} {s.trend}</span><span className="stat-note">{s.note}</span></div><div className={`stat-accent ${s.color}`}/></div>)}</div>
    <div className="overview-grid"><section className="panel topology-card"><PanelTitle icon={NetworkIcon} title="Network topology" subtitle="Trust paths across the simulated enterprise" action="Explore network"/><div className="mini-network"><NetworkCanvas network={network} compact onOpen={()=>onNavigate('Live Network')}/></div><div className="topology-foot"><div className="topology-meta"><span className="status-dot good"/> {network?.nodes.length??7} hosts online</div><button className="link-button" onClick={()=>onNavigate('Live Network')}>Open topology <ArrowUpRight size={13}/></button></div></section>
      <section className="panel posture-card"><PanelTitle icon={Activity} title="Environment status" subtitle="Service health and readiness"/><div className="readiness-score"><div className="readiness-ring"><div><strong>{overview.hosts_total?Math.round(overview.hosts_online/overview.hosts_total*100):0}%</strong><span>HOST READY</span></div></div><div className="readiness-copy"><strong>Simulation foundation online</strong><p>The local API, synthetic sensors, event persistence, and live alert stream are available.</p><span className="ready-label"><span className="status-dot good"/> Core services available</span></div></div><div className="service-list"><ServiceLine label="API & persistence" state="ONLINE"/><ServiceLine label="Network model" state={network?'READY':'WAITING'}/><ServiceLine label="Decoy forge" state="PHASE 2"/><ServiceLine label="Detection engine" state="ONLINE"/></div></section></div>
    <div className="lower-grid"><section className="panel alerts-preview"><PanelTitle icon={AlertTriangle} title="Recent signals" subtitle="Latest backend-recorded alerts" action="View all"/>{alerts.length===0?<EmptyState title="Quiet by design" body="The alert list is empty until simulated sensors are implemented. No sample threat activity is being presented as real telemetry."/>:<div className="alerts-list">{alerts.slice(0,4).map(a=><div className="alert-row" key={a.id}><span className={`severity-mark ${severityColor(a.severity)}`}/><div className="alert-copy"><strong>{a.title}</strong><span>{a.host_id??'Unknown host'} · {formatTime(a.timestamp)}</span></div><span className={`severity-tag ${severityColor(a.severity)}`}>{a.severity}</span></div>)}</div>}<button className="panel-bottom-link" onClick={()=>onNavigate('Live Alerts')}>Open alert console <ArrowUpRight size={13}/></button></section>
      <section className="panel host-preview"><PanelTitle icon={Database} title="Critical assets" subtitle="Highest-value hosts in the synthetic environment"/>{[...(network?.nodes??[])].sort((a,b)=>b.data_value-a.data_value).slice(0,4).map(host=><HostRow key={host.id} host={host}/>)}<button className="panel-bottom-link" onClick={()=>onNavigate('Live Network')}>View all hosts <ArrowUpRight size={13}/></button></section></div>
    <div className="phase-banner"><div className="phase-symbol"><Sparkles size={19}/></div><div><span>BUILD ROADMAP · PHASE 3 OF 5</span><strong>Decoy intelligence and live detection are operational.</strong><p>Incident reconstruction now connects persisted sensor evidence to timelines, supported ATT&CK mappings, and reports.</p></div><button onClick={()=>onNavigate('Decoy Lab')}>Explore Decoy Lab <ArrowUpRight size={14}/></button></div>
  </>
}
function ServiceLine({label,state}:{label:string;state:string}) { return <div className="service-line"><span>{label}</span><b className={state==='ONLINE'||state==='READY'?'online-state':''}>{state}</b></div> }
function HostRow({host}:{host:Host}) { return <div className="host-row"><div className={`host-symbol ${host.zone==='RESTRICTED'?'restricted':host.zone==='DMZ'?'dmz':''}`}><Database size={15}/></div><div className="host-main"><strong>{host.hostname}</strong><span>{host.role}</span></div><span className={`zone-chip ${host.zone==='RESTRICTED'?'restricted':''}`}>{host.zone}</span><span className="host-online"><i/> {host.status}</span></div> }
function EmptyState({title,body}:{title:string;body:string}) { return <div className="empty-state"><div className="empty-icon"><Radio size={18}/></div><strong>{title}</strong><p>{body}</p></div> }

function SettingsPage({apiState,lastUpdated,overview}:{apiState:string;lastUpdated:string;overview:Overview}) {
  const [reduced,setReduced]=useState(()=>window.matchMedia('(prefers-reduced-motion: reduce)').matches)
  const [refresh,setRefresh]=useState('15 seconds')
  return <div className="settings-grid"><section className="panel settings-card"><PanelTitle icon={Settings2} title="Workspace settings" subtitle="Local simulation controls and presentation preferences"/><div className="settings-row"><div><strong>Motion</strong><p>Respect system accessibility preferences for reduced motion.</p></div><label className="toggle-control"><input type="checkbox" checked={reduced} onChange={e=>setReduced(e.target.checked)}/> Reduced motion</label></div><div className="settings-row"><div><strong>Dashboard refresh</strong><p>Display preference for the operator console.</p></div><select value={refresh} onChange={e=>setRefresh(e.target.value)}><option>5 seconds</option><option>15 seconds</option><option>30 seconds</option></select></div><div className="settings-row"><div><strong>Safety mode</strong><p>All host activity and artifacts are synthetic.</p></div><span className="status-chip safe">LOCAL ONLY</span></div></section><section className="panel settings-card"><PanelTitle icon={Activity} title="System health" subtitle="Current service health snapshot"/><div className="health-grid"><div><span>API status</span><strong className={apiState==='online'?'health-good':'health-warn'}>{apiState.toUpperCase()}</strong></div><div><span>Hosts online</span><strong>{overview.hosts_online}/{overview.hosts_total}</strong></div><div><span>Decoys deployed</span><strong>{overview.decoys_deployed}/{overview.decoys_total}</strong></div><div><span>Open alerts</span><strong>{overview.open_alerts}</strong></div><div><span>Active incidents</span><strong>{overview.active_incidents}</strong></div><div><span>Last dashboard refresh</span><strong>{lastUpdated}</strong></div></div><p className="settings-footnote">Health reflects the local simulator API response, not the health of real infrastructure.</p></section></div>
}
