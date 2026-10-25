from datetime import datetime
from pydantic import BaseModel, ConfigDict

class NodeOut(BaseModel):
    id: str
    hostname: str
    role: str
    zone: str
    status: str
    data_value: float
    description: str
    model_config = ConfigDict(from_attributes=True)

class EdgeOut(BaseModel):
    source: str
    target: str
    relation: str = "reachable-in-simulation"

class NetworkOut(BaseModel):
    nodes: list[NodeOut]
    edges: list[EdgeOut]

class AlertOut(BaseModel):
    id: str
    title: str
    severity: str
    confidence: float
    host_id: str | None
    status: str
    timestamp: datetime
    evidence: dict
    model_config = ConfigDict(from_attributes=True)

class HealthOut(BaseModel):
    status: str
    service: str
    version: str
    safety_mode: str
    adaption_mode: str = "cache"
    decoy_count: int = 0

