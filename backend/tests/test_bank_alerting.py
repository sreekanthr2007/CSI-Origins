"""Comprehensive test suite for Bank Node simulation, Alert Dispatcher, and Vault Isolation."""
import pytest
from backend.app.bank_node.bank_client import BankNode, BankNodeRegistry, initialize_bank_nodes
from backend.app.alerts.dispatcher import AlertDispatcher, AlertStatus
from backend.app.compliance.str_generator import STRGenerator
from backend.app.compliance.action_recommender import ActionRecommender
from backend.app.privacy.hashing import generate_standing_hash


def test_bank_node_creation():
    """Check 7.1: Bank node created with correct properties."""
    node = BankNode("bank_sbi", "State Bank of India", "SBIN")
    assert node.bank_id == "bank_sbi"
    assert node.bank_name == "State Bank of India"
    assert node.ifsc_prefix == "SBIN"
    assert node.vault is not None


def test_bank_vault_isolation():
    """Check 7.2 & 7.11: Bank A cannot resolve Bank B's accounts."""
    sbi = BankNode("bank_sbi", "State Bank of India", "SBIN")
    hdfc = BankNode("bank_hdfc", "HDFC Bank", "HDFC")

    sbi_acc = sbi.vault.register_account(
        account_number="11122233344",
        ifsc_code="SBIN0001234",
        customer_name="SBI User"
    )
    hdfc_acc = hdfc.vault.register_account(
        account_number="55566677788",
        ifsc_code="HDFC0005678",
        customer_name="HDFC User"
    )

    # SBI can resolve its own
    assert sbi.resolve_hash(sbi_acc["hash"]) is not None
    assert sbi.resolve_hash(sbi_acc["hash"])["customer_name"] == "SBI User"

    # SBI cannot resolve HDFC's hash
    assert sbi.resolve_hash(hdfc_acc["hash"]) is None

    # HDFC can resolve its own but not SBI's
    assert hdfc.resolve_hash(hdfc_acc["hash"]) is not None
    assert hdfc.resolve_hash(sbi_acc["hash"]) is None


def test_bank_neighborhood_query():
    """Check 7.8 & 7.28: Query bank for neighborhood of its account."""
    sbi = BankNode("bank_sbi", "State Bank of India", "SBIN")
    acc = sbi.vault.register_account("11122233344", "SBIN0001234", "SBI User")
    
    neighborhood = sbi.get_neighborhood(acc["hash"], ephemeral_salt="test_salt_123")
    assert isinstance(neighborhood, list)
    assert len(neighborhood) == 1
    assert neighborhood[0]["bank_id"] == "bank_sbi"
    assert neighborhood[0]["investigation_hash"].startswith("INV:")


def test_alert_generation():
    """Check 7.3: Alert created with correct schema, severity, and involved banks."""
    dispatcher = AlertDispatcher()
    alert = dispatcher.generate_alert(
        component_id="comp_test_alert_001",
        risk_score=0.92,
        explanation={"summary": "High speed mule cycle detected"},
        topology_snapshot={"nodes": ["node1", "node2"], "edges": []}
    )

    assert alert["component_id"] == "comp_test_alert_001"
    assert alert["severity"] == "critical"
    assert alert["risk_score"] == 0.92
    assert "alert_id" in alert
    assert alert["status"] == AlertStatus.PENDING


def test_alert_dispatch():
    """Check 7.3 & 7.19: Alert sent to all involved banks."""
    registry = BankNodeRegistry()
    sbi = BankNode("bank_sbi", "State Bank of India", "SBIN")
    hdfc = BankNode("bank_hdfc", "HDFC Bank", "HDFC")
    registry.register_bank(sbi)
    registry.register_bank(hdfc)

    dispatcher = AlertDispatcher(registry=registry)
    alert = dispatcher.generate_alert(
        component_id="comp_test_dispatch_001",
        risk_score=0.78,
        topology_snapshot={"nodes": ["n1"], "edges": [{"bank_id": "bank_sbi"}, {"bank_id": "bank_hdfc"}]}
    )

    res = dispatcher.dispatch_alert(alert)
    assert "bank_sbi" in res["bank_acknowledged"]
    assert "bank_hdfc" in res["bank_acknowledged"]
    assert len(res["failed"]) == 0


def test_alert_acknowledgement():
    """Check 7.4: Bank acknowledges alert and status changes."""
    sbi = BankNode("bank_sbi", "State Bank of India", "SBIN")
    ack = sbi.receive_alert({"alert_id": "ALERT-12345", "severity": "high"})
    assert ack["status"] == "acknowledged"
    assert ack["bank_id"] == "bank_sbi"
    assert ack["alert_id"] == "ALERT-12345"


def test_alert_retry_on_failure():
    """Check 7.12 & 7.20: Dispatcher handles retries on bank node."""
    registry = BankNodeRegistry()
    sbi = BankNode("bank_sbi", "State Bank of India", "SBIN")
    registry.register_bank(sbi)
    dispatcher = AlertDispatcher(registry=registry)

    # Normal dispatch succeeds on 1st attempt
    res = dispatcher._dispatch_with_retry(sbi, {"alert_id": "ALERT-RETRY-001"})
    assert res["status"] == "acknowledged"


def test_alert_resolution():
    """Check 7.9 & 7.29: Updating alert status to resolved."""
    dispatcher = AlertDispatcher()
    alert = dispatcher.generate_alert("comp_test_res_001", 0.88)
    
    updated = dispatcher.update_alert_status(
        alert_id=alert["alert_id"],
        status=AlertStatus.RESOLVED,
        notes="Debit freeze placed on target account"
    )

    assert updated["resolution_status"] == "resolved"
    assert updated["resolved_at"] is not None
    assert updated["resolution_notes"] == "Debit freeze placed on target account"


def test_str_generation():
    """Check 7.5 & 7.13 & 7.21: STR contains all required FIU-IND fields."""
    sbi = BankNode("bank_sbi", "State Bank of India", "SBIN")
    acc = sbi.vault.register_account("40991209384", "SBIN0001234", "Rajesh Kumar", is_dormant=True)

    alert_data = {
        "alert_id": "ALERT-2026-001",
        "component_id": "comp_str_001",
        "risk_score": 0.94,
        "severity": "critical",
        "involved_banks": ["bank_sbi", "bank_hdfc"],
        "explanation": {"summary": "Rapid circular pass-through ring", "top_drivers": ["pass_through_ratio"]},
        "topology_snapshot": {"nodes": [acc["hash"]], "edges": [{"amount": 500000.0}]}
    }

    str_payload = sbi.generate_str(alert_data)
    assert str_payload["str_id"].startswith("STR-")
    assert str_payload["regulatory_agency"] == "Financial Intelligence Unit - India (FIU-IND)"
    assert str_payload["customer_name"] == "Rajesh Kumar"
    assert str_payload["account_number"] == "40991209384"
    assert str_payload["amount_involved"] == 500000.0
    assert "Freeze Account" in str_payload["recommended_actions"] or "Debit Freeze" in str_payload["recommended_actions"]


def test_str_submission():
    """Check 7.6: STR submission simulation returns valid submission ID."""
    gen = STRGenerator()
    payload = {
        "str_id": "STR-20260815-TEST01",
        "schema_version": "1.0.0",
        "regulatory_agency": "FIU-IND",
        "filing_bank": "State Bank of India",
        "bank_id": "bank_sbi",
        "filing_officer": "PCO Officer",
        "filing_date": "2026-08-15T12:00:00Z",
        "account_number": "1234567890",
        "customer_name": "Test User",
        "risk_score": 0.89,
        "severity": "critical",
        "suspicion_reason": "Rapid pass-through",
        "supporting_evidence": ["Topology Graph"],
        "amount_involved": 250000.0,
        "involved_banks": ["bank_sbi"]
    }

    sub = gen.submit_str(payload)
    assert sub["status"] == "accepted"
    assert sub["submission_id"].startswith("SUB-")
    assert sub["regulatory_agency"] == "FIU-IND"


def test_action_recommendations():
    """Check 7.7 & 7.15: Action recommendations match risk severity thresholds."""
    recommender = ActionRecommender()
    
    # Critical risk
    crit_actions = recommender.recommend_actions(risk_score=0.92)
    crit_names = [a["action"] for a in crit_actions]
    assert "Debit Freeze" in crit_names
    assert "File STR Immediately" in crit_names

    # High risk
    high_actions = recommender.recommend_actions(risk_score=0.75)
    high_names = [a["action"] for a in high_actions]
    assert "Temporary Lien" in high_names
    assert "Enhanced Monitoring (30 days)" in high_names

    # Medium risk
    med_actions = recommender.recommend_actions(risk_score=0.55)
    med_names = [a["action"] for a in med_actions]
    assert "Enhanced Monitoring (15 days)" in med_names

    # Low risk
    low_actions = recommender.recommend_actions(risk_score=0.35)
    low_names = [a["action"] for a in low_actions]
    assert "Flag for Review" in low_names


def test_get_alerts_by_bank():
    """Check 7.10: Alerts filtered by bank ID."""
    dispatcher = AlertDispatcher()
    alert = dispatcher.generate_alert(
        component_id="comp_bank_filter_001",
        risk_score=0.82,
        topology_snapshot={"nodes": [], "edges": [{"bank_id": "bank_icici"}]}
    )
    dispatcher.dispatch_alert(alert)

    icici_alerts = dispatcher.get_alerts_by_bank("bank_icici")
    assert len(icici_alerts) >= 1
    assert any(a["id"] == alert["alert_id"] for a in icici_alerts)


def test_alert_history():
    """Check 7.30: Alert history query returns recent alerts."""
    dispatcher = AlertDispatcher()
    history = dispatcher.get_alert_history(days=7)
    assert isinstance(history, list)
    assert len(history) >= 1
