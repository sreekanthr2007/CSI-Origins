"""Central graph construction and query engine."""
from typing import Dict, Any, List
import networkx as nx


class GraphEngine:
    """Ingests boundary-crossing edges and builds a directed multi-edge temporal graph."""
    def __init__(self):
        self.graph = nx.MultiDiGraph()

    def add_edge_record(self, sender_hash: str, receiver_hash: str, attributes: Dict[str, Any]) -> None:
        """Add a transaction edge record between two hashed accounts."""
        self.graph.add_edge(sender_hash, receiver_hash, **attributes)

    def get_summary(self) -> Dict[str, int]:
        """Return basic graph statistics."""
        return {
            "nodes_count": self.graph.number_of_nodes(),
            "edges_count": self.graph.number_of_edges()
        }
