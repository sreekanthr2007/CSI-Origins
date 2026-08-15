"""Comprehensive unit and performance tests for FeatureExtractor and ComponentDetector."""
import time
import pytest
import datetime
import pandas as pd
import numpy as np

from backend.app.graph.graph_engine import TemporalGraph
from backend.app.features.feature_extractor import FeatureExtractor
from backend.app.features.component_detector import ComponentDetector


def test_pass_through_ratio():
    """Check 4.2: Pass-through ratio calculation where node receives 100 and sends 90."""
    tg = TemporalGraph()
    # Node M receives 100, then sends 90 within 2 hours
    tg.add_edge("HMAC:S1", "HMAC:M", 100.0, "2026-08-15T10:00:00", "SBIN")
    tg.add_edge("HMAC:M", "HMAC:R1", 90.0, "2026-08-15T12:00:00", "HDFC")

    extractor = FeatureExtractor(graph=tg)
    pt = extractor._calculate_pass_through("HMAC:M", window_hours=24)
    assert pytest.approx(pt, 0.01) == 0.90


def test_temporal_velocity():
    """Check 4.3: Temporal velocity calculation with edges at T+0, T+5, T+10 minutes."""
    tg = TemporalGraph()
    # Inbound at 10:00, outbound at 10:05 -> delta 5 min
    tg.add_edge("HMAC:Src1", "HMAC:Mid", 5000.0, "2026-08-15T10:00:00", "SBIN")
    tg.add_edge("HMAC:Mid", "HMAC:Dst1", 4500.0, "2026-08-15T10:05:00", "ICIC")
    # Inbound at 10:05, outbound at 10:10 -> delta 5 min
    tg.add_edge("HMAC:Src2", "HMAC:Mid", 3000.0, "2026-08-15T10:05:00", "SBIN")
    tg.add_edge("HMAC:Mid", "HMAC:Dst2", 2800.0, "2026-08-15T10:10:00", "ICIC")

    extractor = FeatureExtractor(graph=tg)
    vel = extractor._calculate_temporal_velocity("HMAC:Mid")
    assert pytest.approx(vel["avg_time_between_incoming_and_outgoing"], 0.1) == 5.0
    assert vel["velocity_count"] == 2.0


def test_fan_metrics():
    """Check 4.4: Fan-in/fan-out asymmetry for node with 10 senders and 2 receivers."""
    tg = TemporalGraph()
    # 10 senders into Collector
    for i in range(10):
        tg.add_edge(f"HMAC:Sender_{i}", "HMAC:Collector", 1000.0, "2026-08-15T10:00:00", "SBIN")
    # 2 receivers from Collector
    for j in range(2):
        tg.add_edge("HMAC:Collector", f"HMAC:Receiver_{j}", 4500.0, "2026-08-15T11:00:00", "HDFC")

    extractor = FeatureExtractor(graph=tg)
    fan = extractor._calculate_fan_metrics("HMAC:Collector")
    assert fan["in_degree"] == 10.0
    assert fan["out_degree"] == 2.0
    assert pytest.approx(fan["asymmetry_score"], 0.01) == 0.80
    assert fan["in_volume"] == 10000.0
    assert fan["out_volume"] == 9000.0


def test_path_metrics():
    """Check 4.8: Path length detection for chain of 5 nodes."""
    tg = TemporalGraph()
    # N1 -> N2 -> N3 -> N4 -> N5
    nodes = [f"HMAC:N{i}" for i in range(1, 6)]
    for i in range(4):
        tg.add_edge(nodes[i], nodes[i+1], 1000.0, f"2026-08-15T10:{i*10:02d}:00", "SBIN")

    extractor = FeatureExtractor(graph=tg)
    p_start = extractor._calculate_path_metrics("HMAC:N1")
    p_mid = extractor._calculate_path_metrics("HMAC:N3")
    p_end = extractor._calculate_path_metrics("HMAC:N5")

    assert p_start["max_out_path_length"] == 5
    assert p_end["max_in_path_length"] == 5
    assert p_mid["total_path_length"] == 5


def test_first_time_edges():
    """Check 4.5: First-time counterparty anomaly detection."""
    tg = TemporalGraph()
    tg.add_edge("HMAC:X", "HMAC:Y", 1000.0, "2026-08-15T10:00:00", "SBIN")

    extractor = FeatureExtractor(graph=tg)
    ft = extractor._calculate_first_time_metrics("HMAC:X")
    assert ft["first_time_edge_ratio"] == 1.0


def test_round_figure_ratio():
    """Verify round figure transaction ratio (multiples of 1000/500)."""
    tg = TemporalGraph()
    tg.add_edge("HMAC:A", "HMAC:B", 5000.0, "2026-08-15T10:00:00", "SBIN")  # round
    tg.add_edge("HMAC:A", "HMAC:B", 10000.0, "2026-08-15T11:00:00", "SBIN") # round
    tg.add_edge("HMAC:A", "HMAC:B", 1234.56, "2026-08-15T12:00:00", "SBIN") # not round
    tg.add_edge("HMAC:A", "HMAC:B", 5500.0, "2026-08-15T13:00:00", "SBIN")  # round

    extractor = FeatureExtractor(graph=tg)
    ptn = extractor._calculate_transaction_pattern_metrics("HMAC:A")
    assert pytest.approx(ptn["round_figure_ratio"], 0.01) == 0.75


def test_structuring_score():
    """Verify structuring detection near reporting thresholds."""
    tg = TemporalGraph()
    tg.add_edge("HMAC:A", "HMAC:B", 49500.0, "2026-08-15T10:00:00", "SBIN") # under 50k
    tg.add_edge("HMAC:A", "HMAC:B", 980000.0, "2026-08-15T11:00:00", "SBIN") # under 10L
    tg.add_edge("HMAC:A", "HMAC:B", 10000.0, "2026-08-15T12:00:00", "SBIN") # normal

    extractor = FeatureExtractor(graph=tg)
    ptn = extractor._calculate_transaction_pattern_metrics("HMAC:A")
    assert pytest.approx(ptn["structuring_score"], 0.01) == 2.0 / 3.0


def test_full_feature_vector():
    """Check 4.7: Feature vector includes all expected features defined in spec."""
    tg = TemporalGraph()
    tg.add_edge("HMAC:Sender", "HMAC:Target", 49000.0, "2026-08-15T10:00:00", "SBIN", local_risk_score=0.45)
    tg.add_edge("HMAC:Target", "HMAC:Receiver", 47000.0, "2026-08-15T10:30:00", "HDFC", local_risk_score=0.55)

    extractor = FeatureExtractor(graph=tg)
    vec = extractor.extract_node_features("HMAC:Target")

    expected_keys = [
        "node_hash",
        "pass_through_ratio",
        "avg_time_between_incoming_and_outgoing",
        "min_time_between_incoming_and_outgoing",
        "max_time_between_incoming_and_outgoing",
        "std_dev_velocity",
        "velocity_count",
        "in_degree",
        "out_degree",
        "in_volume",
        "out_volume",
        "asymmetry_score",
        "concentration_score",
        "max_in_path_length",
        "max_out_path_length",
        "total_path_length",
        "first_time_sender_count",
        "first_time_receiver_count",
        "first_time_edge_ratio",
        "avg_amount_sent",
        "avg_amount_received",
        "max_amount_sent",
        "max_amount_received",
        "std_amount_sent",
        "std_amount_received",
        "round_figure_ratio",
        "structuring_score",
        "local_risk_score",
        "avg_local_risk_score",
        "max_local_risk_score"
    ]

    for k in expected_keys:
        assert k in vec, f"Missing feature {k} in feature vector"


def test_batch_feature_extraction():
    """Verify batch feature extraction returns formatted pandas DataFrame."""
    tg = TemporalGraph()
    for i in range(10):
        tg.add_edge(f"HMAC:u{i}", f"HMAC:u{i+1}", 5000.0, "2026-08-15T10:00:00", "SBIN")

    extractor = FeatureExtractor(graph=tg)
    nodes = [f"HMAC:u{i}" for i in range(11)]
    df = extractor.extract_features_batch(nodes)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 11
    assert "pass_through_ratio" in df.columns
    assert "total_path_length" in df.columns


def test_component_features_and_risk():
    """Check 4.9 & 4.20: Component features and mule motif risk scoring > 0.7."""
    tg = TemporalGraph()
    # Build 4-hop cross-bank mule chain: A -> B -> C -> D -> E
    chain_nodes = ["HMAC:M1", "HMAC:M2", "HMAC:M3", "HMAC:M4", "HMAC:M5"]
    banks = ["SBIN", "HDFC", "ICIC", "AXIS"]
    for i in range(4):
        tg.add_edge(
            chain_nodes[i],
            chain_nodes[i+1],
            50000.0 - (i * 500), # high pass-through ~0.99
            f"2026-08-15T10:{i*15:02d}:00", # rapid 15 min turnover
            banks[i],
            local_risk_score=0.75
        )

    detector = ComponentDetector(graph=tg)
    comps = detector.get_components_with_risk(min_size=2)
    
    assert len(comps) == 1
    mule_comp = comps[0]
    assert mule_comp["size"] == 5
    assert mule_comp["max_chain_length"] == 5
    assert mule_comp["risk_score"] >= 0.70, f"Expected risk > 0.7, got {mule_comp['risk_score']}"


def test_feature_normalization():
    """Verify feature normalization (z-score and min-max) with missing value handling."""
    data = {
        "pass_through_ratio": [0.1, 0.5, 0.9, np.nan],
        "total_path_length": [1, 3, 5, 2],
        "in_volume": [1000.0, 5000.0, 10000.0, 0.0]
    }
    df = pd.DataFrame(data)
    
    tg = TemporalGraph()
    extractor = FeatureExtractor(graph=tg)
    norm_z = extractor.normalize_features(df, method="zscore")
    norm_mm = extractor.normalize_features(df, method="minmax")

    assert not norm_z.isnull().values.any()
    assert not norm_mm.isnull().values.any()
    assert norm_mm["total_path_length"].max() <= 1.0
    assert norm_mm["total_path_length"].min() >= 0.0


def test_feature_extractor_performance():
    """Benchmark 4.19 & 4.26: Feature extraction on 1,000 nodes completes in < 10.0 seconds."""
    tg = TemporalGraph()
    # Ingest 2,000 edges spanning 1,000 nodes
    edges = [
        {
            "sender_hash": f"HMAC:perf_node_{i % 1000}",
            "receiver_hash": f"HMAC:perf_node_{(i + 1) % 1000}",
            "amount": float(1000 + (i % 5000)),
            "timestamp": "2026-08-15T12:00:00",
            "bank_id": f"BANK_{i % 4}",
            "local_risk_score": 0.2,
            "is_interbank": True
        }
        for i in range(2000)
    ]
    tg.add_edges_batch(edges)

    extractor = FeatureExtractor(graph=tg)
    node_list = [f"HMAC:perf_node_{i}" for i in range(1000)]

    start_t = time.time()
    df = extractor.extract_features_batch(node_list)
    duration = time.time() - start_t

    assert len(df) == 1000
    assert duration < 10.0, f"Extraction on 1000 nodes took {duration:.2f}s, exceeding 10.0s threshold"
