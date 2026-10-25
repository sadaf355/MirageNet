"""Sensor-specific parsing helpers. Endpoints remain in routers/sensors.py."""
def edge_evidence(metadata, event_id, host_id):
    if metadata.get('observed_transition') and metadata.get('source_host'):
        return [{"source":str(metadata['source_host']).lower(),"target":host_id.lower(),"edge_type":"observed","evidence_event_id":event_id}]
    return []
