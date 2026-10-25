export type Host = {
  id: string; hostname: string; role: string; zone: string; status: string;
  data_value: number; description: string; centrality: number;
}
export type Edge = { source: string; target: string; relation: string }
export type Network = { nodes: Host[]; edges: Edge[] }
export type Overview = {
  hosts_online: number; hosts_total: number; decoys_deployed: number; decoys_total: number;
  open_alerts: number; active_incidents: number; detection_rate: number | null;
  system_status: string; environment: string;
}
export type Alert = {
  id: string; title: string; severity: string; confidence: number; host_id: string | null;
  status: string; timestamp: string; evidence: Record<string, unknown>;
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''
async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`)
  if (!response.ok) throw new Error(`API ${response.status}: ${response.statusText}`)
  return response.json() as Promise<T>
}
export const api = {
  health: () => request<{status:string; safety_mode:string}>('/api/health'),
  resetDemo: () => fetch(`${API_BASE}/api/reset`, {method:'POST'}).then(async r => { const data = await r.json(); if (!r.ok) throw new Error(data.detail ?? `API ${r.status}`); return data }),
  alertSiemUrl: (id:string) => `${API_BASE}/api/alerts/${id}/siem`,
  overview: () => request<Overview>('/api/overview'),
  network: () => request<Network>('/api/network'),
  alerts: () => request<Alert[]>('/api/alerts'),
  decoys: () => request<Array<{id:string;name:string;type:string;status:string;host_id?:string}>>('/api/decoys'),
  incidents: () => request<Array<{id:string;title:string;status:string;severity:string;started_at:string;summary:string;event_count:number}>>('/api/incidents'),
  reconstructIncident: (payload: {actor_id?:string; event_ids?:string[]}) => fetch(`${API_BASE}/api/incidents/reconstruct`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)}).then(async r => { const data = await r.json(); if (!r.ok) throw new Error(data.detail ?? `API ${r.status}`); return data }),
  incident: (id:string) => request<IncidentDetail>(`/api/incidents/${id}`),
  incidentReportUrl: (id:string, format:'md'|'json') => `${API_BASE}/api/incidents/${id}/report?format=${format}`,
  sensorTouch: (payload: {decoy_id:string; actor_id:string; action:string; credential_used:boolean; breadcrumb_step:number; benign:boolean}) => fetch(`${API_BASE}/api/sensor/touch`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)}).then(async r => { const data = await r.json(); if (!r.ok) throw new Error(data.detail ?? `API ${r.status}`); return data }),
}

export type IncidentDetail = {
  id:string; title:string; status:string; severity:string; started_at:string; summary:string;
  evidence:{event_count:number;actor_ids:string[];timeline:Array<{id:string;event_type:string;timestamp:string;host_id:string|null;hostname:string;actor_id:string;action:string;summary:string;evidence:Record<string,unknown>}>;host_path:Array<{host_id:string;hostname:string;first_seen:string;event_id:string}>;attack_techniques:Array<{technique_id:string;name:string;evidence_event_ids:string[]}>;alert_ids:string[];recommendations:string[];event_ids:string[];source:string;ended_at:string;graph_note?:string;graph_edges?:Array<{source:string;target:string;basis:string;evidence_event_ids:string[];edge_type?:string;evidence_type?:string}>;adversary_playbook?:{id:string;label:string;confidence:number;technique_sequence:string[];matched_techniques:string[];explanation:string;source:string}}
}
