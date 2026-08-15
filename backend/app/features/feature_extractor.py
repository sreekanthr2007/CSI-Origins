"""Structural and behavioral feature extraction module."""
from typing import Dict, Any
import networkx as nx


class FeatureExtractor:
    """Computes pass-through ratios, velocities, fan-in/fan-out asymmetries, and behavioral features."""
    def __init__(self, graph: nx.MultiDiGraph):
        self.graph = graph

    def extract_node_features(self, node_id: str) -> Dict[str, Any]:
        """Compute structural features for a given node in the graph."""
        in_degree = self.graph.in_degree(node_id) if self.graph.has_node(node_id) else 0
        out_degree = self.graph.out_degree(node_id) if self.graph.has_node(node_id) else 0
        return {
            "node_id": node_id,
            "in_degree": in_degree,
            "out_degree": out_degree,
            "pass_through_ratio": 0.0,
            "velocity_minutes": 0.0
        }
