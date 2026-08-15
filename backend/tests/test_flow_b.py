"""Unit tests for Flow B investigation lifecycle."""
from backend.app.investigation.flow_b_service import FlowBInvestigationService


def test_flow_b_lifecycle():
    service = FlowBInvestigationService()
    salt = service.start_investigation("case-101", "hash-abc")
    assert isinstance(salt, str) and len(salt) > 0
    assert "case-101" in service.active_investigations
    
    closed = service.close_investigation("case-101")
    assert closed is True
    assert "case-101" not in service.active_investigations
