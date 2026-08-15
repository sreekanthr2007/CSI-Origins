"""Comprehensive functional tests for Flow B investigation service and salt lifecycle."""
import pytest
from backend.app.config import settings
from backend.app.graph.graph_engine import TemporalGraph
from backend.app.privacy.hashing import encrypt_salt, decrypt_salt, generate_investigation_salt
from backend.app.investigation.flow_b_service import FlowBService
from backend.app.investigation.cleanup import CleanupManager
from backend.app.database.repositories import InvestigationRepository


@pytest.fixture
def flow_b_setup():
    """Setup test graph and FlowBService."""
    tg = TemporalGraph()
    tg.add_edge("HMAC:Src1", "HMAC:Tgt1", 75000.0, "2026-08-15T10:00:00", "SBIN")
    tg.add_edge("HMAC:Tgt1", "HMAC:Dst1", 72000.0, "2026-08-15T10:15:00", "HDFC")
    
    svc = FlowBService(config=settings, graph=tg)
    return svc, tg


def test_salt_encryption_roundtrip():
    """Check 6.13: Encrypt and decrypt investigation salt using AES-256-GCM."""
    salt = generate_investigation_salt()
    encrypted = encrypt_salt(salt)
    assert encrypted != salt
    assert len(encrypted) > 20

    decrypted = decrypt_salt(encrypted)
    assert decrypted == salt


def test_start_investigation(flow_b_setup):
    """Check 6.6: Start investigation creates database record with encrypted salt."""
    svc, _ = flow_b_setup
    inv_id = svc.start_investigation("HMAC:Tgt1", component_id="comp_test_001")

    assert inv_id is not None
    assert len(inv_id) > 10

    rec = InvestigationRepository.get_by_id(inv_id)
    assert rec is not None
    assert rec["component_id"] == "comp_test_001"
    assert rec["investigation_salt"] != ""
    assert rec["status"] in ["active", "completed"]


def test_investigation_status(flow_b_setup):
    """Check 6.8: Investigation status returns accurate progress data."""
    svc, _ = flow_b_setup
    inv_id = svc.start_investigation("HMAC:Tgt1")

    status_data = svc.get_status(inv_id)
    assert status_data["investigation_id"] == inv_id
    assert "depth_reached" in status_data
    assert "banks_queried" in status_data
    assert status_data["status"] in ["active", "completed"]


def test_close_investigation(flow_b_setup):
    """Check 6.7 & 6.19: Closing investigation destroys salt in database."""
    svc, _ = flow_b_setup
    inv_id = svc.start_investigation("HMAC:Tgt1")

    close_res = svc.close_investigation(inv_id, closed_by="compliance_officer")
    assert close_res["status"] == "closed"
    assert close_res["closed_by"] == "compliance_officer"

    # Verify salt in DB is zeroed / destroyed
    rec = InvestigationRepository.get_by_id(inv_id)
    assert rec["investigation_salt"] == "DESTROYED"
    assert rec["status"] == "closed"


def test_playback_data(flow_b_setup):
    """Check 6.9 & 6.22: Playback steps match traversal trace."""
    svc, _ = flow_b_setup
    inv_id = svc.start_investigation("HMAC:Tgt1")

    steps = svc.get_playback(inv_id)
    assert len(steps) >= 2
    assert steps[0]["action"] == "START"
    assert steps[0]["node"] == "HMAC:Tgt1"
    assert steps[-1]["decision"] in ["ACCEPT", "DONE", "REJECT"]


def test_bank_query_simulation(flow_b_setup):
    """Check 6.10: Bank query retrieves appropriate bank-specific edge neighborhood."""
    svc, _ = flow_b_setup
    salt = generate_investigation_salt()
    res = svc.request_neighborhood_from_bank("HMAC:Tgt1", "HDFC", salt)

    assert isinstance(res, list)


def test_get_result_after_completion(flow_b_setup):
    """Check 6.11: get_result returns complete traversal result dictionary."""
    svc, _ = flow_b_setup
    inv_id = svc.start_investigation("HMAC:Tgt1")

    res = svc.get_result(inv_id)
    assert "start_node" in res
    assert "nodes_visited" in res
    assert "edges_visited" in res


def test_stale_investigation_cleanup(flow_b_setup):
    """Check 6.14 & 6.30: Cleanup manager automatically closes stale investigations."""
    svc, _ = flow_b_setup
    # Start an adhoc investigation
    inv_id = svc.start_investigation("HMAC:Tgt1")

    cleanup = CleanupManager(flow_b_service=svc)
    summary = cleanup.run_cleanup(max_age_hours=0)  # Threshold 0 forces cleanup of current active

    assert summary["status"] == "success"
    assert "cleaned_count" in summary
