"""Sensor-specific parsing and decoy credential matching helpers."""
from __future__ import annotations
import re
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from app.models import Decoy


def edge_evidence(metadata: dict, event_id: str, host_id: str) -> list[dict]:
    if metadata.get('observed_transition') and metadata.get('source_host'):
        return [{"source": str(metadata['source_host']).lower(), "target": host_id.lower(), "edge_type": "observed", "evidence_event_id": event_id}]
    return []


def extract_credentials(decoy: Decoy) -> list[tuple[str, str]]:
    """Extract list of (username, password) tuples from a deployed decoy."""
    creds: list[tuple[str, str]] = []
    content = decoy.content or {}
    if content.get("username") and content.get("password"):
        creds.append((str(content["username"]).strip(), str(content["password"]).strip()))

    body = content.get("body", "")
    if body and isinstance(body, str):
        # Match 'Username: <user>\nPassword: <pass>'
        for u, p in re.findall(r"(?i)username\s*[:=]\s*([^\r\n]+)[\r\n]+\s*password\s*[:=]\s*([^\r\n]+)", body):
            creds.append((u.strip(), p.strip()))
        # Match CSV rows like 'https://...,user,pass'
        for line in body.splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3 and not parts[0].lower().startswith("url") and parts[0].startswith("http"):
                creds.append((parts[1], parts[2]))
    return creds


def match_credential(username: str, password: str, db: Session) -> Decoy | None:
    """Return the deployed credential_note decoy that contains this username and password, or None."""
    from app.models import Decoy
    u_clean = username.strip()
    p_clean = password.strip()
    if not u_clean or not p_clean:
        return None

    decoys = db.query(Decoy).filter(
        Decoy.status == "deployed",
        Decoy.decoy_type == "credential_note",
    ).all()

    for decoy in decoys:
        for u, p in extract_credentials(decoy):
            if u == u_clean and p == p_clean:
                return decoy
    return None
