"""Comprehensive unit and performance tests for database layer and repositories."""
import os
import time
import json
import sqlite3
import pytest
import tempfile
import pathlib

from backend.app.database.connection import get_db_connection, init_db, get_db
from backend.app.database.schema import create_tables, drop_tables, table_exists, TABLE_NAMES
from backend.app.database.repositories import (
    BankRepository,
    EdgeRepository,
    ComponentRepository,
    InvestigationRepository,
    AlertRepository,
    STRRepository,
)


@pytest.fixture
def temp_db():
    """Create an isolated temporary SQLite database for each test."""
    temp_dir = tempfile.mkdtemp()
    db_file = os.path.join(temp_dir, "test_mule.db")
    init_db(db_file)
    yield db_file
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Connection & Schema Tests
# ---------------------------------------------------------------------------
def test_connection_creates_db(temp_db):
    """Verify that the database file is physically created."""
    assert os.path.exists(temp_db)


def test_connection_has_foreign_keys(temp_db):
    """Verify PRAGMA foreign_keys = ON is strictly active."""
    conn = get_db_connection(temp_db)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys;")
    row = cursor.fetchone()
    conn.close()
    assert row[0] == 1


def test_tables_exist(temp_db):
    """Verify all 7 tables exist after init."""
    for table in TABLE_NAMES:
        assert table_exists(table, get_db_connection(temp_db)) is True


def test_table_schema(temp_db):
    """Verify key columns for each table."""
    conn = get_db_connection(temp_db)
    cursor = conn.cursor()
    
    # Check banks columns
    cursor.execute("PRAGMA table_info(banks);")
    bank_cols = [r["name"] for r in cursor.fetchall()]
    assert "id" in bank_cols
    assert "bank_name" in bank_cols
    assert "ifsc_prefix" in bank_cols
    assert "is_active" in bank_cols
    
    # Check hashed_edges columns
    cursor.execute("PRAGMA table_info(hashed_edges);")
    edge_cols = [r["name"] for r in cursor.fetchall()]
    assert "sender_hash" in edge_cols
    assert "receiver_hash" in edge_cols
    assert "amount" in edge_cols
    assert "bank_id" in edge_cols

    conn.close()


def test_foreign_keys_enforced(temp_db):
    """Verify foreign key violation raises sqlite3.IntegrityError."""
    conn = get_db_connection(temp_db)
    cursor = conn.cursor()
    with pytest.raises(sqlite3.IntegrityError):
        # Insert edge pointing to non-existent bank_id
        cursor.execute(
            """
            INSERT INTO hashed_edges (sender_hash, receiver_hash, amount, timestamp, bank_id)
            VALUES ('hash1', 'hash2', 1000.0, '2026-08-15T12:00:00', 'invalid_bank_id');
            """
        )
        conn.commit()
    conn.close()


def test_migration_rollback(temp_db):
    """Verify clean drop_tables and recreation."""
    conn = get_db_connection(temp_db)
    drop_tables(conn)
    for table in TABLE_NAMES:
        assert table_exists(table, conn) is False
    create_tables(conn)
    for table in TABLE_NAMES:
        assert table_exists(table, conn) is True
    conn.close()


# ---------------------------------------------------------------------------
# BankRepository Tests
# ---------------------------------------------------------------------------
def test_create_and_get_bank(temp_db):
    """Create and retrieve a bank record."""
    bank = BankRepository.create("State Bank of India", "SBIN", "SHA256:SBIN-KEY", db_path=temp_db)
    assert bank is not None
    assert bank["ifsc_prefix"] == "SBIN"
    assert bank["is_active"] == 1
    assert len(bank["id"]) == 32  # 32 hex char UUID

    by_id = BankRepository.get_by_id(bank["id"], db_path=temp_db)
    assert by_id["bank_name"] == "State Bank of India"

    by_ifsc = BankRepository.get_by_ifsc_prefix("SBIN", db_path=temp_db)
    assert by_ifsc["id"] == bank["id"]


def test_update_and_delete_bank(temp_db):
    """Update bank name and soft delete."""
    bank = BankRepository.create("HDFC Bank", "HDFC", db_path=temp_db)
    updated = BankRepository.update(bank["id"], db_path=temp_db, bank_name="HDFC Bank Ltd")
    assert updated["bank_name"] == "HDFC Bank Ltd"

    BankRepository.delete(bank["id"], db_path=temp_db)
    active_banks = BankRepository.get_all(active_only=True, db_path=temp_db)
    assert not any(b["id"] == bank["id"] for b in active_banks)
    
    all_banks = BankRepository.get_all(active_only=False, db_path=temp_db)
    assert any(b["id"] == bank["id"] for b in all_banks)


# ---------------------------------------------------------------------------
# EdgeRepository Tests
# ---------------------------------------------------------------------------
def test_batch_insert_and_queries(temp_db):
    """Test batch insert, time range query, and node query."""
    bank = BankRepository.create("Axis Bank", "UTIB", db_path=temp_db)
    
    edges = [
        {"sender_hash": "nodeA", "receiver_hash": "nodeB", "amount": 50000.0, "timestamp": "2026-08-15T10:00:00", "bank_id": bank["id"], "local_risk_score": 0.2},
        {"sender_hash": "nodeB", "receiver_hash": "nodeC", "amount": 49500.0, "timestamp": "2026-08-15T10:30:00", "bank_id": bank["id"], "local_risk_score": 0.8},
        {"sender_hash": "nodeC", "receiver_hash": "nodeD", "amount": 49000.0, "timestamp": "2026-08-15T11:00:00", "bank_id": bank["id"], "local_risk_score": 0.9},
    ]

    inserted = EdgeRepository.batch_insert(edges, db_path=temp_db)
    assert inserted == 3

    # Time range query
    in_range = EdgeRepository.get_edges_in_time_range("2026-08-15T10:00:00", "2026-08-15T10:45:00", db_path=temp_db)
    assert len(in_range) == 2

    # Node query
    node_b_edges = EdgeRepository.get_edges_for_node("nodeB", db_path=temp_db)
    assert len(node_b_edges) == 2

    # Historical edge count
    count = EdgeRepository.count_edges_between("nodeA", "nodeB", db_path=temp_db)
    assert count == 1
    count_nonexistent = EdgeRepository.count_edges_between("nodeA", "nodeZ", db_path=temp_db)
    assert count_nonexistent == 0

    # Component edges
    comp_edges = EdgeRepository.get_edges_for_component(["nodeA", "nodeB"], db_path=temp_db)
    assert len(comp_edges) == 2


# ---------------------------------------------------------------------------
# ComponentRepository Tests
# ---------------------------------------------------------------------------
def test_save_and_retrieve_component(temp_db):
    """Save component with JSON fields and query."""
    comp_data = {
        "detection_time": "2026-08-15T10:35:00",
        "risk_score": 0.9450,
        "hashed_nodes": ["nodeA", "nodeB", "nodeC"],
        "bank_ids": ["SBI", "HDFC", "ICICI"],
        "feature_vector": {"pass_through_ratio": 0.98, "hops": 3, "velocity_min": 30},
        "shap_explanation": {"top_driver": "pass_through_ratio", "impact": 0.45},
        "status": "active"
    }

    saved = ComponentRepository.save(comp_data, db_path=temp_db)
    assert saved["id"] is not None
    assert saved["risk_score"] == 0.9450
    assert saved["hashed_nodes"] == ["nodeA", "nodeB", "nodeC"]

    by_id = ComponentRepository.get_by_id(saved["id"], db_path=temp_db)
    assert by_id["feature_vector"]["pass_through_ratio"] == 0.98

    by_node = ComponentRepository.get_by_node_hash("nodeB", db_path=temp_db)
    assert len(by_node) >= 1
    assert by_node[0]["id"] == saved["id"]

    updated = ComponentRepository.update_status(saved["id"], "investigating", db_path=temp_db)
    assert updated["status"] == "investigating"


# ---------------------------------------------------------------------------
# InvestigationRepository Tests
# ---------------------------------------------------------------------------
def test_create_and_close_investigation(temp_db):
    """Create investigation with ephemeral salt and close it."""
    comp = ComponentRepository.save({
        "detection_time": "2026-08-15T12:00:00",
        "risk_score": 0.89,
        "hashed_nodes": ["n1", "n2"],
        "bank_ids": ["SBI"],
        "feature_vector": {},
        "shap_explanation": {}
    }, db_path=temp_db)

    inv = InvestigationRepository.create(
        component_id=comp["id"],
        investigation_salt="salt_enc_9876543210",
        banks_queried=["SBI", "HDFC"],
        db_path=temp_db
    )
    assert inv["status"] == "active"
    assert inv["investigation_salt"] == "salt_enc_9876543210"
    assert "SBI" in inv["banks_queried"]

    closed = InvestigationRepository.close_investigation(inv["id"], closed_by="decay_halting", db_path=temp_db)
    assert closed["status"] == "closed"
    assert closed["closed_by"] == "decay_halting"
    assert closed["completed_at"] is not None


# ---------------------------------------------------------------------------
# Alert & STR Repository Tests
# ---------------------------------------------------------------------------
def test_alert_and_str_lifecycle(temp_db):
    """Create alert, link to bank, update status, and generate STR report."""
    bank = BankRepository.create("ICICI Bank", "ICIC", db_path=temp_db)
    comp = ComponentRepository.save({
        "detection_time": "2026-08-15T13:00:00",
        "risk_score": 0.92,
        "hashed_nodes": ["node1", "node2"],
        "bank_ids": [bank["id"]],
        "feature_vector": {"velocity": 15},
        "shap_explanation": {}
    }, db_path=temp_db)

    alert = AlertRepository.create(
        component_id=comp["id"],
        severity="critical",
        dispatched_to=[bank["id"]],
        db_path=temp_db
    )
    assert alert["severity"] == "critical"
    assert alert["resolution_status"] == "pending"

    # Link alert to component
    ComponentRepository.update_status(comp["id"], "alerted", alert_id=alert["id"], db_path=temp_db)

    # Query pending alerts
    pending = AlertRepository.get_pending_alerts(db_path=temp_db)
    assert any(a["id"] == alert["id"] for a in pending)

    # Generate STR Report
    payload = STRRepository.generate_str_payload(
        account_details={"account_number": "1234567890", "holder": "De-anonymized User"},
        component_data=comp
    )
    str_rec = STRRepository.create(alert["id"], bank["id"], payload, db_path=temp_db)
    assert str_rec["filed_status"] == "draft"
    assert str_rec["report_payload"]["regulatory_agency"] == "FIU-IND / IDPIC"

    # Update STR filed status
    updated_str = STRRepository.update_status(str_rec["id"], "submitted", db_path=temp_db)
    assert updated_str["filed_status"] == "submitted"


# ---------------------------------------------------------------------------
# Performance Benchmarks
# ---------------------------------------------------------------------------
def test_batch_insert_and_query_performance(temp_db):
    """Verify 1,000 edge batch insert < 1s and queries < 50ms."""
    bank = BankRepository.create("Kotak Mahindra Bank", "KKBK", db_path=temp_db)
    
    edges = []
    base_ts = 1700000000
    for i in range(1000):
        edges.append({
            "sender_hash": f"perf_node_{i % 50}",
            "receiver_hash": f"perf_node_{(i + 1) % 50}",
            "amount": 1000.0 + i,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(base_ts + i * 60)),
            "bank_id": bank["id"],
            "local_risk_score": 0.1,
            "is_interbank": True
        })

    # Benchmark Batch Insert
    t0 = time.time()
    count = EdgeRepository.batch_insert(edges, db_path=temp_db)
    insert_duration = time.time() - t0
    assert count == 1000
    assert insert_duration < 1.0  # Must be under 1 second

    # Benchmark Query by Timestamp Range
    t0 = time.time()
    results = EdgeRepository.get_edges_in_time_range(
        "2023-11-14T22:13:20",
        "2023-11-15T05:00:00",
        db_path=temp_db
    )
    query_duration_ms = (time.time() - t0) * 1000
    assert query_duration_ms < 50.0  # Must be under 50ms

    # Benchmark Query by Node Hash
    t0 = time.time()
    node_edges = EdgeRepository.get_edges_for_node("perf_node_10", limit=100, db_path=temp_db)
    node_duration_ms = (time.time() - t0) * 1000
    assert len(node_edges) > 0
    assert node_duration_ms < 50.0  # Must be under 50ms
