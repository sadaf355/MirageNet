from sqlalchemy.orm import Session
from app.models import Node

HOSTS = [
    ("web-01", "WEB-01", "DMZ web application", "DMZ", 0.55, "Public-facing fictional web tier."),
    ("ws-01", "WS-01", "Employee workstation", "CORP", 0.45, "Synthetic employee workstation."),
    ("fs-01", "FS-01", "Finance / HR file server", "CORP", 0.92, "Contains only synthetic finance and HR artifacts."),
    ("jmp-01", "JMP-01", "Admin jump host", "ADMIN", 0.82, "Simulated administrative pivot point."),
    ("db-01", "DB-01", "Customer database", "RESTRICTED", 1.00, "Synthetic customer records only."),
    ("git-01", "GIT-01", "Code server", "RESTRICTED", 0.78, "Fictional source repository host."),
    ("bkp-01", "BKP-01", "Backup server", "RESTRICTED", 0.72, "Synthetic backup repository."),
]

def seed_nodes(db: Session) -> None:
    if db.query(Node).first():
        return
    for ident, hostname, role, zone, value, description in HOSTS:
        db.add(Node(id=ident, hostname=hostname, role=role, zone=zone, status="online",
                    data_value=value, description=description))
    db.commit()
