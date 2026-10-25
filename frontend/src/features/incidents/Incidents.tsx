import { useEffect, useRef, useState } from 'react'
import cytoscape, { type Core, type EventObject } from 'cytoscape'
import { motion, useReducedMotion } from 'framer-motion'
import { Activity, ArrowDownToLine, GitBranch, RefreshCw, ShieldAlert, Waypoints } from 'lucide-react'
import { api, type IncidentDetail } from '../../services/api'

type IncidentRow = {id:string;title:string;status:string;severity:string;started_at:string;summary:string;event_count:number}
const fmt = (v:string) => { const d=new Date(v); return Number.isNaN(d.getTime())?'—':d.toLocaleString() }
const sev = (v:string) => v==='high'?'red':v==='medium'?'amber':'mint'

export function Incidents() {
  const [rows,setRows] = useState<IncidentRow[]>([])
  const [selected,setSelected] = useState<IncidentDetail|null>(null)
  const [actor,setActor] = useState('')
  const [busy,setBusy] = useState(false)
  const [message,setMessage] = useState('')
  const [error,setError] = useState(false)
  const [activeEventId,setActiveEventId] = useState('')
  const [evidenceEventId,setEvidenceEventId] = useState('')
  const [pathStep,setPathStep] = useState(-1)
  const [pathPlaying,setPathPlaying] = useState(false)
  const reduceMotion = useReducedMotion()
  const graphRef = useRef<HTMLDivElement|null>(null)
  const cyRef = useRef<Core|null>(null)
  const [burning,setBurning] = useState(false)
  const [burnMessage,setBurnMessage] = useState('')
  const evidence = selected?.evidence
  async function load(preferId?:string) {
    const list = await api.incidents(); setRows(list)
    const target = preferId ?? selected?.id ?? list[0]?.id
    if (target) setSelected(await api.incident(target)); else setSelected(null)
  }
  useEffect(()=>{ void load().catch(e=>{setError(true);setMessage(e instanceof Error?e.message:'Could not load incidents')}) },[])
  useEffect(()=>{
    if(!graphRef.current || !evidence) return
    cyRef.current?.destroy()
    const hosts=evidence.host_path.map(h=>({data:{id:h.host_id,label:h.hostname}}))
    const edges=(evidence.graph_edges||[]).map((e,i)=>({data:{id:`incident-edge-${i}`,source:e.source.toLowerCase(),target:e.target.toLowerCase(),kind:e.edge_type||e.evidence_type||'inferred',label:(e.edge_type==='observed'||e.evidence_type==='observed')?'observed':'inferred'}}))
    const known=new Set(hosts.map(h=>h.data.id))
    const safeEdges=edges.filter(e=>known.has(e.data.source)&&known.has(e.data.target))
    const cy=cytoscape({container:graphRef.current,elements:[...hosts,...safeEdges],layout:{name:'breadthfirst',directed:true,padding:24},userZoomingEnabled:true,style:[
      {selector:'node',style:{'label':'data(label)','color':'#d8e6f1','background-color':'#17413f','border-width':2,'border-color':'#55e6c1','font-size':11,'text-valign':'bottom','text-margin-y':8,'width':34,'height':34}},
      {selector:'edge',style:{'curve-style':'bezier','target-arrow-shape':'triangle','target-arrow-color':'#55e6c1','line-color':'#55e6c1','width':2}},
      {selector:'edge[kind = "inferred"]',style:{'line-style':'dashed','line-color':'#c49c63','target-arrow-color':'#c49c63'}},
      {selector:'.linked-active',style:{'border-width':4,'border-color':'#ffffff','background-color':'#55e6c1','line-color':'#ffffff','width':4}}
    ]})
    cyRef.current=cy
    cy.on('tap','node',(evt: EventObject)=>{const host=evt.target.id();const item=evidence.timeline?.find(t=>(t.host_id??'').toLowerCase()===host);if(item){setActiveEventId(item.id);setEvidenceEventId(item.id)}})
    return ()=>{cy.destroy();cyRef.current=null}
  },[selected?.id,evidence])
  useEffect(()=>{const cy=cyRef.current;if(!cy||!evidence)return;cy.elements().removeClass('linked-active');const item=evidence.timeline?.find(t=>t.id===activeEventId);if(item && item.host_id)cy.getElementById(item.host_id.toLowerCase()).addClass('linked-active')},[activeEventId,evidence])
  async function burnFromIncident(){
    const item=evidence?.timeline?.find(t=>t.id===activeEventId) || evidence?.timeline?.[0]
    const decoyId=String(item?.evidence?.decoy_id||'')
    if(!decoyId){setBurnMessage('Select a timeline event linked to a decoy first.');return}
    setBurning(true);setBurnMessage('')
    try{const r=await fetch(`/api/decoys/${encodeURIComponent(decoyId)}/burn`,{method:'POST'});const data=await r.json();if(!r.ok)throw new Error(data.detail||'Burn failed');setBurnMessage(`Decoy burned; replacement ${data.replacement?.id||'created'}.`)}catch(e){setBurnMessage(e instanceof Error?e.message:'Burn failed')}finally{setBurning(false)}
  }
  async function reconstruct() {
    setBusy(true); setError(false); setMessage('')
    try { const result = await api.reconstructIncident(actor.trim()?{actor_id:actor.trim()}:{}); await load(result.id); setMessage('Incident story reconstructed from persisted simulator events.') }
    catch(e) { setError(true);setMessage(e instanceof Error?e.message:'Reconstruction failed') }
    finally { setBusy(false) }
  }
  async function animatePath() { if (!evidence?.host_path.length || pathPlaying) return; setPathPlaying(true); for (let i=0;i<evidence.host_path.length;i++) { setPathStep(i); const ev=evidence.timeline.find(t=>t.host_id===evidence.host_path[i].host_id); if(ev){setActiveEventId(ev.id);setEvidenceEventId(ev.id)} if (!reduceMotion) await new Promise(resolve=>window.setTimeout(resolve,900)); } setPathPlaying(false) }
  return <div className="incident-workspace">
    <section className="panel incident-controls"><div className="panel-title"><div className="panel-title-icon"><GitBranch size={17}/></div><div className="panel-title-copy"><h2>Evidence-backed reconstruction</h2><p>Build a story from persisted synthetic events. No narrative is invented without event evidence.</p></div><span className="source-chip">PHASE 4</span></div>
      <div className="incident-action-row"><label>Optional simulated actor ID<input value={actor} onChange={e=>setActor(e.target.value)} placeholder="Leave blank to use recent events"/></label><button className="button-primary" disabled={busy} onClick={()=>void reconstruct()}><Waypoints size={14}/>{busy?'Reconstructing…':'Reconstruct from events'}</button><button className="button-secondary" onClick={()=>void load().catch(e=>{setError(true);setMessage(String(e))})}><RefreshCw size={14}/> Refresh</button></div>
      {message&&<div className={error?'inline-error':'inline-success'}><Activity size={14}/>{message}</div>}
    </section>
    <div className="incident-grid">
      <section className="panel incident-list-panel"><div className="panel-title"><div className="panel-title-icon"><ShieldAlert size={17}/></div><div className="panel-title-copy"><h2>Incident records</h2><p>{rows.length} reconstructed stories</p></div></div>
        {rows.length===0?<div className="empty-state"><div className="empty-icon"><GitBranch size={18}/></div><strong>No incidents reconstructed</strong><p>Emit sensor events from Live Alerts, then reconstruct a story.</p></div>:rows.map(row=><button key={row.id} className={`incident-record ${selected?.id===row.id?'selected':''}`} onClick={()=>void api.incident(row.id).then(setSelected)}><span className={`severity-mark ${sev(row.severity)}`}/><span className="incident-record-copy"><strong>{row.title}</strong><small>{fmt(row.started_at)}</small><small>{row.event_count} events · {row.status}</small></span><span className={`severity-tag ${sev(row.severity)}`}>{row.severity}</span></button>)}
      </section>
      <section className="panel incident-detail-panel">{!selected?<div className="empty-state"><div className="empty-icon"><GitBranch size={18}/></div><strong>Select an incident</strong><p>Timeline, host path, ATT&CK mappings and reports appear here.</p></div>:<>
        <div className="panel-title"><div className="panel-title-icon"><GitBranch size={17}/></div><div className="panel-title-copy"><h2>{selected.title}</h2><p>{selected.id} · started {fmt(selected.started_at)}</p></div><span className={`severity-tag ${sev(selected.severity)}`}>{selected.severity}</span></div>
        <p className="incident-summary">{selected.summary}</p>
        {evidence?.adversary_playbook&&<div className="playbook-card" role="status"><div><span className="source-chip">ADVERSARY PLAYBOOK REPLAY</span><strong>{evidence.adversary_playbook.label}</strong><p>{evidence.adversary_playbook.explanation}</p><small>ATT&CK sequence: {(evidence.adversary_playbook.technique_sequence??[]).join(' → ')||'no supported techniques'} · match {Math.round((evidence.adversary_playbook.confidence??0)*100)}%</small></div></div>}
        <div className="incident-section"><h3><Waypoints size={14}/> Linked attack graph <span className="source-chip">Observed solid · inferred dashed</span></h3><div ref={graphRef} className="incident-attack-graph" role="img" aria-label="Interactive incident attack graph; select a host to highlight its timeline event."/><p className="muted-copy">Selecting a host highlights its first matching timeline event. Dashed links are topology inferences, not observed traffic.</p></div>
        <div className="incident-metrics"><div><strong>{evidence?.event_count??0}</strong><span>EVENTS</span></div><div><strong>{evidence?.host_path.length??0}</strong><span>HOSTS</span></div><div><strong>{evidence?.attack_techniques.length??0}</strong><span>ATT&CK</span></div></div>
        <div className="incident-section"><h3><Waypoints size={14}/> Simulated host path</h3>{!evidence?.host_path?.length?<p className="muted-copy">No host path could be inferred from the selected evidence.</p>:<><div className="path-animation-controls"><button className="button-secondary" disabled={pathPlaying} onClick={()=>void animatePath()}>{pathPlaying?'Playing path…':'▶ Animate path'}</button><button className="button-secondary" onClick={()=>setPathStep(v=>Math.min((evidence.host_path?.length||1)-1,v+1))}>Next host →</button><button className="button-secondary" onClick={()=>setPathStep(-1)}>Reset</button><span>{pathStep>=0?`Paused at host ${pathStep+1} of ${evidence.host_path?.length||0}`:'Path animation is step-controlled'}</span></div><div className="host-path">{(evidence.host_path||[]).map((host,i)=><motion.button type="button" className={`path-item ${pathStep===i?'path-active':''}`} key={`${host.host_id}-${i}`} onClick={()=>{setPathStep(i);const ev=evidence.timeline?.find(t=>t.host_id===host.host_id);if(ev){setActiveEventId(ev.id);setEvidenceEventId(ev.id)}}} animate={reduceMotion?{}:{opacity:(pathStep>=0 && i>pathStep) ? 0.48 : 1,scale:pathStep===i?1.025:1}} transition={{duration:reduceMotion?0:.25}}><span className="path-index">{String(i+1).padStart(2,'0')}</span><div><strong>{host.hostname}</strong><small>{host.host_id}</small></div>{i<(evidence.host_path?.length||0)-1&&<span className="path-arrow">→</span>}</motion.button>)}</div></>}</div>
        <div className="incident-section"><h3><Waypoints size={14}/> Topology-constrained graph edges</h3>{!evidence?.graph_edges?.length?<p className="muted-copy">No sequential host transition was available to infer a topology edge.</p>:<div className="technique-list">{evidence.graph_edges.map((edge,i)=>{const eventIds=edge.evidence_event_ids||[];const basisLabel=(edge.basis||edge.evidence_type||edge.edge_type||'topology inference').replaceAll('_',' ');return <button type="button" className={`technique-row edge-evidence ${eventIds.includes(activeEventId)?'linked-active':''}`} key={`${edge.source}-${edge.target}-${i}`} onClick={()=>{const id=eventIds[0]??'';setActiveEventId(id);setEvidenceEventId(id)}}><strong>{edge.source} → {edge.target}</strong><span>{basisLabel}</span><small>{eventIds.length} evidence event(s) · click to inspect</small></button>})}</div>}<p className="muted-copy">{evidence?.graph_note}</p></div>
        <div className="incident-section"><h3><Activity size={14}/> Ordered evidence timeline</h3>{!evidence?.timeline?.length?<p className="muted-copy">No timeline entries.</p>:<div className="incident-timeline">{(evidence.timeline||[]).map(item=><button type="button" className={`timeline-item timeline-selectable ${activeEventId===item.id?'linked-active':''}`} key={item.id} onClick={()=>{setActiveEventId(item.id);setEvidenceEventId(item.id)}}><span className="timeline-pin"/><div className="timeline-main"><strong>{item.summary}</strong><small>{fmt(item.timestamp)} · {item.event_type} · {item.id}</small><p>Action: {item.action} · Evidence source: synthetic sensor</p></div></button>)}</div>}</div>
        <div className="incident-section"><h3><ShieldAlert size={14}/> ATT&CK techniques supported by evidence</h3>{!evidence?.attack_techniques?.length?<p className="muted-copy">No technique matched the current evidence rules. Unsupported techniques are not inferred.</p>:<div className="technique-list">{(evidence.attack_techniques||[]).map(t=>{const eventIds=t.evidence_event_ids||[];return <button type="button" className={`technique-row attack-badge-row ${eventIds.includes(activeEventId)?'linked-active':''}`} key={t.technique_id} onClick={()=>{const id=eventIds[0]??'';setActiveEventId(id);setEvidenceEventId(id)}}><strong className="attack-badge">{t.technique_id}</strong><span>{t.name}</span><small>{eventIds.length} evidence event(s)</small></button>})}</div>}</div>
        {evidenceEventId && evidence && <aside className="evidence-drawer"><div><strong>Evidence inspector</strong><button className="inspector-close" onClick={()=>setEvidenceEventId('')}>Close ×</button></div>{(()=>{const item=evidence.timeline?.find(t=>t.id===evidenceEventId);return item?<><span className="source-chip">SYNTHETIC SENSOR EVIDENCE</span><h4>{item.summary}</h4><p>{fmt(item.timestamp)} · {item.hostname} · {item.actor_id}</p><p>Event type: {item.event_type} · Action: {item.action}</p><pre>{JSON.stringify(item.evidence,null,2)}</pre></>:<p className="muted-copy">No event was attached to this edge.</p>})()}</aside>}
        <div className="incident-section"><h3><Activity size={14}/> Response recommendations</h3><ul className="recommendation-list">{(evidence?.recommendations||[]).map(r=><li key={r}>{r}</li>)}</ul></div>
        <div className="report-actions"><button className="button-secondary" disabled={burning} onClick={()=>void burnFromIncident()}>{burning?'Burning…':'Burn selected decoy'}</button>{burnMessage&&<span className="muted-copy" role="status">{burnMessage}</span>}<a className="button-secondary" href={api.incidentReportUrl(selected.id,'md')} target="_blank" rel="noreferrer"><ArrowDownToLine size={14}/> Markdown report</a><a className="button-secondary" href={api.incidentReportUrl(selected.id,'json')} target="_blank" rel="noreferrer"><ArrowDownToLine size={14}/> JSON evidence</a></div>
      </>}</section>
    </div>
  </div>
}
