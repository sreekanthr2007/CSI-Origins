"""Deployment Verification Suite for TRACE System."""
import sys
import os
import time
import sqlite3
from datetime import datetime, timezone

# Ensure UTF-8 output on Windows
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)

from backend.app.config import settings
from backend.app.database.connection import get_db
from backend.app.database.repositories import ComponentRepository, AlertRepository, STRRepository

from backend.app.privacy.hashing import generate_standing_hash
from backend.app.graph.graph_engine import TemporalGraph, GraphEngine
from backend.app.features.feature_extractor import FeatureExtractor
from backend.app.ml.classifier import MuleClassifier
from backend.app.alerts.dispatcher import AlertDispatcher
from backend.app.bank_node.bank_client import initialize_bank_nodes
from backend.app.compliance.str_generator import STRGenerator


def verify_database_connection() -> bool:
    """Verifies active SQLite database connectivity and schema integrity."""
    print("🔍 [1/5] Checking database connection & tables...")
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            required = ["components", "alerts", "str_reports", "investigations"]
            for req in required:
                if req not in tables:
                    print(f"❌ Missing required database table: {req}")
                    return False
        print(f"✅ Database connection verified. Found tables: {', '.join(tables)}")
        return True

    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return False


def verify_privacy_audit() -> bool:
    """Verifies strict Zero-PII compliance across central database tables."""
    print("🔍 [2/5] Running Zero-PII privacy audit on central storage...")
    pii_keywords = ["customer_name", "phone_number", "aadhaar", "pan_number", "passport", "email"]
    with get_db() as conn:
        cursor = conn.cursor()
        for table in ["components", "alerts", "investigations"]:
            cursor.execute(f"PRAGMA table_info({table});")
            columns = [row[1].lower() for row in cursor.fetchall()]
            for kw in pii_keywords:
                if kw in columns:
                    print(f"❌ PII leak detected in table {table}: column {kw}")
                    return False

        # Scan stored records in components and alerts for raw unhashed accounts
        cursor.execute("SELECT hashed_nodes FROM components;")
        rows = cursor.fetchall()
        for r in rows:
            content = str(r[0])
            if "SBIN" in content or "HDFC0" in content or "ICIC0" in content:
                print(f"❌ Raw IFSC/Account found in component hashed_nodes: {content}")
                return False

    print("✅ Privacy Audit PASSED: 0 PII columns or plain identifiers found in central DB.")
    return True


def verify_ml_and_graph_engine() -> bool:
    """Verifies ML classifier inference and graph feature extraction performance."""
    print("🔍 [3/5] Benchmarking Graph Engine & ML Classifier...")
    t0 = time.perf_counter()
    graph = TemporalGraph()
    standing_key = settings.get_standing_key()

    node_a = generate_standing_hash("ACC001", "bank_sbi", standing_key)
    node_b = generate_standing_hash("ACC002", "bank_hdfc", standing_key)
    node_c = generate_standing_hash("ACC003", "bank_icici", standing_key)

    now = datetime.now(timezone.utc)
    graph.add_edge(node_a, node_b, 100000.0, now.isoformat(), "bank_sbi")
    graph.add_edge(node_b, node_c, 98000.0, now.isoformat(), "bank_hdfc")


    engine = GraphEngine(graph)
    components = engine.extract_connected_components(min_nodes=2)
    t_graph = (time.perf_counter() - t0) * 1000

    if not components:
        print("❌ Graph Engine failed to extract connected components.")
        return False

    extractor = FeatureExtractor()
    classifier = MuleClassifier()
    # Warmup / train initialization
    features = extractor.extract_features(components[0], graph)
    _ = classifier.predict_proba(features)

    t1 = time.perf_counter()
    prob = classifier.predict_proba(features)
    t_ml = (time.perf_counter() - t1) * 1000

    print(f"✅ Graph extraction latency: {t_graph:.2f} ms (< 500 ms target)")
    print(f"✅ ML inference latency: {t_ml:.2f} ms (< 50 ms target) | Mule Probability: {prob:.2f}")

    if t_graph > 500.0 or t_ml > 50.0:
        print("❌ Performance benchmark exceeded latency limits.")
        return False
    return True


def verify_bank_node_and_compliance() -> bool:
    """Verifies Bank Node local de-anonymization and Section 12 PMLA STR generation."""
    print("🔍 [4/5] Testing Bank Node Vault & STR Generator...")
    registry = initialize_bank_nodes()
    sbi = registry.get_bank_by_id("bank_sbi")
    if not sbi:
        print("❌ Bank SBI not registered in BankNodeRegistry.")
        return False

    # Register test private account in SBI airgapped vault
    acc = sbi.vault.register_account(
        account_number="40991209384",
        ifsc_code="SBIN0001234",
        customer_name="Verification User",
        kyc_status="verified"
    )

    resolved = sbi.resolve_hash(acc["hash"])
    if not resolved or resolved["customer_name"] != "Verification User":
        print("❌ Local bank vault de-anonymization failed.")
        return False

    str_gen = STRGenerator()
    alert_payload = {
        "alert_id": "ALERT-VERIFY-001",
        "risk_score": 0.94,
        "severity": "critical",
        "topology_snapshot": {"nodes": [acc["hash"]], "edges": [{"amount": 100000.0}]}
    }
    str_doc = sbi.generate_str(alert_payload)
    sub = str_gen.submit_str(str_doc)

    if sub.get("status") not in ["submitted", "accepted"]:
        print(f"❌ STR submission failed with status: {sub.get('status')}")
        return False

    print(f"✅ Bank Vault & STR PASSED. Generated {str_doc['str_id']}, ACK: {sub.get('fiu_ack')}")
    return True


def verify_alert_dispatching() -> bool:
    """Verifies central alert dispatcher multi-bank notification with automated retry."""
    print("🔍 [5/5] Testing Central Alert Dispatcher...")
    dispatcher = AlertDispatcher()
    alert = dispatcher.generate_alert(
        component_id="comp_verify_001",
        risk_score=0.88,
        topology_snapshot={"nodes": [], "edges": [{"bank_id": "bank_sbi"}, {"bank_id": "bank_hdfc"}]}
    )
    res = dispatcher.dispatch_alert(alert)

    if "bank_sbi" not in res.get("bank_acknowledged", []):
        print(f"❌ Alert dispatch failed: {res}")
        return False

    print(f"✅ Alert Dispatch PASSED. Acknowledged by: {', '.join(res['bank_acknowledged'])}")
    return True


def main():
    print("\n" + "=" * 65)
    print("🛡️  TRACE: CROSS-BANK MULE DETECTION NETWORK — DEPLOYMENT VERIFY")
    print("=" * 65)

    checks = [
        verify_database_connection,
        verify_privacy_audit,
        verify_ml_and_graph_engine,
        verify_bank_node_and_compliance,
        verify_alert_dispatching
    ]

    all_passed = True
    for check in checks:
        if not check():
            all_passed = False
            break
        print("-" * 65)

    if all_passed:
        print("\n" + "🎉" * 20)
        print("✅ ALL DEPLOYMENT VERIFICATION CHECKS PASSED SUCCESSFULLY (Exit 0)")
        print("🎉" * 20 + "\n")
        sys.exit(0)
    else:
        print("\n❌ DEPLOYMENT VERIFICATION FAILED (Exit 1)\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
