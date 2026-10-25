from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Decoy
from app.services.forge import forge_decoys, serialize_decoy, rotate_decoy

router = APIRouter(tags=["decoys"])

class ForgeRequest(BaseModel):
    count: int = Field(default=60, ge=1, le=200)
    company_profile: str | None = Field(default=None, max_length=120)

@router.get("/api/decoys")
def list_decoys(db: Session = Depends(get_db)):
    rows = db.query(Decoy).order_by(Decoy.name).all()
    return [serialize_decoy(d) for d in rows]

@router.post("/api/forge/run")
def run_forge(payload: ForgeRequest = ForgeRequest(), db: Session = Depends(get_db)):
    try:
        return forge_decoys(db, payload.count, company_profile=payload.company_profile)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.post("/api/deploy")
def deploy_decoys(db: Session = Depends(get_db)):
    rows = db.query(Decoy).filter(Decoy.status == "staged").all()
    for decoy in rows:
        decoy.status = "deployed"
    db.commit()
    return {"deployed": len(rows), "status": "deployed",
            "message": "Artifacts marked deployed inside the synthetic simulator only."}

@router.post("/api/decoys/{decoy_id}/burn")
def burn_decoy(decoy_id: str, db: Session = Depends(get_db)):
    decoy = db.get(Decoy, decoy_id)
    if not decoy:
        raise HTTPException(status_code=404, detail="Decoy not found")
    replacement = rotate_decoy(db, decoy)
    return {"id": decoy.id, "status": decoy.status, "replacement": serialize_decoy(replacement),
            "message": "Old synthetic token burned and replaced with a fresh unique synthetic artifact. No real credential was revoked."}
