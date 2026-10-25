from uuid import uuid4
from app.models import Alert, Event, Incident, Node
from app.services.network_service import TOPOLOGY_EDGES
import networkx as nx

def attach_event_to_incident(db, session_id, run_id, event, alert, severity):
    evidence = event.evidence or {}
    # Scenario run ID prevents separate demos by the same actor from merging; otherwise group by actor session.
    key = run_id or session_id
    incidents = db.query(Incident).order_by(Incident.started_at.desc()).limit(200).all()
    incident = next((i for i in incidents if (i.evidence or {}).get('correlation_key') == key), None)
    if incident is None:
        incident = Incident(id=f"inc-{uuid4().hex[:16]}", title=f"Session investigation · {event.actor_id}"[:180],
            status="investigating", severity=severity, started_at=event.timestamp, summary="Correlated synthetic events from one actor session.",
            evidence={"correlation_key":key,"session_id":session_id,"run_id":run_id,"event_ids":[],"alert_ids":[],"event_count":0,"timeline":[],"host_path":[],"graph_edges":[],"attack_techniques":[],"recommendations":["Review the synthetic evidence and validate the simulated actor classification."]})
        db.add(incident); db.flush()
    story = dict(incident.evidence or {})
    event_ids = list(story.get('event_ids', [])); alert_ids = list(story.get('alert_ids', [])); timeline = list(story.get('timeline', [])); path = list(story.get('host_path', []))
    if event.id not in event_ids:
        event_ids.append(event.id)
        node = db.get(Node, event.host_id) if event.host_id else None
        timeline.append({"id":event.id,"event_type":event.event_type,"timestamp":event.timestamp.isoformat(),"host_id":event.host_id,"hostname":node.hostname if node else event.host_id,"actor_id":event.actor_id,"action":evidence.get('action',event.event_type),"summary":f"{event.actor_id} {evidence.get('action',event.event_type)} on {node.hostname if node else event.host_id}","evidence":evidence})
        if event.host_id and not any(x.get('host_id') == event.host_id for x in path): path.append({"host_id":event.host_id,"hostname":node.hostname if node else event.host_id,"first_seen":event.timestamp.isoformat(),"event_id":event.id})
    if alert and alert.id not in alert_ids: alert_ids.append(alert.id)
    edges = list(story.get('graph_edges', []))
    for item in timeline:
        ev = item.get('evidence') or {}
        for edge in ev.get('observed_edges', []) + ev.get('inferred_hops', []):
            basis = edge.get('basis') or ("observed_transition" if edge.get('edge_type') == 'observed' else "topology_shortest_path_inference")
            edge = {**edge, "basis": basis, "evidence_event_ids": [edge.get('evidence_event_id') or item['id']], "evidence_type": "observed" if edge.get('edge_type') == 'observed' else "inferred"}
            if not any(e.get('source') == edge.get('source') and e.get('target') == edge.get('target') and e.get('evidence_type') == edge.get('evidence_type') for e in edges): edges.append(edge)
    # Credential scenario mappings are tied to persisted event evidence.
    techniques = list(story.get('attack_techniques', []))
    rules = [("T1552.001","Credentials In Files",lambda e:e.event_type=="file_read" and "credential" in str((e.evidence or {}).get("decoy_type","")).lower()),("T1078","Valid Accounts",lambda e:e.event_type=="auth_attempt" or bool((e.evidence or {}).get("credential_evidence")),),("T1021.004","SSH",lambda e:e.event_type=="simulated_ssh")]
    for ev in db.query(Event).filter(Event.id.in_(event_ids)).all():
        for tid,name,predicate in rules:
            if predicate(ev):
                row=next((t for t in techniques if t.get('technique_id')==tid),None)
                if row is None: row={"technique_id":tid,"name":name,"evidence_event_ids":[]}; techniques.append(row)
                if ev.id not in row['evidence_event_ids']: row['evidence_event_ids'].append(ev.id)
    story.update({"event_ids":event_ids,"alert_ids":alert_ids,"event_count":len(event_ids),"timeline":sorted(timeline,key=lambda x:x['timestamp']),"host_path":path,"graph_edges":edges,"attack_techniques":techniques,"actor_ids":sorted({x.get('actor_id','') for x in timeline}),"source":"session_correlated_synthetic_events","graph_note":"Observed edges come from explicit transition evidence; inferred edges use simulator topology only."})
    from app.services.sensor_pipeline.playbook import classify_playbook
    story["adversary_playbook"] = classify_playbook(techniques, story["timeline"])
    incident.evidence=story
    if severity == 'high' or (severity == 'medium' and incident.severity == 'low'): incident.severity=severity
    incident.summary=f"{len(event_ids)} correlated synthetic events across {len(path)} hosts; {len(techniques)} evidence-backed ATT&CK mappings."
    return incident
