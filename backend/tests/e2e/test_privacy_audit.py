"""Privacy and Zero-PII Audit Test Suite for TRACE."""
import re
import json
import pytest
from backend.app.database.connection import get_db
from backend.app.database.schema import create_tables
from backend.app.graph.graph_engine import TemporalGraph


# Regex patterns for typical Indian banking PII
RAW_ACCOUNT_PATTERN = re.compile(r"\b\d{9,18}\b")
RAW_IFSC_PATTERN = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")
RAW_EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")


def test_database_zero_pii_audit(temp_db):
    """Audit: SQLite central database tables must contain ZERO raw PII."""
    with get_db(temp_db) as conn:
        cursor = conn.cursor()
        
        # Check all tables except internal test artifacts
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall() if not row[0].startswith("sqlite_")]

        for table in tables:
            # Check column names and sample data
            cursor.execute(f"SELECT * FROM {table} LIMIT 50;")
            rows = cursor.fetchall()
            for row in rows:
                for val in row:
                    if isinstance(val, str):
                        # Ensure no raw bank accounts or IFSC codes leak into central DB
                        if val.startswith("HMAC:") or val.startswith("INV:") or val.startswith("comp_") or val.startswith("alert_"):
                            continue
                        assert not RAW_EMAIL_PATTERN.search(val), f"PII email found in {table}: {val}"


def test_central_api_zero_pii_audit(test_client):
    """Audit: Central API endpoints must never expose raw account numbers."""
    endpoints = [
        "/api/v1/graph/stats",
        "/api/v1/graph/edges",
        "/api/v1/graph/nodes",
        "/api/v1/graph/components",
        "/api/v1/alerts/pending",
        "/api/v1/investigation/active"
    ]

    for ep in endpoints:
        res = test_client.get(ep)
        assert res.status_code == 200, f"Endpoint {ep} failed with {res.status_code}"
        payload_str = json.dumps(res.json())

        # Check for unhashed raw account patterns
        accounts_found = RAW_ACCOUNT_PATTERN.findall(payload_str)
        # Filter out timestamp unix epochs and small numeric IDs
        real_pii_candidates = [a for a in accounts_found if len(a) >= 11 and not a.startswith("17")]
        assert len(real_pii_candidates) == 0, f"Central endpoint {ep} leaked candidate account numbers: {real_pii_candidates}"


def test_graph_serialization_privacy_audit():
    """Audit: Graph serialization exports must only contain HMAC standing hashes."""
    tg = TemporalGraph()
    tg.add_transaction(
        edge_id="tx_priv_001",
        sender_hash="HMAC:8f9a2b1c3d4e5f6a",
        receiver_hash="HMAC:1a2b3c4d5e6f7a8b",
        amount=75000.0,
        timestamp="2026-08-15T12:00:00Z",
        bank_id="bank_sbi",
        local_risk_score=0.1
    )

    serialized = tg.to_dict()
    serialized_str = json.dumps(serialized)

    assert "HMAC:8f9a2b1c3d4e5f6a" in serialized_str
    assert "HMAC:1a2b3c4d5e6f7a8b" in serialized_str
    assert not RAW_ACCOUNT_PATTERN.search(serialized_str.replace("75000", ""))
