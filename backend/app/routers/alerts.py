from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Alert, Node
from app.services.stream import alert_stream

router = APIRouter(tags=["alerts"])

def serialize_alert(a: Alert) -> dict:
    return {"id": a.id, "title": a.title, "severity": a.severity, "confidence": a.confidence,
            "host_id": a.host_id, "status": a.status, "timestamp": a.timestamp.isoformat(),
            "evidence": a.evidence}

@router.get("/api/alerts")
def list_alerts(limit: int = 25, db: Session = Depends(get_db)):
    limit = max(1, min(limit, 100))
    return [serialize_alert(a) for a in db.query(Alert).order_by(Alert.timestamp.desc()).limit(limit).all()]

@router.get("/api/alerts/{alert_id}/siem")
def export_alert_siem(alert_id: str, db: Session = Depends(get_db)):
    """Export a single synthetic alert as a normalized SIEM/webhook JSON payload."""
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    host = db.get(Node, alert.host_id) if alert.host_id else None
    evidence = alert.evidence or {}
    return {
        "schema_version": "1.0", "event_kind": "miragenet.alert",
        "alert": {"id": alert.id, "title": alert.title, "severity": alert.severity,
                  "confidence": alert.confidence, "status": alert.status,
                  "timestamp": alert.timestamp.isoformat()},
        "asset": {"host_id": alert.host_id, "hostname": host.hostname if host else alert.host_id},
        "actor": {"id": evidence.get("actor_id")},
        "detection": {"source": "MirageNet synthetic sensor", "mode": "sandbox-only",
                      "event_id": evidence.get("event_id"), "technique": evidence.get("technique")},
        "evidence": evidence,
        "response": {"recommended": "Review synthetic evidence; do not take real-world action."}
    }

@router.websocket("/ws/alerts")
async def alerts_stream(websocket: WebSocket):
    await alert_stream.connect(websocket)
    try:
        await websocket.send_json({"type": "connected", "message": "MirageNet alert stream ready",
                                   "mode": "synthetic-sandbox-only"})
        while True:
            # Client may send a lightweight keepalive; no commands are executed.
            await websocket.receive_text()
    except WebSocketDisconnect:
        alert_stream.disconnect(websocket)
