from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.network_service import get_network

router = APIRouter(prefix="/api/network", tags=["network"])

@router.get("")
def network(db: Session = Depends(get_db)):
    data = get_network(db)
    return {"nodes": [
        {"id": n.id, "hostname": n.hostname, "role": n.role, "zone": n.zone,
         "status": n.status, "data_value": n.data_value, "description": n.description,
         "centrality": round(data["centrality"].get(n.id, 0), 3)}
        for n in data["nodes"]
    ], "edges": [e.model_dump() for e in data["edges"]]}
