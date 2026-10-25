from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Alert, Decoy, Incident, Node
from app.schemas import HealthOut

router = APIRouter(prefix="/api", tags=["system"])

@router.get("/health", response_model=HealthOut)
def health(db: Session = Depends(get_db)):
    import os
    is_live = bool(os.getenv("ADAPTION_API_KEY", "").strip())
    adaption_mode = "live" if is_live else "cache"
    decoy_count = db.query(Decoy).count()
    return {"status": "ok", "service": "miragenet-api", "version": "0.1.0",
            "safety_mode": "synthetic-sandbox-only",
            "adaption_mode": adaption_mode,
            "decoy_count": decoy_count}

@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    return {
        "hosts_online": db.query(Node).filter(Node.status == "online").count(),
        "hosts_total": db.query(Node).count(),
        "decoys_deployed": db.query(Decoy).filter(Decoy.status == "deployed").count(),
        "decoys_total": db.query(Decoy).count(),
        "open_alerts": db.query(Alert).filter(Alert.status == "open").count(),
        "active_incidents": db.query(Incident).filter(Incident.status != "closed").count(),
        "detection_rate": None,
        "system_status": "operational",
        "environment": "SIMULATION",
    }


@router.post("/reset")
def reset_demo_state(db: Session = Depends(get_db)):
    """Reset simulator records and recreate a deterministic 60-decoy demo inventory."""
    from app.models import Event, Session as ActorSession
    from app.services.forge import forge_decoys
    # Delete dependent history first; hosts remain stable and are reseeded if missing.
    for model in (Alert, Incident, Event, ActorSession, Decoy):
        db.query(model).delete(synchronize_session=False)
    db.commit()
    from app.seed import seed_nodes
    seed_nodes(db)
    result = forge_decoys(db, 60, company_profile="Northwind Logistics demo")
    staged = db.query(Decoy).filter(Decoy.status == "staged").all()
    for decoy in staged:
        decoy.status = "deployed"
    db.commit()
    return {"status": "reset", "decoys_created": len(staged), "decoys_deployed": len(staged),
            "events": 0, "alerts": 0, "incidents": 0,
            "breadcrumb_chain": result.get("breadcrumb_chain"),
            "message": "Demo state reset. Hosts retained; 60 synthetic decoys freshly forged and deployed."}
