"""routers/play.py — Fictional intruder play mode endpoints."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Decoy
from app.routers.sensors import SensorPayload, _record
from app.services.sensor_pipeline.record import record_event

router = APIRouter(prefix="/api/play", tags=["safe intruder play"])


class ReadRequest(BaseModel):
    decoy_id: str
    actor_id: str = Field(default="play-actor", min_length=1, max_length=80)


class LoginRequest(BaseModel):
    """Honey-login via the play API (JSON version for the Intruder Play UI)."""
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=128)
    actor_id: str = Field(default="play-actor", min_length=1, max_length=80)


@router.get("/filesystem")
def filesystem(db: Session = Depends(get_db)):
    entries = [
        {
            "id": d.id, "name": d.name, "type": d.decoy_type,
            "host_id": d.host_id, "status": d.status,
            "path": f"/{d.host_id}/{d.name}",
            # Expose whether the decoy contains extractable honey credentials
            "has_honey_credentials": (
                d.decoy_type == "credential_note"
                and bool((d.content or {}).get("username"))
                and bool((d.content or {}).get("password"))
            ),
        }
        for d in db.query(Decoy).filter(Decoy.status == "deployed").order_by(Decoy.name).limit(200).all()
    ]
    return {
        "mode": "fictional-read-only-filesystem",
        "entries": entries,
        "restrictions": [
            "No shell commands", "No real filesystem access",
            "No real credentials", "Interactions are logged to synthetic sensors",
        ],
    }


@router.post("/read")
async def read_entry(payload: ReadRequest, db: Session = Depends(get_db)):
    decoy = db.get(Decoy, payload.decoy_id)
    if decoy is None or decoy.status != "deployed":
        raise HTTPException(status_code=404, detail="Deployed synthetic file not found")
    content = decoy.content or {}
    body = content.get("body") or json.dumps(content, indent=2, ensure_ascii=False)
    result = await _record(
        "file_read",
        SensorPayload(
            actor_id=payload.actor_id, host_id=decoy.host_id,
            decoy_id=decoy.id, token=decoy.token,
            action="play_read", breadcrumb_step=1,
            metadata={"source": "intruder_play",
                      "decoy_name": decoy.name, "decoy_type": decoy.decoy_type},
        ),
        db, decoy_sensitive=True,
    )
    return {
        "mode": "simulated-read",
        "actor_id": payload.actor_id,
        "decoy_id": decoy.id,
        "path": f"/{decoy.host_id}/{decoy.name}",
        "preview": str(body)[:4000],
        "event": result["event"],
        "alert": result.get("alert"),
        "notice": "Synthetic file body displayed. This read passed through the shared sensor pipeline; no operating-system file was read.",
    }


@router.post("/login")
async def play_login(payload: LoginRequest, db: Session = Depends(get_db)):
    """
    Fictional honey-credential login action for the Intruder Play UI.

    The player enters credentials they discovered in a credential_note decoy.
    - Match  → auth_attempt with credential_used=True, high-confidence alert, fictional dashboard.
    - No match → low-severity event, rejection message.
    No real authentication or shell access of any kind.
    """
    from app.routers.sensors import _match_credential, BENIGN_ACTORS
    from app.models import Node

    host = db.query(Node).filter(Node.hostname == "WEB-01").first()
    if host is None:
        raise HTTPException(status_code=503, detail="Fictional WEB-01 host is not seeded")

    is_benign = payload.actor_id in BENIGN_ACTORS
    matched_decoy = _match_credential(payload.username, payload.password, db)

    if matched_decoy:
        result = await record_event(
            event_type="auth_attempt",
            actor_id=payload.actor_id,
            host_id=host.id,
            decoy_id=matched_decoy.id,
            token=matched_decoy.token,
            action="honey_credential_login",
            credential_used=True,
            breadcrumb_step=2,
            benign=is_benign,
            metadata={
                "source": "intruder_play",
                "sensor": "play_login",
                "honey_login": True,
                "matched_decoy_id": matched_decoy.id,
                "matched_decoy_name": matched_decoy.name,
                "username_presented": payload.username,
                "force_alert": True,
            },
            simulated_timestamp=None,
            db=db, decoy_sensitive=True, auth_event=True,
        )
        # Fictional dashboard data
        nodes = db.query(Node).all()
        decoy_hosts = [
            {"hostname": n.hostname, "role": n.role, "status": "online (simulated)"}
            for n in nodes
        ]
        return {
            "mode": "honey-credential-match",
            "result": "access_granted_to_fictional_dashboard",
            "username": payload.username,
            "matched_decoy_id": matched_decoy.id,
            "matched_decoy_name": matched_decoy.name,
            "event": result["event"],
            "alert": result.get("alert"),
            "fictional_dashboard": {
                "title": "Northwind Logistics — Decoy Admin Dashboard",
                "warning": "FICTIONAL DECOY. No real systems. This access has been logged.",
                "hosts": decoy_hosts,
            },
            "notice": (
                "You used a honey credential found in a synthetic decoy note. "
                "A high-confidence alert has been raised. "
                "The fictional dashboard above lists simulator hosts only. "
                "No real authentication or system access occurred."
            ),
        }
    else:
        result = await record_event(
            event_type="auth_attempt",
            actor_id=payload.actor_id,
            host_id=host.id,
            decoy_id=None, token=None,
            action="failed_honey_login",
            credential_used=False,
            breadcrumb_step=1,
            benign=is_benign,
            metadata={
                "source": "intruder_play",
                "sensor": "play_login",
                "honey_login": True,
                "credential_match": False,
                "username_presented": payload.username,
                "force_low_alert": True,
            },
            simulated_timestamp=None,
            db=db, decoy_sensitive=True, auth_event=False,
        )
        return {
            "mode": "honey-credential-miss",
            "result": "access_denied",
            "username": payload.username,
            "event": result["event"],
            "alert": result.get("alert"),
            "notice": (
                "Credentials not found in any deployed decoy. "
                "This failed attempt has been logged as a low-severity event. "
                "Try reading a credential_note artifact first to find valid honey credentials."
            ),
        }
