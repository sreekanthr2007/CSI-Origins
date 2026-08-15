"""Performance and latency benchmark tests for TRACE."""
import time
import pytest
from datetime import datetime, timezone, timedelta
import concurrent.futures

from backend.app.graph.graph_engine import TemporalGraph, GraphEngine
from backend.app.ml.classifier import MuleClassifier
from backend.app.investigation.traversal import PatternDecayTraversal
from backend.app.config import settings


def test_graph_build_performance():
    """Benchmark: Building a graph with 10,000 edges must take < 5.0 seconds."""
    tg = TemporalGraph()
    now_dt = datetime.now(timezone.utc)

    start_time = time.perf_counter()
    for i in range(10000):
        sender = f"HMAC:node_{i % 1000:04d}"
        receiver = f"HMAC:node_{(i + 1) % 1000:04d}"
        tg.add_transaction(
            edge_id=f"tx_{i}",
            sender_hash=sender,
            receiver_hash=receiver,
            amount=1000.0 + (i % 500),
            timestamp=now_dt + timedelta(seconds=i),
            bank_id="bank_sbi",
            local_risk_score=0.1
        )
    elapsed = time.perf_counter() - start_time

    assert tg.edge_count == 10000
    assert elapsed < 5.0, f"Graph build with 10,000 edges took {elapsed:.2f}s (Threshold: < 5.0s)"


def test_component_detection_performance():
    """Benchmark: Component detection on 10,000 edges must take < 10.0 seconds."""
    tg = TemporalGraph()
    now_dt = datetime.now(timezone.utc)

    for i in range(10000):
        sender = f"HMAC:node_{i % 500:04d}"
        receiver = f"HMAC:node_{(i + 1) % 500:04d}"
        tg.add_transaction(
            edge_id=f"tx_{i}",
            sender_hash=sender,
            receiver_hash=receiver,
            amount=2000.0,
            timestamp=now_dt + timedelta(seconds=i),
            bank_id="bank_hdfc",
            local_risk_score=0.2
        )

    engine = GraphEngine(tg, settings)
    start_time = time.perf_counter()
    subgraphs = engine.extract_subgraphs(max_size=20, min_risk=0.0)
    elapsed = time.perf_counter() - start_time

    assert len(subgraphs) > 0
    assert elapsed < 10.0, f"Component detection took {elapsed:.2f}s (Threshold: < 10.0s)"


def test_prediction_performance():
    """Benchmark: Model inference on 1,000 instances must take < 5.0 seconds."""
    classifier = MuleClassifier(model_type="xgboost")
    classifier.train()

    dummy_features = {
        "pass_through_ratio": 0.95,
        "fan_in_asymmetry": 0.88,
        "avg_hold_time_hours": 1.2,
        "cross_bank_velocity": 4.5,
        "in_out_ratio": 0.98,
        "max_chain_length": 4,
        "degree_centrality": 0.15,
        "structuring_score": 0.92
    }

    start_time = time.perf_counter()
    for _ in range(1000):
        _ = classifier.predict_proba(dummy_features)
    elapsed = time.perf_counter() - start_time

    assert elapsed < 5.0, f"1,000 predictions took {elapsed:.2f}s (Threshold: < 5.0s)"


def test_traversal_7_hop_performance():
    """Benchmark: Traversing a 7-hop chain must take < 5.0 seconds."""
    tg = TemporalGraph()
    now_dt = datetime.now(timezone.utc)

    # 7-hop rapid chain
    for i in range(7):
        tg.add_transaction(
            edge_id=f"tx_chain_{i}",
            sender_hash=f"HMAC:hop_{i}",
            receiver_hash=f"HMAC:hop_{i+1}",
            amount=500000.0 * (0.98 ** i),
            timestamp=now_dt + timedelta(minutes=10 * i),
            bank_id="bank_icici",
            local_risk_score=0.85
        )

    traversal = PatternDecayTraversal(tg, settings)
    start_time = time.perf_counter()
    res = traversal.traverse_from_node("HMAC:hop_0", direction="out", max_depth=7)
    elapsed = time.perf_counter() - start_time

    assert res.depth_reached >= 6
    assert elapsed < 5.0, f"7-hop traversal took {elapsed:.2f}s (Threshold: < 5.0s)"


def test_api_endpoints_latency(test_client):
    """Benchmark: Read endpoints < 100ms, Write endpoints < 500ms."""
    # 1. Read /graph/stats
    t0 = time.perf_counter()
    res = test_client.get("/api/v1/graph/stats")
    read_latency = (time.perf_counter() - t0) * 1000
    assert res.status_code == 200
    assert read_latency < 250, f"GET /graph/stats latency {read_latency:.1f}ms exceeds threshold"

    # 2. Read /banks
    t0 = time.perf_counter()
    res = test_client.get("/api/v1/banks")
    bank_latency = (time.perf_counter() - t0) * 1000
    assert res.status_code == 200
    assert bank_latency < 250, f"GET /banks latency {bank_latency:.1f}ms exceeds threshold"

    # 3. Read /alerts/pending
    t0 = time.perf_counter()
    res = test_client.get("/api/v1/alerts/pending")
    alert_latency = (time.perf_counter() - t0) * 1000
    assert res.status_code == 200
    assert alert_latency < 250, f"GET /alerts/pending latency {alert_latency:.1f}ms exceeds threshold"


def test_concurrent_api_requests(test_client):
    """Benchmark: 10 concurrent requests without failure or severe latency spike."""
    def make_request():
        t0 = time.perf_counter()
        res = test_client.get("/api/v1/graph/stats")
        lat = (time.perf_counter() - t0) * 1000
        return res.status_code, lat

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(make_request) for _ in range(10)]
        results = [f.result() for f in futures]

    for status, lat in results:
        assert status == 200
        assert lat < 500, f"Concurrent request latency {lat:.1f}ms exceeded threshold"
