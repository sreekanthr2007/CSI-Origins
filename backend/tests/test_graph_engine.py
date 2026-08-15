"""Unit tests for central graph engine."""
from backend.app.graph.graph_engine import GraphEngine


def test_graph_engine_add_edge():
    engine = GraphEngine()
    engine.add_edge_record("nodeA", "nodeB", {"amount": 50000, "timestamp": 1700000000})
    summary = engine.get_summary()
    assert summary["nodes_count"] == 2
    assert summary["edges_count"] == 1
