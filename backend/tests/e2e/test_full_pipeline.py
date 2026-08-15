"""End-to-End Test for the Complete Multi-Phase Detection & Compliance Pipeline."""
import pytest
from datetime import datetime, timezone

from backend.app.data_generator.pipeline import DataGenerationPipeline
from backend.app.graph.graph_engine import TemporalGraph, GraphEngine
from backend.app.features import FeatureExtractor
from backend.app.ml.classifier import MuleClassifier

from backend.app.ml.explainability import ExplainabilityEngine
from backend.app.investigation.flow_b_service import FlowBService
from backend.app.alerts.dispatcher import AlertDispatcher
from backend.app.compliance.str_generator import STRGenerator
from backend.app.database.connection import get_db
from backend.app.database.repositories import ComponentRepository, AlertRepository, STRRepository
from backend.app.config import settings


def test_full_cross_bank_pipeline(temp_db, test_banks):
    """E2E Test: Full Detection -> Investigation -> Dispatch -> De-anonymize -> STR Pipeline."""
    # 1. Generate Synthetic Transactions across 4 Banks
    pipeline = DataGenerationPipeline(num_banks=4, contamination_rate=0.20)
    tx_df = pipeline.generate()
    assert len(tx_df) > 0, "Failed to generate synthetic transaction stream"

    # 2. Build Temporal Graph
    tg = TemporalGraph()
    for _, row in tx_df.iterrows():
        tg.add_transaction(
            edge_id=str(row.get("transaction_id", f"tx_{_}")),
            sender_hash=str(row["sender_hash"]),
            receiver_hash=str(row["receiver_hash"]),
            amount=float(row["amount"]),
            timestamp=datetime.fromisoformat(str(row["timestamp"])),
            bank_id=str(row["bank_id"]),
            local_risk_score=float(row.get("local_risk_score", 0.1))
        )

    assert tg.node_count > 0
    assert tg.edge_count > 0

    # 3. Flow A: Subgraph Extraction & ML Classification
    engine = GraphEngine(tg, settings)
    subgraphs = engine.extract_subgraphs(max_size=30, min_risk=0.0)
    assert len(subgraphs) > 0

    extractor = FeatureExtractor()
    classifier = MuleClassifier(model_type="xgboost")
    classifier.train()
    explainer = ExplainabilityEngine(classifier.model)

    detected_mules = []
    for sg in subgraphs:
        features = extractor.extract_features(sg, tg)
        prob = classifier.predict_proba(features)
        if prob >= 0.70:
            detected_mules.append((sg, features, prob))

    assert len(detected_mules) > 0, "Flow A failed to detect any mule clusters"

    # 4. Process Highest-Risk Cluster
    best_sg, best_features, best_prob = max(detected_mules, key=lambda x: x[2])
    explanation = explainer.explain_prediction(best_features)

    # 5. Store Component & Dispatch Alert
    with get_db(temp_db) as conn:
        comp_repo = ComponentRepository(conn)
        alert_repo = AlertRepository(conn)
        str_repo = STRRepository(conn)

        comp_id = f"comp_pipeline_{int(datetime.now(timezone.utc).timestamp())}"
        hashed_nodes = list(best_sg.nodes())
        bank_ids = list({d.get("bank_id", "bank_sbi") for u, v, d in best_sg.edges(data=True)})

        comp_repo.create({
            "id": comp_id,
            "hashed_nodes": hashed_nodes,
            "bank_ids": bank_ids,
            "risk_score": best_prob,
            "max_chain_length": len(best_sg.edges()),
            "total_volume": sum(d.get("amount", 1000) for u, v, d in best_sg.edges(data=True)),
            "avg_pass_through": best_features.get("pass_through_ratio", 0.9),
            "status": "active"
        })

        dispatcher = AlertDispatcher(bank_registry=test_banks, alert_repo=alert_repo)
        dispatch_res = dispatcher.dispatch_alert(
            component_id=comp_id,
            risk_score=best_prob,
            involved_banks=bank_ids,
            explanation=explanation
        )

        assert dispatch_res["status"] == "dispatched"
        assert len(dispatch_res["acknowledged_banks"]) > 0

        # 6. Flow B Investigation
        start_node = hashed_nodes[0]
        flow_b = FlowBService(tg, test_banks, settings)
        inv = flow_b.start_investigation(start_node=start_node, component_id=comp_id)

        assert inv.status == "completed"
        assert inv.depth_reached >= 1

        # 7. Regulatory STR Generation
        primary_bank = bank_ids[0] if bank_ids else "bank_sbi"
        str_gen = STRGenerator(test_banks, alert_repo=alert_repo, str_repo=str_repo)
        str_res = str_gen.generate_str(
            alert_id=dispatch_res["alert_id"],
            bank_id=primary_bank,
            account_number=f"{primary_bank.upper()[:4]}11223344",
            customer_name="Suspect Entity A",
            suspicion_reason="Automated cross-bank mule ring detection with 95%+ confidence",
            amount_involved=500000.0,
            supporting_evidence=["Graph Subgraph", "SHAP Feature Summary"]
        )

        assert str_res is not None
        assert "FIU-IND" in str_res["regulatory_agency"]


        # 8. Clean up investigation cryptographic state
        flow_b.close_investigation(inv.id, closed_by="compliance_officer")
        closed_inv = flow_b.get_investigation_result(inv.id)
        assert closed_inv["status"] == "closed"
