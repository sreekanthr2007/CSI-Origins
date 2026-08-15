"""Unit tests for bank alerting, local vault, and STR generation."""
from backend.app.bank_node.bank_client import BankClient
from backend.app.alerts.dispatcher import AlertDispatcher
from backend.app.compliance.str_generator import STRGenerator


def test_bank_alert_and_vault():
    client = BankClient(bank_id="SBI", bank_name="State Bank of India")
    client.vault.register_account("1234567890", "SBIN0001234", {"name": "Test User", "kyc": "VERIFIED"})
    
    # Resolve in local vault
    profile = client.vault.resolve_identity("1234567890")
    assert profile is not None
    assert profile["name"] == "Test User"
    
    # Receive alert
    dispatcher = AlertDispatcher()
    alert = dispatcher.dispatch_alert("comp-1", ["SBI"], 0.92, {"hops": 4})
    receipt = client.receive_alert(alert)
    assert receipt["status"] == "ALERT_RECEIVED"


def test_str_generator():
    generator = STRGenerator()
    report = generator.generate_report("SBI", {"account": "1234567890"}, {"pass_through": 0.95})
    assert report["reporting_entity"] == "SBI"
    assert "regulatory_body" in report
