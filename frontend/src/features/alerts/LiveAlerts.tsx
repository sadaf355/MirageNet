import { useEffect, useState } from 'react'
import { Activity, Bell, Fingerprint, Radio, ShieldAlert, Zap } from 'lucide-react'
import type { Alert } from '../../services/api'
import { api } from '../../services/api'

type Decoy = {id:string; name:string; type:string; status:string; host_id?:string; token?:string}
type AutoRotation = {
  burned_decoy_id: string
  replacement: {
    name: string
    token: string
  }
}
const color = (s:string) => s==='high'?'red':s==='medium'?'amber':'mint'
const time = (v:string) => { const d=new Date(v); return Number.isNaN(d.getTime())?'—':d.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}) }

export function LiveAlerts({alerts,onAlert}:{alerts:Alert[];onAlert:(a:Alert)=>void}) {
  const [decoys,setDecoys] = useState<Decoy[]>([])
  const [decoyId,setDecoyId] = useState('')
  const [actor,setActor] = useState('simulated-intruder-01')
  const [action,setAction] = useState('read')
  const [credential,setCredential] = useState(false)
  const [step,setStep] = useState('1')
  const [benign,setBenign] = useState(false)
  const [busy,setBusy] = useState(false)
  const [message,setMessage] = useState('')
  const [error,setError] = useState(false)
  const [severityFilter,setSeverityFilter] = useState('all')
  const [hostFilter,setHostFilter] = useState('')
  const [actorFilter,setActorFilter] = useState('')
  const [scenarioFilter,setScenarioFilter] = useState('')
  const [expandedAlert,setExpandedAlert] = useState('')
  const [events,setEvents] = useState<Array<{id:string;event_type:string;host_id:string;actor_id:string;timestamp:string;evidence:Record<string,unknown>}>>([])
  useEffect(()=>{ void refreshDecoys(); void refreshEvents() },[])
  async function refreshDecoys(){ try { const r=await fetch('/api/decoys'); if(r.ok){const rows=await r.json() as Decoy[]; setDecoys(rows); const deployed=rows.find(x=>x.status==='deployed'); if(deployed)setDecoyId(deployed.id)} } catch{} }
  async function refreshEvents(){ try { const r=await fetch('/api/events?limit=8'); if(r.ok)setEvents(await r.json()) } catch{} }
  async function simulate(){ if(!decoyId){setError(true);setMessage('Forge and deploy at least one synthetic decoy first.');return} setBusy(true);setMessage('');setError(false);try { const result=await api.sensorTouch({decoy_id:decoyId,actor_id:actor.trim()||'simulated-intruder',action,credential_used:credential,breadcrumb_step:Number(step),benign}); if(result.alert)onAlert(result.alert as Alert); const rotation=result.auto_rotation; setMessage(rotation?`High-confidence touch burned ${rotation.burned_decoy_id}; replacement ${rotation.replacement.name} is deployed with new token ${rotation.replacement.token}.`:`Event persisted · confidence ${Math.round((result.alert?.confidence ?? result.session.confidence)*100)}% · ${result.alert?.severity ?? 'event only'} signal`); await refreshDecoys(); await refreshEvents() } catch(e){setError(true);setMessage(e instanceof Error?e.message:'Could not emit simulator event')} finally{setBusy(false)} }
  const deployed=decoys.filter(d=>d.status==='deployed')
  return <div className="alerts-workspace">
    <section className="panel sensor-panel"><div className="panel-title"><div className="panel-title-icon"><Fingerprint size={17}/></div><div className="panel-title-copy"><h2>Controlled sensor simulator</h2><p>Emit a synthetic decoy touch through the backend pipeline — no real host or file is accessed.</p></div><span className="source-chip">LOCAL ONLY</span></div>
      <div className="sensor-form">
        <label>Deployed decoy<select value={decoyId} onChange={e=>setDecoyId(e.target.value)}><option value="">Select a deployed decoy</option>{deployed.map(d=><option key={d.id} value={d.id}>{d.name} · {d.type}</option>)}</select></label>
        <label>Simulated actor<input value={actor} onChange={e=>setActor(e.target.value)} maxLength={80}/></label>
        <label>Action<select value={action} onChange={e=>setAction(e.target.value)}><option value="read">Read artifact</option><option value="enumerate">Enumerate artifact</option><option value="copy">Copy artifact</option><option value="credential-use">Use synthetic credential</option></select></label>
        <label>Breadcrumb step<select value={step} onChange={e=>setStep(e.target.value)}><option value="1">Step 1 of 3</option><option value="2">Step 2 of 3</option><option value="3">Step 3 of 3</option></select></label>
        <label className="sensor-check"><input type="checkbox" checked={credential||action==='credential-use'} onChange={e=>setCredential(e.target.checked)} /> Credential-use evidence</label>
        <label className="sensor-check"><input type="checkbox" checked={benign} onChange={e=>setBenign(e.target.checked)} /> Mark as benign test actor (−0.40 score adjustment)</label>
        <button className="button-primary sensor-submit" disabled={busy||!deployed.length} onClick={()=>void simulate()}><Zap size={14}/>{busy?'Emitting…':'Simulate decoy touch'}</button>
      </div>
      {message&&<div className={error?'inline-error':'inline-success'}>{error?<ShieldAlert size={14}/>:<Activity size={14}/>} {message}</div>}
      {!deployed.length&&<div className="sensor-hint">No deployed decoys found. Open Decoy Lab, forge artifacts, then deploy them before testing sensors.</div>}
    </section>
    <section className="panel"><div className="panel-title"><div className="panel-title-icon"><Bell size={17}/></div><div className="panel-title-copy"><h2>Alert stream</h2><p>Persisted alerts · updates arrive over WebSocket</p></div><span className="inventory-count">{alerts.length} LOADED</span></div>{alerts.length===0?<div className="empty-state"><div className="empty-icon"><Radio size={18}/></div><strong>No alerts recorded</strong><p>Use the simulator above to emit your first synthetic event.</p></div>:(<><div className="alert-filters" aria-label="Filter alerts"><label>Severity<select value={severityFilter} onChange={e=>setSeverityFilter(e.target.value)}><option value="all">All severities</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select></label><label>Host<input value={hostFilter} onChange={e=>setHostFilter(e.target.value)} placeholder="Filter host"/></label><label>Actor<input value={actorFilter} onChange={e=>setActorFilter(e.target.value)} placeholder="Filter actor"/></label><label>Scenario<input value={scenarioFilter} onChange={e=>setScenarioFilter(e.target.value)} placeholder="Filter scenario"/></label></div><div className="alerts-list">{alerts.filter(a=>(severityFilter==='all'||a.severity===severityFilter)&&(!hostFilter||(a.host_id??'').toLowerCase().includes(hostFilter.toLowerCase()))&&(!actorFilter||String(a.evidence?.actor_id??'').toLowerCase().includes(actorFilter.toLowerCase()))&&(!scenarioFilter||String(a.evidence?.scenario??'').toLowerCase().includes(scenarioFilter.toLowerCase()))).map(a=><div className="alert-detail-row" key={a.id}><button className="alert-row alert-expand" aria-expanded={expandedAlert===a.id} onClick={()=>setExpandedAlert(expandedAlert===a.id?'':a.id)}><span className={`severity-mark ${color(a.severity)}`} aria-label={`Severity ${a.severity}`}/><div className="alert-copy"><strong>{a.title}</strong><span>{a.host_id??'Unknown host'} · {String(a.evidence?.actor_id??'unknown actor')} · {time(a.timestamp)}</span></div><span className={`severity-tag ${color(a.severity)}`}>{a.severity.toUpperCase()}</span><span className="confidence">{Math.round(a.confidence*100)}%</span></button>{expandedAlert===a.id&&<div className="alert-explanation"><p><b>Why it fired:</b> {String(a.evidence?.why_fired??'Synthetic sensor evidence matched a detection rule.')}</p><div className="score-breakdown">{(['D','N','U','P'] as const).map(k=><span key={k}><b>{k}</b> {String((a.evidence?.score_breakdown as Record<string,unknown>|undefined)?.[k]??'—')}</span>)}<span><b>Benign adjustment</b> {String((a.evidence?.score_breakdown as Record<string,unknown>|undefined)?.benign_adjustment??0)}</span></div><p><b>Recommended next action:</b> {String(a.evidence?.recommended_next_action??'Review synthetic evidence and validate actor classification.')}</p><p><b>Scenario:</b> {String(a.evidence?.scenario??'manual sensor')} · <b>Event:</b> {String(a.evidence?.event_id??'—')}</p>{Boolean(a.evidence?.auto_rotation)&&<div className="rotation-receipt" role="status"><strong>Auto burn-and-rotate completed</strong><span>Old token burned · replacement deployed</span><b>{(a.evidence?.auto_rotation as AutoRotation | undefined)?.replacement?.name??'Replacement decoy'}</b><code>{(a.evidence?.auto_rotation as AutoRotation | undefined)?.replacement?.token??''}</code></div>}</div>}</div>)}</div></>)}</section>
    <section className="panel"><div className="panel-title"><div className="panel-title-icon"><Activity size={17}/></div><div className="panel-title-copy"><h2>Recent sensor events</h2><p>Persisted evidence from the local simulator</p></div><button className="text-action" onClick={()=>void refreshEvents()}>Refresh</button></div>{events.length===0?<div className="sensor-hint">No events recorded yet.</div>:<div className="event-list">{events.map(e=><div className="event-row" key={e.id}><span className="event-dot"/><div><strong>{(e.event_type??'').replaceAll('_',' ')}</strong><span>{e.actor_id} · {e.host_id}</span></div><code>{time(e.timestamp)}</code><span className="source-chip">{e.evidence?.simulated?'SIMULATED':'EVENT'}</span></div>)}</div>}</section>
  </div>
}
