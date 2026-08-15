"""End-to-End Test for Scenario 3: Distributor & Smurfing Ring."""
import pytest
from datetime import datetime, timezone

from backend.app.graph.graph_engine import TemporalGraph, GraphEngine
from backend.app.features import FeatureExtractor
from backend.app.ml.classifier import MuleClassifier

from backend.app.investigation.traversal import PatternDecayTraversal
from backend.app.config import settings


def test_scenario_3_distributor_smurfing(test_scenario_data):
    """E2E Test: Distributor & Smurfing Ring (1 Hub -> 10 Receivers under ₹50k threshold)."""
    s3_data = test_scenario_data["scenario_3"]
    hub_hash = s3_data["hub_hash"]
    receiver_hashes = s3_data["receiver_hashes"]
    edges = s3_data["edges"]

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

    assert tg.node_count == 11, f"Expected 11 nodes (1 hub + 10 receivers), got {tg.node_count}"
    assert tg.edge_count == 10, f"Expected 10 edges, got {tg.edge_count}"

    # 2. Graph Engine Flow A: Subgraph Extraction
    engine = GraphEngine(tg, settings)
    subgraphs = engine.extract_subgraphs(max_size=30, min_risk=0.0)
    assert len(subgraphs) > 0, "Failed to extract distributor smurfing subgraph"

    smurf_subgraph = subgraphs[0]
    assert len(smurf_subgraph.nodes()) == 11

    # 3. Feature Extraction
    extractor = FeatureExtractor()
    features = extractor.extract_features(smurf_subgraph, tg)

    # Validate structuring and burst distribution patterns
    assert "structuring_score" in features or "out_degree_entropy" in features or "cross_bank_velocity" in features

    # 4. ML Detection & Risk Score
    classifier = MuleClassifier(model_type="xgboost")
    classifier.train()
    risk_score = classifier.predict_proba(features)

    assert risk_score >= 0.70, f"Smurfing distributor risk score {risk_score} should be >= 0.70"

    # 5. Flow B Outward Traversal from Distributor Hub
    traversal = PatternDecayTraversal(tg, settings)
    trav_res = traversal.traverse_from_node(hub_hash, direction="out", max_depth=5)

    assert trav_res is not None
    # Must visit all 10 receivers
    assert len(trav_res.nodes_visited) >= 10, f"Expected traversal to reach at least 10 receivers, got {len(trav_res.nodes_visited)}"
