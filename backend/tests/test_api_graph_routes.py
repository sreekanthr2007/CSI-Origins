"""Integration tests for Graph Engine and Feature Extraction API endpoints."""
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.graph.graph_engine import GraphEngine

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_graph_state():
    """Reset graph and populate sample data before each API test."""
    ge = GraphEngine.get_instance()
    ge.get_graph().graph.clear()
    
    # Ingest a sample 3-node chain
    edges = [
        {
            "sender_hash": "HMAC:alpha",
            "receiver_hash": "HMAC:beta",
            "amount": 49000.0,
            "timestamp": "2026-08-15T10:00:00",
            "bank_id": "SBIN",
            "local_risk_score": 0.8,
            "is_interbank": True
        },
        {
            "sender_hash": "HMAC:beta",
            "receiver_hash": "HMAC:gamma",
            "amount": 47000.0,
            "timestamp": "2026-08-15T10:15:00",
            "bank_id": "HDFC",
            "local_risk_score": 0.85,
            "is_interbank": True
        }
    ]
    ge.ingest_batch(edges)


def test_get_graph_stats_api():
    """Test GET /api/v1/graph/stats."""
    resp = client.get("/api/v1/graph/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["node_count"] == 3
    assert data["edge_count"] == 2
    assert "SBIN" in data["edges_by_bank"]
    assert "HDFC" in data["edges_by_bank"]


def test_get_graph_edges_api():
    """Test GET /api/v1/graph/edges with pagination."""
    resp = client.get("/api/v1/graph/edges?limit=10&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["edges"]) == 2
    assert data["edges"][0]["sender_hash"] == "HMAC:alpha"


def test_get_graph_nodes_api():
    """Test GET /api/v1/graph/nodes with pagination."""
    resp = client.get("/api/v1/graph/nodes?limit=10&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert "HMAC:beta" in data["nodes"]


def test_get_node_features_api():
    """Test GET /api/v1/graph/features/{node_hash}."""
    resp = client.get("/api/v1/graph/features/HMAC:beta")
    assert resp.status_code == 200
    data = resp.json()
    assert data["node_hash"] == "HMAC:beta"
    assert data["pass_through_ratio"] > 0.90
    assert data["in_degree"] == 1.0
    assert data["out_degree"] == 1.0


def test_get_batch_features_api():
    """Test GET /api/v1/graph/features/batch."""
    resp = client.get("/api/v1/graph/features/batch?nodes=HMAC:alpha,HMAC:beta")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_nodes"] == 2
    assert len(data["features"]) == 2


def test_get_node_component_api():
    """Test GET /api/v1/graph/component/{node_hash}."""
    resp = client.get("/api/v1/graph/component/HMAC:beta")
    assert resp.status_code == 200
    data = resp.json()
    assert data["size"] == 3
    assert "HMAC:alpha" in data["nodes"]
    assert "HMAC:gamma" in data["nodes"]
    assert data["risk_score"] > 0.5


def test_get_components_api():
    """Test GET /api/v1/graph/components."""
    resp = client.get("/api/v1/graph/components?min_size=2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["components"][0]["size"] == 3


def test_api_input_validation():
    """Test error handling for malformed requests."""
    # 404 for unknown node features
    resp = client.get("/api/v1/graph/features/HMAC:nonexistent_node")
    assert resp.status_code == 404

    # 422/400 for empty nodes in batch
    resp = client.get("/api/v1/graph/features/batch?nodes=")
    assert resp.status_code == 400
