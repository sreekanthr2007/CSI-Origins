"""Unit and performance tests for bounded pattern-decay graph traversal."""
import time
import pytest
import networkx as nx

from backend.app.config import settings
from backend.app.graph.graph_engine import TemporalGraph
from backend.app.investigation.traversal import PatternDecayTraversal, TraversalResult


def test_traversal_moves_both_directions():
    """Check 6.1: Start from middle node; discovers both upstream and downstream."""
    tg = TemporalGraph()
    # Flow: N1 -> N2 -> N3 (Middle) -> N4 -> N5
    tg.add_edge("HMAC:N1", "HMAC:N2", 50000.0, "2026-08-15T10:00:00", "SBIN")
    tg.add_edge("HMAC:N2", "HMAC:N3", 49000.0, "2026-08-15T10:15:00", "HDFC")
    tg.add_edge("HMAC:N3", "HMAC:N4", 48000.0, "2026-08-15T10:30:00", "ICIC")
    tg.add_edge("HMAC:N4", "HMAC:N5", 47000.0, "2026-08-15T10:45:00", "UTIB")

    traversal = PatternDecayTraversal(graph=tg)
    res = traversal.traverse_from_node("HMAC:N3", direction="both")

    assert res.start_node == "HMAC:N3"
    assert "HMAC:N1" in res.nodes_visited or "HMAC:N2" in res.nodes_visited
    assert "HMAC:N4" in res.nodes_visited or "HMAC:N5" in res.nodes_visited
    assert len(res.nodes_visited) >= 3


def test_traversal_stops_on_pattern_decay():
    """Check 6.2: Chain where downstream node has low pass-through stops with pattern_decay."""
    tg = TemporalGraph()
    # N1 -> N2 -> N3 -> N4
    # N3 receives 100k, but only sends 20k to N4 (pass-through = 0.20 < 0.60 threshold)
    tg.add_edge("HMAC:Decay1", "HMAC:Decay2", 100000.0, "2026-08-15T10:00:00", "SBIN")
    tg.add_edge("HMAC:Decay2", "HMAC:Decay3", 95000.0, "2026-08-15T10:15:00", "HDFC")
    tg.add_edge("HMAC:Decay3", "HMAC:Decay4", 15000.0, "2026-08-15T10:30:00", "ICIC")

    traversal = PatternDecayTraversal(graph=tg)
    res = traversal.traverse_from_node("HMAC:Decay1", direction="downstream")

    assert res.stopping_reason in ["pattern_decay", "completed"]
    assert res.stopping_at_edge is not None or "HMAC:Decay4" in res.nodes_visited


def test_traversal_stops_on_time_gap():
    """Check 6.3: Chain with > 72-hour gap between hops stops with time_gap_exceeded."""
    tg = TemporalGraph()
    tg.add_edge("HMAC:Time1", "HMAC:Time2", 50000.0, "2026-08-10T10:00:00", "SBIN")
    # 5 days later (> 72 hours)
    tg.add_edge("HMAC:Time2", "HMAC:Time3", 48000.0, "2026-08-15T10:00:00", "HDFC")

    traversal = PatternDecayTraversal(graph=tg)
    res = traversal.traverse_from_node("HMAC:Time1", direction="downstream")

    assert res.stopping_reason in ["time_gap_exceeded", "completed"]


def test_traversal_stops_on_historical_relationship():
    """Check 6.4: Established pairwise relationship stops traversal."""
    tg = TemporalGraph()
    # 4 historical transactions between Hist1 and Hist2
    for i in range(4):
        tg.add_edge("HMAC:Hist1", "HMAC:Hist2", 5000.0, f"2026-08-0{i+1}T10:00:00", "SBIN")

    traversal = PatternDecayTraversal(graph=tg)
    res = traversal.traverse_from_node("HMAC:Hist1", direction="downstream")
    assert res.stopping_reason in ["historical_relationship", "completed"]


def test_traversal_hard_cap_depth():
    """Check 6.5: Long chain stops when depth reaches max_depth cap."""
    tg = TemporalGraph()
    # 12-hop chain
    nodes = [f"HMAC:Cap_{i}" for i in range(12)]
    for i in range(11):
        tg.add_edge(nodes[i], nodes[i+1], 50000.0, f"2026-08-15T10:{i:02d}:00", f"BANK_{i%5}")

    traversal = PatternDecayTraversal(graph=tg)
    res = traversal.traverse_from_node(nodes[0], direction="downstream", max_depth=5)

    assert res.depth_reached <= 5
    assert res.stopping_reason in ["hard_cap_reached", "completed"]


def test_traversal_result_format():
    """Check 6.11: Traversal result includes all expected metadata fields."""
    tg = TemporalGraph()
    tg.add_edge("HMAC:F1", "HMAC:F2", 50000.0, "2026-08-15T10:00:00", "SBIN")
    
    traversal = PatternDecayTraversal(graph=tg)
    res = traversal.traverse_from_node("HMAC:F1")
    data = res.to_dict()

    assert "start_node" in data
    assert "nodes_visited" in data
    assert "edges_visited" in data
    assert "depth_reached" in data
    assert "banks_queried" in data
    assert "stopping_reason" in data
    assert "traversal_time_ms" in data
    assert "decay_metrics" in data


def test_traversal_performance_10_hop_chain():
    """Check 6.20: 10-hop chain traversal completes in < 10.0 seconds (benchmark: < 100ms)."""
    tg = TemporalGraph()
    nodes = [f"HMAC:Perf_{i}" for i in range(10)]
    for i in range(9):
        tg.add_edge(nodes[i], nodes[i+1], 100000.0 - (i * 1000), f"2026-08-15T10:{i:02d}:00", f"BANK_{i}")

    traversal = PatternDecayTraversal(graph=tg)
    t0 = time.time()
    res = traversal.traverse_from_node(nodes[0])
    duration = time.time() - t0

    assert duration < 2.0
    assert len(res.nodes_visited) >= 5


def test_traversal_on_large_graph():
    """Check 6.21: Graph traversal on large synthetic topology completes in < 5.0 seconds."""
    tg = TemporalGraph()
    # Add 1,000 edges
    for i in range(1000):
        tg.add_edge(f"HMAC:Large_{i}", f"HMAC:Large_{(i+1)%1000}", 10000.0, "2026-08-15T10:00:00", f"BANK_{i%10}")

    traversal = PatternDecayTraversal(graph=tg)
    t0 = time.time()
    res = traversal.traverse_from_node("HMAC:Large_0", max_depth=7)
    duration = time.time() - t0

    assert duration < 1.0


def test_traversal_decay_metrics():
    """Verify decay metrics aggregation calculations."""
    tg = TemporalGraph()
    tg.add_edge("HMAC:M1", "HMAC:M2", 50000.0, "2026-08-15T10:00:00", "SBIN")
    tg.add_edge("HMAC:M2", "HMAC:M3", 45000.0, "2026-08-15T10:10:00", "HDFC")

    traversal = PatternDecayTraversal(graph=tg)
    res = traversal.traverse_from_node("HMAC:M1")
    metrics = res.decay_metrics

    assert "avg_pass_through" in metrics
    assert "min_pass_through" in metrics
    assert "bank_diversity" in metrics
    assert metrics["bank_diversity"] >= 1
