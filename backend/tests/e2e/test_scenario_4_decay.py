"""End-to-End Test for Scenario 4: Traversal Decay & False Positive Prevention."""
import pytest
from datetime import datetime, timezone

from backend.app.graph.graph_engine import TemporalGraph, GraphEngine
from backend.app.features import FeatureExtractor
from backend.app.ml.classifier import MuleClassifier

from backend.app.investigation.traversal import PatternDecayTraversal
from backend.app.config import settings


def test_scenario_4_traversal_decay_legitimate(test_scenario_data):
    """E2E Test: Legitimate Multi-Day Hold and Traversal Decay."""
    s4_data = test_scenario_data["scenario_4"]
    legit_hash = s4_data["legit_hash"]
    edges = s4_data["edges"]

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

    assert tg.node_count >= 3
    assert tg.edge_count == 2

    # 2. Graph Engine Flow A: Subgraph Extraction & Features
    engine = GraphEngine(tg, settings)
    subgraphs = engine.extract_subgraphs(max_size=10, min_risk=0.0)
    assert len(subgraphs) > 0

    legit_subgraph = subgraphs[0]
    extractor = FeatureExtractor()
    features = extractor.extract_features(legit_subgraph, tg)

    # Validate pass-through ratio is low (e.g. 20%) and hold time is high (> 72 hours)
    assert "pass_through_ratio" in features
    assert features["pass_through_ratio"] <= 0.50, f"Expected pass through <= 0.50, got {features['pass_through_ratio']}"

    # 3. ML Classifier Prediction (False Positive Check)
    classifier = MuleClassifier(model_type="xgboost")
    classifier.train()
    risk_score = classifier.predict_proba(features)
    is_mule = classifier.predict(features, threshold=0.70)

    assert not is_mule, "Legitimate account should NOT be flagged as mule"
    assert risk_score < 0.50, f"Legitimate risk score {risk_score} should be < 0.50"

    # 4. Flow B Traversal Bounded Decay Validation
    traversal = PatternDecayTraversal(tg, settings)
    trav_res = traversal.traverse_from_node(legit_hash, direction="both", max_depth=7)

    # Traversal should stop very early (<= 2 hops) due to hold time gap (> 72h) or pass-through decay (< 0.60)
    assert trav_res.depth_reached <= 2, f"Expected decay to stop traversal <= 2 hops, reached depth {trav_res.depth_reached}"
    assert trav_res.stopping_reason in ["pattern_decay", "time_gap", "hard_cap", "completed"]

