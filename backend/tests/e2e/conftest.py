"""Pytest configuration and shared fixtures for End-to-End (E2E) testing."""
import os
import tempfile
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.config import settings
from backend.app.database.connection import get_db
from backend.app.database.schema import create_tables
from backend.app.graph.graph_engine import TemporalGraph, GraphEngine
from backend.app.bank_node.bank_client import initialize_bank_nodes, BankNodeRegistry
from backend.app.privacy.hashing import generate_standing_hash
from backend.app.data_generator.motif_injector import MotifInjector



@pytest.fixture(scope="session")
def test_client():
    """FastAPI TestClient session fixture."""
    return TestClient(app)


@pytest.fixture
def temp_db():
    """Isolated temporary SQLite database per test."""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_e2e.db")
    with get_db(db_path) as conn:
        create_tables(conn)
    yield db_path
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass


@pytest.fixture
def test_banks():
    """Pre-seeded 10 bank node registry fixture."""
    return initialize_bank_nodes()


@pytest.fixture
def test_scenario_data(test_banks):
    """Factory generating targeted dataset configurations for all 4 E2E scenarios."""
    standing_key = settings.get_standing_key()
    now_dt = datetime.now(timezone.utc)

    # -----------------------------------------------------------------------
    # Scenario 1: Fast 4-Bank Rapid Chain (A -> B -> C -> D, ~98% pass-through, ₹5L)
    # -----------------------------------------------------------------------
    s1_banks = ["bank_sbi", "bank_hdfc", "bank_icici", "bank_axis"]
    s1_accounts = [
        {"account_number": f"SBIN{i:08d}", "ifsc_code": "SBIN0001000", "bank_id": "bank_sbi", "name": f"User S1_{i}"}
        for i in range(1, 6)
    ]
    for i, b in enumerate(s1_banks):
        s1_accounts[i]["bank_id"] = b

    s1_hashes = [
        generate_standing_hash(a["account_number"], a["ifsc_code"], standing_key)
        for a in s1_accounts
    ]

    s1_edges = []
    # 4-hop chain: 0 -> 1 -> 2 -> 3
    amt = 500000.0
    for hop in range(3):
        t_str = (now_dt + timedelta(minutes=15 * hop)).isoformat()
        s1_edges.append({
            "sender_hash": s1_hashes[hop],
            "receiver_hash": s1_hashes[hop + 1],
            "amount": amt * (0.98 ** hop),
            "timestamp": t_str,
            "bank_id": s1_banks[hop],
            "local_risk_score": 0.85
        })

    # -----------------------------------------------------------------------
    # Scenario 2: Collector Star (8 senders -> 1 collector, ₹50,000 each)
    # -----------------------------------------------------------------------
    s2_collector_acc = {"account_number": "PUNB99887766", "ifsc_code": "PUNB0001234", "bank_id": "bank_pnb", "name": "Collector Target"}
    s2_collector_hash = generate_standing_hash(s2_collector_acc["account_number"], s2_collector_acc["ifsc_code"], standing_key)
    
    s2_senders = [
        {"account_number": f"HDFC8800{i:04d}", "ifsc_code": "HDFC0001000", "bank_id": "bank_hdfc", "name": f"Sender {i}"}
        for i in range(8)
    ]
    s2_sender_hashes = [
        generate_standing_hash(a["account_number"], a["ifsc_code"], standing_key)
        for a in s2_senders
    ]

    s2_edges = []
    for i, s_hash in enumerate(s2_sender_hashes):
        t_str = (now_dt + timedelta(minutes=10 * i)).isoformat()
        s2_edges.append({
            "sender_hash": s_hash,
            "receiver_hash": s2_collector_hash,
            "amount": 50000.0,
            "timestamp": t_str,
            "bank_id": "bank_hdfc",
            "local_risk_score": 0.80
        })

    # -----------------------------------------------------------------------
    # Scenario 3: Distributor & Smurfing Ring (1 hub -> 10 receivers, ₹48k-₹49.9k)
    # -----------------------------------------------------------------------
    s3_hub_acc = {"account_number": "ICIC77665544", "ifsc_code": "ICIC0001234", "bank_id": "bank_icici", "name": "Smurfing Distributor"}
    s3_hub_hash = generate_standing_hash(s3_hub_acc["account_number"], s3_hub_acc["ifsc_code"], standing_key)

    s3_receivers = [
        {"account_number": f"YESB5500{i:04d}", "ifsc_code": "YESB0001000", "bank_id": "bank_yes", "name": f"Receiver {i}"}
        for i in range(10)
    ]
    s3_receiver_hashes = [
        generate_standing_hash(a["account_number"], a["ifsc_code"], standing_key)
        for a in s3_receivers
    ]

    s3_edges = []
    for i, r_hash in enumerate(s3_receiver_hashes):
        t_str = (now_dt + timedelta(minutes=12 * i)).isoformat()
        s3_edges.append({
            "sender_hash": s3_hub_hash,
            "receiver_hash": r_hash,
            "amount": 48500.0 + (i * 120),  # Under 50,000 threshold
            "timestamp": t_str,
            "bank_id": "bank_icici",
            "local_risk_score": 0.75
        })

    # -----------------------------------------------------------------------
    # Scenario 4: Legitimate Multi-Day Hold (Traversal Decay Test)
    # -----------------------------------------------------------------------
    s4_legit_acc = {"account_number": "BARB11223344", "ifsc_code": "BARB0001234", "bank_id": "bank_bob", "name": "Legitimate Merchant"}
    s4_legit_hash = generate_standing_hash(s4_legit_acc["account_number"], s4_legit_acc["ifsc_code"], standing_key)
    s4_payer_hash = generate_standing_hash("BARB99990001", "BARB0001234", standing_key)
    s4_supplier_hash = generate_standing_hash("BARB99990002", "BARB0001234", standing_key)

    s4_edges = [
        # Payment in
        {
            "sender_hash": s4_payer_hash,
            "receiver_hash": s4_legit_hash,
            "amount": 100000.0,
            "timestamp": (now_dt - timedelta(days=5)).isoformat(),
            "bank_id": "bank_bob",
            "local_risk_score": 0.05
        },
        # Supplier payout 4 days later (96 hours gap > 72h hold threshold, low pass-through 20%)
        {
            "sender_hash": s4_legit_hash,
            "receiver_hash": s4_supplier_hash,
            "amount": 20000.0,
            "timestamp": (now_dt - timedelta(days=1)).isoformat(),
            "bank_id": "bank_bob",
            "local_risk_score": 0.05
        }
    ]

    return {
        "scenario_1": {
            "name": "Fast 4-Bank Rapid Chain",
            "banks": s1_banks,
            "accounts": s1_accounts,
            "hashes": s1_hashes,
            "edges": s1_edges,
            "target_hash": s1_hashes[1]
        },
        "scenario_2": {
            "name": "Collector Star",
            "collector": s2_collector_acc,
            "collector_hash": s2_collector_hash,
            "senders": s2_senders,
            "sender_hashes": s2_sender_hashes,
            "edges": s2_edges,
            "target_hash": s2_collector_hash
        },
        "scenario_3": {
            "name": "Distributor & Smurfing Ring",
            "hub": s3_hub_acc,
            "hub_hash": s3_hub_hash,
            "receivers": s3_receivers,
            "receiver_hashes": s3_receiver_hashes,
            "edges": s3_edges,
            "target_hash": s3_hub_hash
        },
        "scenario_4": {
            "name": "Legitimate Account Traversal Decay",
            "legit_acc": s4_legit_acc,
            "legit_hash": s4_legit_hash,
            "edges": s4_edges,
            "target_hash": s4_legit_hash
        }
    }


# ---------------------------------------------------------------------------
# Test Assertion Helpers
# ---------------------------------------------------------------------------
def assert_alert_contains(alert: dict, expected_severity: str, min_risk: float = 0.70):
    """Helper to validate alert payload severity and threshold."""
    assert alert is not None, "Alert payload is None"
    assert "severity" in alert, "Alert missing severity key"
    assert alert["severity"] == expected_severity.lower(), f"Expected {expected_severity}, got {alert['severity']}"
    assert float(alert.get("risk_score", 0.0)) >= min_risk, f"Risk score below minimum {min_risk}"


def assert_component_risk(component: dict, min_risk: float = 0.70):
    """Helper to validate detected component risk score."""
    assert component is not None, "Component is None"
    score = float(component.get("risk_score", 0.0))
    assert score >= min_risk, f"Component risk score {score} is below expected {min_risk}"


def assert_traversal_stops(traversal_result: dict, expected_reasons=None):
    """Helper to validate Flow B bounded traversal stopping reason."""
    assert traversal_result is not None
    reason = traversal_result.get("stopping_reason")
    if expected_reasons:
        if isinstance(expected_reasons, str):
            expected_reasons = [expected_reasons]
        assert reason in expected_reasons, f"Stopping reason '{reason}' not in expected {expected_reasons}"
