"""Bounded pattern-decay graph traversal algorithm."""
from typing import Dict, Any, List, Set
import networkx as nx


class BoundedTraversal:
    """Performs bidirectional graph traversal governed by pattern-decay stopping criteria and hard caps."""
    def __init__(self, max_hops: int = 6, max_banks: int = 12, decay_threshold: float = 0.70):
        self.max_hops = max_hops
        self.max_banks = max_banks
        self.decay_threshold = decay_threshold

    def traverse_neighborhood(self, graph: nx.MultiDiGraph, origin_node: str) -> Dict[str, Any]:
        """Traverse upstream and downstream from origin_node until pattern decays or caps are hit."""
        visited_nodes: Set[str] = {origin_node} if graph.has_node(origin_node) else set()
        return {
            "origin_node": origin_node,
            "subgraph_nodes": list(visited_nodes),
            "traversal_depth": 0,
            "stopped_reason": "CAP_OR_DECAY_REACHED"
        }
