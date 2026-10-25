import networkx as nx
from sqlalchemy.orm import Session
from app.models import Node
from app.services.network_service import TOPOLOGY_EDGES

def placement_scores(db: Session) -> dict[str, float]:
    """Return L(h)=0.5*normalized betweenness + 0.5*normalized data value."""
    nodes = db.query(Node).all()
    if not nodes:
        return {}
    graph = nx.Graph()
    graph.add_nodes_from(n.id for n in nodes)
    graph.add_edges_from(TOPOLOGY_EDGES)
    centrality = nx.betweenness_centrality(graph, normalized=True)
    max_c = max(centrality.values(), default=0.0)
    max_v = max((n.data_value for n in nodes), default=1.0) or 1.0
    scores = {}
    for node in nodes:
        b = centrality.get(node.id, 0.0) / max_c if max_c else 0.0
        v = node.data_value / max_v
        scores[node.id] = round(0.5 * b + 0.5 * v, 4)
    return scores

TYPE_PREFERENCES = {
    "finance_hr": ("fs-01", "bkp-01"),
    "credential_note": ("ws-01", "jmp-01"),
    "config": ("jmp-01", "git-01"),
    "database": ("db-01", "bkp-01"),
    "api_artifact": ("web-01", "git-01"),
}

def choose_host(db: Session, ordinal: int = 0, decoy_type: str | None = None) -> tuple[str, float]:
    """Type-aware placement: prefer PRD-relevant hosts, then rank by L(h)."""
    scores = placement_scores(db)
    if not scores:
        raise ValueError("Network hosts must be seeded before placing decoys")
    preferred = TYPE_PREFERENCES.get(decoy_type or "", ())
    candidates = [host for host in preferred if host in scores] or list(scores)
    ranked = sorted(candidates, key=lambda host: (-scores[host], host))
    host_id = ranked[ordinal % len(ranked)]
    return host_id, scores[host_id]
