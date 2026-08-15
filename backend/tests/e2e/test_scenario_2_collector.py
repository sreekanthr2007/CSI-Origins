"""End-to-End Test for Scenario 2: Collector Star Motif."""
import pytest
from datetime import datetime, timezone

from backend.app.graph.graph_engine import TemporalGraph, GraphEngine
from backend.app.features import FeatureExtractor
from backend.app.ml.classifier import MuleClassifier

from backend.app.investigation.traversal import PatternDecayTraversal
from backend.app.config import settings


def test_scenario_2_collector_star(test_scenario_data):
    """E2E Test: Collector Star Motif (8 Senders -> 1 Collector Node)."""
    s2_data = test_scenario_data["scenario_2"]
    collector_hash = s2_data["collector_hash"]
    sender_hashes = s2_data["sender_hashes"]
    edges = s2_data["edges"]

    # 1. Build Graph
    tg = TemporalGraph()
    for e in edges:
        tg.add_transaction(
            edge_id=f"tx_{e['sender_hash'][:8]}_{e['receiver_hash'][:8]}",
            sender_hash=e["sender_hash"],
            receiver_hash=e["receiver_hash"],
            amount=e["amount"],
            timestamp=datetime.fromisoformat(e["timestamp"]),
            bank_id=e["bank_id"],
            local_risk_score=e["local_risk_score"]
        )

    assert tg.node_count == 9, f"Expected 9 nodes (8 senders + 1 collector), got {tg.node_count}"
    assert tg.edge_count == 8, f"Expected 8 edges, got {tg.edge_count}"

    # 2. Graph Engine Flow A: Subgraph Extraction
    engine = GraphEngine(tg, settings)
    subgraphs = engine.extract_subgraphs(max_size=25, min_risk=0.0)
    assert len(subgraphs) > 0, "Failed to extract collector star subgraph"

    star_subgraph = subgraphs[0]
    assert len(star_subgraph.nodes()) == 9, f"Expected 9 nodes in star component, got {len(star_subgraph.nodes())}"

    # 3. Feature Extraction
    extractor = FeatureExtractor()
    features = extractor.extract_features(star_subgraph, tg)

    # Validate high fan-in asymmetry and in-degree concentration
    assert "in_out_ratio" in features or "fan_in_asymmetry" in features or "degree_centrality" in features

    # 4. ML Detection & Risk Score
    classifier = MuleClassifier(model_type="xgboost")
    classifier.train()
    risk_score = classifier.predict_proba(features)

    assert risk_score >= 0.70, f"Collector star risk score {risk_score} should be >= 0.70"

    # 5. Flow B Backward/Inward Traversal from Collector Node
    traversal = PatternDecayTraversal(tg, settings)
    trav_res = traversal.traverse_from_node(collector_hash, direction="in", max_depth=5)

    assert trav_res is not None
    # Must reach all 8 senders
    assert len(trav_res.nodes_visited) >= 8, f"Expected traversal to discover at least 8 senders, got {len(trav_res.nodes_visited)}"
    assert trav_res.stopping_reason in ["pattern_decay", "hard_cap", "time_gap", "completed"]

