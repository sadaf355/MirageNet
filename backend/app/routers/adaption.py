from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Decoy
from app.services.adaption_integration import status, generate_decoys, generate_sessions, build_cache
from app.services.forge import forge_decoys

router = APIRouter(prefix="/api/adaption", tags=["adaption"])

class GenerateRequest(BaseModel):
    rows: int = Field(default=200, ge=150, le=200)

class SessionRequest(BaseModel):
    rows: int = Field(default=30, ge=20, le=50)

@router.get("/status")
def adaption_status():
    return status()

@router.post("/generate-decoys")
def run_adaption_decoys(payload: GenerateRequest = GenerateRequest(), db: Session = Depends(get_db)):
    try:
        result = generate_decoys(payload.rows)
        retained = int(result.get("retained", result.get("retained_rows", 0)))
        if retained > 0:
            count = min(200, retained)
            forged = forge_decoys(db, count, company_profile="Northwind Logistics · Adaption/cache corpus")
            result["deployed_before"] = db.query(Decoy).filter(Decoy.status == "deployed").count()
            result["staged_created"] = forged["created"]
            result["source_mode"] = forged["source_mode"]
            result["decoys"] = forged["decoys"]
        else:
            result["staged_created"] = 0
        result["deployed_count"] = db.query(Decoy).filter(Decoy.status == "deployed").count()
        result["staged_count"] = db.query(Decoy).filter(Decoy.status == "staged").count()
        result["message"] = str(result.get("message", "")) + " Generated, retained, staged, and deployed counts are reported separately."
        return result
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Adaption generation failed: {exc}") from exc

@router.post("/generate-sessions")
def run_adaption_sessions(payload: SessionRequest = SessionRequest()):
    try:
        return generate_sessions(payload.rows)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Adaption session generation failed: {exc}") from exc

@router.post("/build-cache")
def rebuild_cache():
    try:
        return build_cache(generated_limit=200, threshold=0.85)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not build decoy cache: {exc}") from exc


@router.put("/evidence/screenshot")
async def save_adaption_screenshot(request: Request):
    """Save a real user-captured Adaption job screenshot; no generated/fake screenshots."""
    content_type = request.headers.get("content-type", "").lower()
    if content_type not in {"image/png", "image/jpeg"}:
        raise HTTPException(status_code=415, detail="Upload a PNG or JPEG screenshot captured from the actual Adaption job UI.")
    body = await request.body()
    if len(body) < 8 or len(body) > 12 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Screenshot must be between 8 bytes and 12 MB.")
    is_png = body.startswith(b"\x89PNG\r\n\x1a\n")
    is_jpeg = body.startswith(b"\xff\xd8\xff")
    if not (is_png or is_jpeg):
        raise HTTPException(status_code=400, detail="File signature does not match PNG/JPEG screenshot content.")
    from pathlib import Path
    from app.services.adaption_integration import ROOT, write_manifest
    relative = "data/adaption_evidence/adaption_job_screenshot.png" if is_png else "data/adaption_evidence/adaption_job_screenshot.jpg"
    target = ROOT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(body)
    manifest = write_manifest({"screenshot": relative, "screenshot_captured_by_user": True})
    return {"saved": True, "path": relative, "bytes": len(body), "manifest": manifest}
