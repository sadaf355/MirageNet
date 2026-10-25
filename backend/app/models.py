from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

def utcnow():
    return datetime.now(timezone.utc)

class Node(Base):
    __tablename__ = "nodes"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    hostname: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    role: Mapped[str] = mapped_column(String(80))
    zone: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(24), default="online")
    data_value: Mapped[float] = mapped_column(Float, default=0.5)
    description: Mapped[str] = mapped_column(Text, default="Fictional lab host")

class Decoy(Base):
    __tablename__ = "decoys"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    decoy_type: Mapped[str] = mapped_column(String(48))
    host_id: Mapped[str] = mapped_column(ForeignKey("nodes.id"), index=True)
    token: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    enticement_score: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(24), default="staged")
    content: Mapped[dict] = mapped_column(JSON, default=dict)

class Event(Base):
    __tablename__ = "events"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    host_id: Mapped[str | None] = mapped_column(ForeignKey("nodes.id"), nullable=True, index=True)
    actor_id: Mapped[str] = mapped_column(String(80), default="simulated-actor")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)

class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(80), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(24), default="observing")

class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    title: Mapped[str] = mapped_column(String(180))
    severity: Mapped[str] = mapped_column(String(16), index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    host_id: Mapped[str | None] = mapped_column(ForeignKey("nodes.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="open")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)

class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    title: Mapped[str] = mapped_column(String(180))
    status: Mapped[str] = mapped_column(String(24), default="investigating")
    severity: Mapped[str] = mapped_column(String(16), default="medium")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    summary: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
