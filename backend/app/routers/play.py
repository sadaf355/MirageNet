from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Decoy
from app.routers.sensors import SensorPayload, _record
router=APIRouter(prefix="/api/play",tags=["safe intruder play"])
class ReadRequest(BaseModel):
    decoy_id:str
    actor_id:str=Field(default="play-actor",min_length=1,max_length=80)
@router.get("/filesystem")
def filesystem(db:Session=Depends(get_db)):
    return {"mode":"fictional-read-only-filesystem","entries":[{"id":d.id,"name":d.name,"type":d.decoy_type,"host_id":d.host_id,"status":d.status,"path":f"/{d.host_id}/{d.name}"} for d in db.query(Decoy).filter(Decoy.status=="deployed").order_by(Decoy.name).limit(200).all()],"restrictions":["No shell commands","No real filesystem access","No real credentials","Interactions are logged to synthetic sensors"]}
@router.post("/read")
async def read_entry(payload:ReadRequest,db:Session=Depends(get_db)):
    decoy=db.get(Decoy,payload.decoy_id)
    if decoy is None or decoy.status!="deployed": raise HTTPException(status_code=404,detail="Deployed synthetic file not found")
    content=decoy.content or {}
    import json
    body = content.get("body") or json.dumps(content, indent=2, ensure_ascii=False)
    result = await _record("file_read", SensorPayload(actor_id=payload.actor_id, host_id=decoy.host_id,
        decoy_id=decoy.id, token=decoy.token, action="play_read", breadcrumb_step=1,
        metadata={"source":"intruder_play","decoy_name":decoy.name,"decoy_type":decoy.decoy_type}),
        db, decoy_sensitive=True)
    return {"mode":"simulated-read","actor_id":payload.actor_id,"decoy_id":decoy.id,"path":f"/{decoy.host_id}/{decoy.name}",
            "preview":str(body)[:4000], "event":result["event"], "alert":result.get("alert"),
            "notice":"Synthetic file body displayed. This read passed through the shared sensor pipeline; no operating-system file was read."}
