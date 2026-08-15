"""Comprehensive test suite for TemporalGraph and GraphEngine."""
import time
import json
import pytest
import datetime
import networkx as nx

from backend.app.config import settings
from backend.app.graph.graph_engine import TemporalGraph, GraphEngine
from backend.app.database.connection import init_db
from backend.app.database.repositories import EdgeRepository, BankRepository


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    """Setup isolated test database for repositories."""
    db_file = tmp_path / "test_graph.db"
    init_db(str(db_file))
    return str(db_file)


def test_graph_add_edge():
    """Verify single edge insertion with full metadata."""
    tg = TemporalGraph()
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    key = tg.add_edge(
        sender_hash="HMAC:node1",
        receiver_hash="HMAC:node2",
        amount=15000.0,
        timestamp=now_iso,
        bank_id="SBIN",
        local_risk_score=0.25,
        is_interbank=True
    )

    assert tg.get_node_count() == 2
    assert tg.get_edge_count() == 1
    assert "HMAC:node1" in tg.get_nodes()
    assert "HMAC:node2" in tg.get_nodes()

    edge_data = tg.graph["HMAC:node1"]["HMAC:node2"][key]
    assert edge_data["amount"] == 15000.0
    assert edge_data["bank_id"] == "SBIN"
    assert edge_data["local_risk_score"] == 0.25
    assert edge_data["is_interbank"] is True


def test_graph_build_from_db(setup_test_db):
    """Verify building graph from EdgeRepository database records."""
    db_path = setup_test_db
    bank = BankRepository.create("SBI", "SBIN", db_path=db_path)
    bank_id = bank["id"]

    edges = [
        {
            "sender_hash": f"HMAC:user_{i}",
            "receiver_hash": f"HMAC:user_{i+1}",
            "amount": 1000.0 * (i + 1),
            "timestamp": f"2026-08-15T10:{i:02d}:00",
            "bank_id": bank_id,
            "local_risk_score": 0.1,
            "is_interbank": True
        }
        for i in range(5)
    ]
    EdgeRepository.batch_insert(edges, db_path=db_path)

    tg = TemporalGraph()
    count = tg.build_from_db(db_path=db_path)
    assert count == 5
    assert tg.get_node_count() == 6
    assert tg.get_edge_count() == 5



def test_graph_statistics():
    """Verify graph summary statistics match expected calculations."""
    tg = TemporalGraph()
    # Create triangle HMAC:A -> HMAC:B -> HMAC:C -> HMAC:A
    tg.add_edge("HMAC:A", "HMAC:B", 1000, "2026-08-15T01:00:00", "SBIN")
    tg.add_edge("HMAC:B", "HMAC:C", 1000, "2026-08-15T02:00:00", "HDFC")
    tg.add_edge("HMAC:C", "HMAC:A", 1000, "2026-08-15T03:00:00", "ICIC")

    stats = tg.get_graph_stats()
    assert stats["node_count"] == 3
    assert stats["edge_count"] == 3
    assert stats["avg_degree"] == 2.0
    assert stats["is_connected"] is True
    assert stats["component_count"] == 1
    assert stats["edges_by_bank"]["SBIN"] == 1
    assert stats["edges_by_bank"]["HDFC"] == 1
    assert stats["edges_by_bank"]["ICIC"] == 1


def test_get_edges_for_node():
    """Verify node edge retrieval handles in, out, and bidirectional edges."""
    tg = TemporalGraph()
    tg.add_edge("HMAC:X", "HMAC:Y", 500, "2026-08-15T01:00:00", "SBIN")
    tg.add_edge("HMAC:Y", "HMAC:Z", 600, "2026-08-15T02:00:00", "HDFC")

    # In edges for Y
    in_y = tg.get_in_edges("HMAC:Y")
    assert len(in_y) == 1
    assert in_y[0]["sender_hash"] == "HMAC:X"
    assert in_y[0]["amount"] == 500

    # Out edges for Y
    out_y = tg.get_out_edges("HMAC:Y")
    assert len(out_y) == 1
    assert out_y[0]["receiver_hash"] == "HMAC:Z"
    assert out_y[0]["amount"] == 600

    # All edges for Y
    all_y = tg.get_edges_for_node("HMAC:Y")
    assert len(all_y) == 2


def test_get_connected_component():
    """Verify connected component subgraph extraction."""
    tg = TemporalGraph()
    # Component 1: A -> B -> C
    tg.add_edge("HMAC:A", "HMAC:B", 100, "2026-08-15T01:00:00", "SBIN")
    tg.add_edge("HMAC:B", "HMAC:C", 100, "2026-08-15T02:00:00", "SBIN")

    # Component 2: X -> Y
    tg.add_edge("HMAC:X", "HMAC:Y", 200, "2026-08-15T03:00:00", "HDFC")

    sub_a = tg.get_connected_component("HMAC:A")
    assert sub_a.get_node_count() == 3
    assert set(sub_a.get_nodes()) == {"HMAC:A", "HMAC:B", "HMAC:C"}

    sub_x = tg.get_connected_component("HMAC:X")
    assert sub_x.get_node_count() == 2
    assert set(sub_x.get_nodes()) == {"HMAC:X", "HMAC:Y"}


def test_get_neighbors():
    """Verify neighborhood discovery with directional filtering."""
    tg = TemporalGraph()
    tg.add_edge("HMAC:P1", "HMAC:Center", 100, "2026-08-15T01:00:00", "SBIN")
    tg.add_edge("HMAC:P2", "HMAC:Center", 100, "2026-08-15T01:00:00", "SBIN")
    tg.add_edge("HMAC:Center", "HMAC:S1", 100, "2026-08-15T02:00:00", "SBIN")

    in_neigh = tg.get_neighbors("HMAC:Center", direction="in")
    assert set(in_neigh) == {"HMAC:P1", "HMAC:P2"}

    out_neigh = tg.get_neighbors("HMAC:Center", direction="out")
    assert set(out_neigh) == {"HMAC:S1"}

    both_neigh = tg.get_neighbors("HMAC:Center", direction="both")
    assert set(both_neigh) == {"HMAC:P1", "HMAC:P2", "HMAC:S1"}


def test_get_shortest_path():
    """Verify shortest path finding between nodes."""
    tg = TemporalGraph()
    tg.add_edge("HMAC:1", "HMAC:2", 10, "2026-08-15T01:00:00", "SBIN")
    tg.add_edge("HMAC:2", "HMAC:3", 10, "2026-08-15T02:00:00", "SBIN")
    tg.add_edge("HMAC:3", "HMAC:4", 10, "2026-08-15T03:00:00", "SBIN")

    path = tg.get_shortest_path("HMAC:1", "HMAC:4")
    assert path == ["HMAC:1", "HMAC:2", "HMAC:3", "HMAC:4"]

    no_path = tg.get_shortest_path("HMAC:4", "HMAC:1")
    assert no_path is None


def test_temporal_window():
    """Verify temporal window filtering preserves valid edges only."""
    tg = TemporalGraph()
    tg.add_edge("HMAC:1", "HMAC:2", 100, "2026-08-15T08:00:00", "SBIN")
    tg.add_edge("HMAC:2", "HMAC:3", 200, "2026-08-15T12:00:00", "SBIN")
    tg.add_edge("HMAC:3", "HMAC:4", 300, "2026-08-15T18:00:00", "SBIN")

    window = tg.get_temporal_window("2026-08-15T10:00:00", "2026-08-15T14:00:00")
    assert window.get_edge_count() == 1
    assert window.get_node_count() == 2
    assert set(window.get_nodes()) == {"HMAC:2", "HMAC:3"}


def test_graph_serialization():
    """Verify graph JSON round-trip serialization and deserialization."""
    tg = TemporalGraph()
    tg.add_edge(
        sender_hash="HMAC:Alice",
        receiver_hash="HMAC:Bob",
        amount=45000.0,
        timestamp="2026-08-15T14:30:00",
        bank_id="HDFC",
        local_risk_score=0.65,
        is_interbank=True
    )

    json_str = tg.to_json()
    assert isinstance(json_str, str)
    assert "HMAC:Alice" in json_str

    reconstructed = TemporalGraph.from_json(json_str)
    assert reconstructed.get_node_count() == 2
    assert reconstructed.get_edge_count() == 1

    edge_data = list(reconstructed.graph.edges(data=True))[0][2]
    assert edge_data["amount"] == 45000.0
    assert edge_data["bank_id"] == "HDFC"
    assert edge_data["local_risk_score"] == 0.65


def test_graph_performance_10k_edges():
    """Benchmark: 10,000 edges batch ingestion builds in < 5.0 seconds."""
    edges = [
        {
            "sender_hash": f"HMAC:sender_{i % 500}",
            "receiver_hash": f"HMAC:receiver_{(i + 1) % 500}",
            "amount": float(100 + (i % 10000)),
            "timestamp": "2026-08-15T12:00:00",
            "bank_id": f"BANK_{i % 5}",
            "local_risk_score": 0.1,
            "is_interbank": True
        }
        for i in range(10000)
    ]

    tg = TemporalGraph()
    start_time = time.time()
    count = tg.add_edges_batch(edges)
    duration = time.time() - start_time

    assert count == 10000
    assert tg.get_edge_count() == 10000
    assert duration < 5.0, f"Ingestion took {duration:.2f}s, exceeding 5.0s threshold"
