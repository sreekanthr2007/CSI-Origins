"""Connected component extraction and mule network risk detection."""
import logging
from typing import Dict, Any, List, Optional, Union, Set
import networkx as nx
import numpy as np

from backend.app.config import settings, Settings
from backend.app.graph.graph_engine import TemporalGraph
from backend.app.features.feature_extractor import FeatureExtractor

logger = logging.getLogger("mule-detection-components")


class ComponentDetector:
    """Detects connected subgraphs and calculates cross-bank mule network risk scores."""

    def __init__(self, graph: Union[TemporalGraph, nx.MultiDiGraph], config: Optional[Settings] = None):
        if isinstance(graph, TemporalGraph):
            self.temporal_graph = graph
            self.nx_graph: nx.MultiDiGraph = graph.graph
        elif isinstance(graph, (nx.MultiDiGraph, nx.DiGraph)):
            self.temporal_graph = None
            self.nx_graph = graph
        else:
            raise ValueError(f"Unsupported graph type: {type(graph)}")

        self.config = config or settings
        self.feature_extractor = FeatureExtractor(graph=graph, config=self.config)

    def get_all_components(self) -> List[List[str]]:
        """Return all weakly connected components as lists of node hashes."""
        if self.nx_graph.number_of_nodes() == 0:
            return []
        undirected = self.nx_graph.to_undirected(as_view=True)
        components = [list(c) for c in nx.connected_components(undirected)]
        # Sort components descending by size
        components.sort(key=len, reverse=True)
        return components

    def _compute_component_risk(self, component_nodes: List[str]) -> float:
        """Calculate multi-factor risk score [0.0 - 1.0] for a connected subgraph.
        
        Combines:
        1. Average pass-through ratio (30%)
        2. Maximum chain length (20%)
        3. Cross-bank diversity (20%)
        4. Temporal compression / rapid velocity (15%)
        5. Node behavioral risk & high pass-through proportion (15%)
        """
        if not component_nodes:
            return 0.0

        comp_feats = self.feature_extractor.extract_component_features(component_nodes)
        
        # 1. Pass-through score
        avg_pt = comp_feats.get("avg_pass_through", 0.0)
        pt_score = min(max(avg_pt, 0.0), 1.0)

        # 2. Chain length score (normalized against max depth ~4-6)
        max_chain = comp_feats.get("max_chain_length", 1)
        chain_score = min(max_chain / 3.0, 1.0)

        # 3. Cross-bank score (cross-bank hopping is a hallmark of mule networks)
        num_banks = comp_feats.get("num_banks", 1)
        bank_score = min(num_banks / 2.0, 1.0)

        # 4. Temporal compression score: fast money traversal increases risk
        traversal_mins = comp_feats.get("avg_traversal_time", 60.0)
        if traversal_mins <= 0.0:
            velocity_score = 0.5
        elif traversal_mins <= 30.0:
            velocity_score = 1.0
        elif traversal_mins <= 180.0:
            velocity_score = 0.85
        elif traversal_mins <= 1440.0:
            velocity_score = 0.65
        else:
            velocity_score = 0.40

        # 5. High pass-through nodes ratio
        high_pt_nodes = comp_feats.get("high_pass_through_nodes", 0)
        node_ratio_score = high_pt_nodes / max(len(component_nodes), 1)

        # Weighted combination
        raw_risk = (
            (0.30 * pt_score) +
            (0.20 * chain_score) +
            (0.20 * bank_score) +
            (0.15 * velocity_score) +
            (0.15 * node_ratio_score)
        )

        # Non-linear boost for strong combined indicators
        if avg_pt >= 0.70 and max_chain >= 3 and num_banks >= 2:
            raw_risk = min(raw_risk * 1.25, 0.99)

        return round(float(min(max(raw_risk, 0.0), 1.0)), 4)

    def get_components_with_risk(self, min_size: int = 2) -> List[Dict[str, Any]]:
        """Return connected components filtered by minimum size with calculated risk metadata."""
        all_comps = self.get_all_components()
        results: List[Dict[str, Any]] = []

        for nodes in all_comps:
            if len(nodes) < min_size:
                continue

            sub = self.nx_graph.subgraph(nodes)
            banks: Set[str] = set()
            total_vol = 0.0
            for _, _, d in sub.edges(data=True):
                total_vol += float(d.get("amount", 0.0))
                b_id = d.get("bank_id")
                if b_id:
                    banks.add(b_id)

            comp_feats = self.feature_extractor.extract_component_features(nodes)
            risk = self._compute_component_risk(nodes)

            results.append({
                "nodes": nodes,
                "size": len(nodes),
                "banks": sorted(list(banks)),
                "total_volume": round(float(total_vol), 2),
                "avg_pass_through": comp_feats.get("avg_pass_through", 0.0),
                "max_chain_length": comp_feats.get("max_chain_length", 1),
                "risk_score": risk
            })

        # Sort descending by risk_score
        results.sort(key=lambda c: c["risk_score"], reverse=True)
        return results

    def prune_component(self, component_nodes: List[str], min_pass_through: float = 0.6) -> List[str]:
        """Prune component by removing peripheral nodes with pass-through below threshold."""
        pruned = []
        for n in component_nodes:
            pt = self.feature_extractor._calculate_pass_through(n)
            if pt >= min_pass_through:
                pruned.append(n)
        return pruned
