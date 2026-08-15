"""Integration tests for end-to-end multi-bank alert dispatch, de-anonymization, and STR filing."""
import time
import pytest
from backend.app.bank_node.bank_client import initialize_bank_nodes, BankNode
from backend.app.alerts.dispatcher import AlertDispatcher, AlertStatus
from backend.app.compliance.str_generator import STRGenerator
from backend.app.database.repositories import ComponentRepository


def test_end_to_end_alert_flow():
    """Check 7.18 & 7.26 & 7.27: End-to-end flow from component -> alert -> bank ACK -> de-anonymize -> STR -> FIU."""
    registry = initialize_bank_nodes()
    sbi = registry.get_bank_by_id("bank_sbi")
    hdfc = registry.get_bank_by_id("bank_hdfc")

    # 1. Register private account inside SBI's airgapped vault
    sbi_acc = sbi.vault.register_account(
        account_number="40991209384",
        ifsc_code="SBIN0001234",
        customer_name="Rajesh Kumar",
        kyc_status="verified",
        declared_income=45000.0,
        is_dormant=True
    )

    # 2. Register detected component in database
    comp = ComponentRepository.save({
        "detection_time": "2026-08-15T10:00:00Z",
        "risk_score": 0.93,
        "hashed_nodes": [sbi_acc["hash"], "HMAC:CounterpartyHDFC"],
        "bank_ids": ["bank_sbi", "bank_hdfc"],
        "feature_vector": {"pass_through_ratio": 0.98, "cross_bank_velocity": 4.5},
        "shap_explanation": {"summary": "High speed multi-bank cyclic laundering"}
    })

    # 3. Generate and dispatch alert
    dispatcher = AlertDispatcher(registry=registry)
    t0 = time.perf_counter()
    alert = dispatcher.generate_alert(
        component_id=comp["id"],
        risk_score=0.93,
        explanation={"summary": "High speed multi-bank cyclic laundering"}
    )
    dispatch_res = dispatcher.dispatch_alert(alert)
    dispatch_dur = time.perf_counter() - t0

    assert "bank_sbi" in dispatch_res["bank_acknowledged"]
    assert "bank_hdfc" in dispatch_res["bank_acknowledged"]
    assert dispatch_dur < 2.0  # Check 7.26 benchmark

    # 4. Bank SBI de-anonymizes flagged account in its local vault
    resolved = sbi.resolve_hash(sbi_acc["hash"])
    assert resolved is not None
    assert resolved["customer_name"] == "Rajesh Kumar"

    # 5. Bank SBI generates official STR report
    t1 = time.perf_counter()
    str_gen = STRGenerator()
    str_payload = sbi.generate_str(alert)
    str_dur = time.perf_counter() - t1

    assert str_payload["customer_name"] == "Rajesh Kumar"
    assert str_payload["account_number"] == "40991209384"
    assert str_dur < 0.50  # Check 7.27 benchmark

    # 6. Submit STR to FIU-IND
    sub_res = str_gen.submit_str(str_payload)
    assert sub_res["status"] == "accepted"
    assert sub_res["regulatory_agency"] == "FIU-IND"

    # 7. Resolve central alert
    resolve_res = dispatcher.update_alert_status(alert["alert_id"], AlertStatus.RESOLVED, notes="STR filed to FIU-IND")
    assert resolve_res["resolution_status"] == "resolved"


def test_multiple_bank_alert_flow():
    """Check 7.19 & 7.26: Alert involving 5 banks dispatched and acknowledged."""
    registry = initialize_bank_nodes()
    dispatcher = AlertDispatcher(registry=registry)

    involved = ["bank_sbi", "bank_hdfc", "bank_icici", "bank_axis", "bank_pnb"]
    alert = dispatcher.generate_alert(
        component_id="comp_multi_5_banks",
        risk_score=0.88,
        topology_snapshot={"nodes": [], "edges": [{"bank_id": b} for b in involved]}
    )

    t0 = time.perf_counter()
    res = dispatcher.dispatch_alert(alert)
    dur = time.perf_counter() - t0

    assert len(res["bank_acknowledged"]) == 5
    assert len(res["failed"]) == 0
    assert dur < 2.0


def test_alert_dispatch_performance():
    """Check 7.26: Dispatch to 10 banks completes in under 5 seconds."""
    registry = initialize_bank_nodes()
    dispatcher = AlertDispatcher(registry=registry)

    all_banks = [b.bank_id for b in registry.get_all_banks()]
    alert = dispatcher.generate_alert(
        component_id="comp_10_banks_perf",
        risk_score=0.75,
        topology_snapshot={"nodes": [], "edges": [{"bank_id": b} for b in all_banks]}
    )

    t0 = time.perf_counter()
    res = dispatcher.dispatch_alert(alert)
    dur = time.perf_counter() - t0

    assert len(res["bank_acknowledged"]) == 10
    assert dur < 5.0


def test_concurrent_alerts():
    """Check 7.18: Multiple alerts generated and dispatched in rapid succession."""
    registry = initialize_bank_nodes()
    dispatcher = AlertDispatcher(registry=registry)

    for i in range(10):
        alert = dispatcher.generate_alert(
            component_id=f"comp_concurrent_{i}",
            risk_score=0.70 + (i * 0.02),
            topology_snapshot={"nodes": [], "edges": [{"bank_id": "bank_sbi"}, {"bank_id": "bank_hdfc"}]}
        )
        res = dispatcher.dispatch_alert(alert)
        assert len(res["bank_acknowledged"]) == 2
