"""Unit tests for FIU-IND compliance, STR generation, validation, and action recommendations."""
import pytest
from backend.app.compliance.str_generator import STRGenerator, REQUIRED_FIELDS
from backend.app.compliance.action_recommender import ActionRecommender
from backend.app.alerts.dispatcher import AlertDispatcher


def test_str_schema():
    """Check 7.13 & 7.21: STR contains all mandatory FIU-IND schema fields."""
    gen = STRGenerator()
    alert_data = {
        "alert_id": "ALERT-COMP-001",
        "component_id": "comp_comp_001",
        "risk_score": 0.88,
        "severity": "high",
        "involved_banks": ["bank_sbi", "bank_hdfc"],
        "explanation": {"summary": "High speed circular routing", "top_drivers": ["pass_through_ratio"]}
    }
    account = {
        "account_number": "100200300400",
        "customer_name": "Anita Sharma",
        "bank_name": "State Bank of India",
        "kyc_status": "verified"
    }

    str_payload = gen.generate_str(alert_data, "bank_sbi", account)
    for field in REQUIRED_FIELDS:
        assert field in str_payload, f"Mandatory field {field} missing from STR"
        assert str_payload[field] is not None, f"Mandatory field {field} is None"


def test_str_sanitization():
    """Check 7.14 & 7.23: STR sanitization strips raw secrets or sensitive non-AML data."""
    gen = STRGenerator()
    payload = {
        "str_id": "STR-SAN-001",
        "schema_version": "1.0.0",
        "filing_bank": "State Bank of India",
        "bank_id": "bank_sbi",
        "filing_officer": "Compliance Officer",
        "account_number": "1234567890",
        "customer_name": "Test User",
        "suspicion_reason": "Rapid pass-through",
        "supporting_evidence": ["Evidence 1"],
        "amount_involved": 100000.0,
        "filing_date": "2026-08-15T10:00:00Z",
        "risk_score": 0.90,
        "severity": "critical",
        "involved_banks": ["bank_sbi"],
        "password": "unwanted_secret",
        "private_key": "raw_private_key"
    }

    sanitized = gen._sanitize_str_data(payload)
    assert "password" not in sanitized
    assert "private_key" not in sanitized


def test_str_validation():
    """Check 7.13: Incomplete STR payload raises schema validation error."""
    gen = STRGenerator()
    incomplete = {
        "str_id": "STR-INVAL-001",
        "filing_bank": "State Bank of India"
    }
    with pytest.raises(ValueError, match="Missing mandatory fields"):
        gen._validate_str_payload(incomplete)


def test_action_recommendations():
    """Check 7.15: Risk levels correctly dictate actionable priorities."""
    rec = ActionRecommender()
    
    # Priority rank tests
    assert rec.get_action_priority("Debit Freeze") == 1
    assert rec.get_action_priority("Enhanced Monitoring (30 days)") == 3
    assert rec.get_action_priority("Monitor for 7 days") == 5

    # Description non-empty
    assert len(rec.get_action_description("Debit Freeze")) > 10


def test_str_submission():
    """Check 7.6: Simulated regulatory submission returns accepted confirmation."""
    gen = STRGenerator()
    alert_data = {
        "alert_id": "ALERT-SUB-001",
        "risk_score": 0.91,
        "severity": "critical",
        "involved_banks": ["bank_sbi"]
    }
    account = {"account_number": "9988776655", "customer_name": "Vikas Verma"}
    
    payload = gen.generate_str(alert_data, "bank_sbi", account)
    sub = gen.submit_str(payload)
    
    assert sub["status"] == "accepted"
    assert sub["regulatory_agency"] == "FIU-IND"
    assert sub["submission_id"].startswith("SUB-")


def test_str_retrieval():
    """Check 7.5: Save and retrieve STR record by STR ID."""
    gen = STRGenerator()
    alert_data = {"alert_id": "ALERT-RET-001", "risk_score": 0.85, "severity": "high"}
    account = {"account_number": "1122334455", "customer_name": "Karan Mehra"}
    
    payload = gen.generate_str(alert_data, "bank_hdfc", account)
    str_id = payload["str_id"]
    gen.save_str(payload)

    retrieved = gen.get_str_by_id(str_id)
    assert retrieved is not None
    assert retrieved["str_id"] == str_id
    assert retrieved["customer_name"] == "Karan Mehra"


def test_alert_to_str_relationship():
    """Check 7.5: STR is retrievable by linked alert ID."""
    dispatcher = AlertDispatcher()
    alert = dispatcher.generate_alert("comp_link_001", 0.90)

    gen = STRGenerator()
    payload = gen.generate_str(alert, "bank_sbi", {"account_number": "5566778899", "customer_name": "Suresh Gupta"})
    gen.save_str(payload)

    str_by_alert = gen.get_str_by_alert(alert["alert_id"])
    assert str_by_alert is not None
    assert str_by_alert["alert_id"] == alert["alert_id"]
    assert str_by_alert["customer_name"] == "Suresh Gupta"
