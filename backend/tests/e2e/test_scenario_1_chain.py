"""End-to-End Test for Scenario 1: Fast 4-Bank Rapid Chain."""
import pytest
from datetime import datetime, timezone

from backend.app.graph.graph_engine import TemporalGraph, GraphEngine
from backend.app.features import FeatureExtractor
from backend.app.ml.classifier import MuleClassifier

from backend.app.ml.explainability import ExplainabilityEngine
from backend.app.investigation.traversal import PatternDecayTraversal
from backend.app.investigation.flow_b_service import FlowBService
from backend.app.alerts.dispatcher import AlertDispatcher
from backend.app.compliance.str_generator import STRGenerator
from backend.app.database.repositories import ComponentRepository, AlertRepository, STRRepository
from backend.app.database.connection import get_db
from backend.app.config import settings


def test_scenario_1_fast_4_bank_chain(temp_db, test_banks, test_scenario_data):
    """E2E Test: Fast 4-Bank Rapid Chain (A -> B -> C -> D)."""
    s1_data = test_scenario_data["scenario_1"]
    edges = s1_data["edges"]
    banks = s1_data["banks"]
    hashes = s1_data["hashes"]

    # 1. Build Temporal Graph
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

    assert tg.node_count >= 4, f"Expected at least 4 nodes, got {tg.node_count}"
    assert tg.edge_count >= 3, f"Expected at least 3 edges, got {tg.edge_count}"

    # 2. Graph Engine Flow A: Subgraph Extraction & Features
    engine = GraphEngine(tg, settings)
    subgraphs = engine.extract_subgraphs(max_size=20, min_risk=0.0)
    assert len(subgraphs) > 0, "Failed to extract subgraphs for rapid chain"

    primary_subgraph = subgraphs[0]
    involved_banks = set()
    for u, v, data in primary_subgraph.edges(data=True):
        if "bank_id" in data:
            involved_banks.add(data["bank_id"])

    # 3. Feature Extraction
    extractor = FeatureExtractor()
    features = extractor.extract_features(primary_subgraph, tg)
    assert "pass_through_ratio" in features
    assert features["pass_through_ratio"] >= 0.80

    # 4. ML Classification & Detection
    classifier = MuleClassifier(model_type="xgboost")
    classifier.train()  # Auto-trains synthetic baseline if not fitted
    risk_score = classifier.predict_proba(features)
    is_mule = classifier.predict(features, threshold=0.75)

    assert is_mule, "Model failed to classify 4-bank rapid chain as mule"
    assert risk_score > 0.85, f"Risk score {risk_score} should be > 0.85"

    # 5. SHAP Explainability
    explainer = ExplainabilityEngine(classifier.model)
    explanation = explainer.explain_prediction(features)
    assert explanation is not None
    assert "summary" in explanation
    assert "feature_importance" in explanation
    assert len(explanation["feature_importance"]) > 0

    # 6. Flow B Investigation Traversal
    traversal = PatternDecayTraversal(tg, settings)
    target_node = hashes[0]
    trav_res = traversal.traverse_from_node(target_node, direction="out", max_depth=7)

    assert trav_res.depth_reached >= 3, f"Expected traversal depth >= 3, got {trav_res.depth_reached}"
    assert len(trav_res.nodes_visited) >= 4, f"Expected >= 4 visited nodes, got {len(trav_res.nodes_visited)}"
    assert len(trav_res.banks_queried) >= 3, f"Expected >= 3 banks queried, got {len(trav_res.banks_queried)}"
    assert trav_res.stopping_reason in ["hard_cap", "pattern_decay", "time_gap", "completed"]


    # 7. Alert Dispatch to All 4 Banks
    with get_db(temp_db) as conn:
        comp_repo = ComponentRepository(conn)
        alert_repo = AlertRepository(conn)
        str_repo = STRRepository(conn)

        # Store component
        comp_id = f"comp_s1_{int(datetime.now(timezone.utc).timestamp())}"
        comp_repo.create({
            "id": comp_id,
            "hashed_nodes": list(hashes),
            "bank_ids": list(banks),
            "risk_score": risk_score,
            "max_chain_length": 4,
            "total_volume": 500000.0,
            "avg_pass_through": 0.98,
            "status": "active"
        })

        dispatcher = AlertDispatcher(bank_registry=test_banks, alert_repo=alert_repo)
        dispatch_res = dispatcher.dispatch_alert(
            component_id=comp_id,
            risk_score=risk_score,
            involved_banks=banks,
            explanation=explanation
        )

        assert dispatch_res["status"] == "dispatched"
        assert len(dispatch_res["acknowledged_banks"]) == 4, f"All 4 banks must acknowledge, got {dispatch_res['acknowledged_banks']}"

        # 8. Bank Compliance STR Generation
        str_gen = STRGenerator(test_banks, alert_repo=alert_repo, str_repo=str_repo)
        str_res = str_gen.generate_str(
            alert_id=dispatch_res["alert_id"],
            bank_id="bank_sbi",
            account_number="SBIN00000001",
            customer_name="Rajesh Kumar",
            suspicion_reason="4-Bank Rapid High Velocity Mule Chain (Pass-Through: 98%)",
            amount_involved=500000.0,
            supporting_evidence=["Graph Chain Motif", "SHAP Feature Attribution: Pass-Through 0.98"]
        )

        assert str_res is not None
        assert "str_id" in str_res
        assert "FIU-IND" in str_res["regulatory_agency"]
        assert str_res["amount_involved"] == 500000.0

        # Submit STR
        sub_res = str_gen.submit_str(str_res["str_id"])
        assert sub_res["status"] in ["submitted", "accepted"]
        assert "fiu_ack" in sub_res or "acknowledgment_id" in sub_res

