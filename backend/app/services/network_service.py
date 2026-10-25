import networkx as nx
from sqlalchemy.orm import Session
from app.models import Node
from app.schemas import EdgeOut

# Required PRD topology. Edges represent reachability inside the fictional simulator only.
TOPOLOGY_EDGES = [
    ("web-01", "ws-01"),
    ("ws-01", "fs-01"),
    ("ws-01", "jmp-01"),
    ("jmp-01", "db-01"),
    ("jmp-01", "git-01"),
    ("jmp-01", "bkp-01"),
    ("fs-01", "bkp-01"),
]

def get_network(db: Session) -> dict:
    nodes = db.query(Node).order_by(Node.id).all()
    graph = nx.Graph()
    graph.add_nodes_from(n.id for n in nodes)
    graph.add_edges_from(TOPOLOGY_EDGES)
    edges = [EdgeOut(source=a, target=b) for a, b in TOPOLOGY_EDGES]
    return {"nodes": nodes, "edges": edges, "centrality": nx.betweenness_centrality(graph)}
