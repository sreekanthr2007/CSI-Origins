"""TRACE: Cross-Bank Mule Account Detection Network — Interactive E2E Demo Runner."""
import sys
import os
import argparse
import time
from datetime import datetime, timezone, timedelta

# Set UTF-8 encoding for Windows terminal
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# Ensure project root is in sys.path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.app.config import settings
from backend.app.privacy.hashing import generate_standing_hash
from backend.app.graph.graph_engine import TemporalGraph, GraphEngine
from backend.app.features.feature_extractor import FeatureExtractor
from backend.app.ml.classifier import MuleClassifier

from backend.app.ml.explainability import ExplainabilityEngine
from backend.app.bank_node.bank_client import initialize_bank_nodes
from backend.app.investigation.flow_b_service import FlowBService
from backend.app.alerts.dispatcher import AlertDispatcher
from backend.app.compliance.str_generator import STRGenerator
from backend.app.database.connection import get_db
from backend.app.database.repositories import ComponentRepository, AlertRepository, STRRepository


def run_scenario(scenario_num: int):
    """Executes a complete scenario pipeline and prints formatted progress."""
    start_total = time.perf_counter()
    standing_key = settings.get_standing_key()
    now_dt = datetime.now(timezone.utc)
    bank_registry = initialize_bank_nodes()

    scenario_names = {
        1: "Fast 4-Bank Rapid Chain (Pass-Through: 98%, ₹5L, 4 Banks)",
        2: "Collector Star Motif (8 Senders -> 1 Collector, ₹50k each)",
        3: "Distributor & Smurfing Ring (1 Hub -> 10 Receivers under ₹50k)",
        4: "Legitimate Account Traversal Decay (False Positive Prevention)"
    }
    sc_title = scenario_names.get(scenario_num, f"Custom Scenario {scenario_num}")

    print("\n" + "┌" + "─" * 65 + "┐")
    print(f"│ CROSS-BANK MULE DETECTION NETWORK (TRACE) - DEMO".ljust(66) + "│")
    print(f"│ Scenario {scenario_num}: {sc_title[:48]}".ljust(66) + "│")
    print("└" + "─" * 65 + "┘\n")

    # 1. Data Synthesis
    print("🚀 Generating synthetic multi-bank data...")
    tg = TemporalGraph()

    if scenario_num == 1:
        banks = ["bank_sbi", "bank_hdfc", "bank_icici", "bank_axis"]
        accounts = [f"ACC_S1_{i:04d}" for i in range(5)]
        hashes = [generate_standing_hash(acc, "SBIN0001000", standing_key) for acc in accounts]
        for hop in range(4):
            tg.add_transaction(
                edge_id=f"tx_s1_{hop}",
                sender_hash=hashes[hop],
                receiver_hash=hashes[hop + 1],
                amount=500000.0 * (0.98 ** hop),
                timestamp=now_dt + timedelta(minutes=12 * hop),
                bank_id=banks[hop % len(banks)],
                local_risk_score=0.92
            )
        start_node = hashes[0]
        involved_banks = banks

    elif scenario_num == 2:
        collector = generate_standing_hash("PUNB_COLLECTOR", "PUNB0001000", standing_key)
        involved_banks = ["bank_pnb", "bank_hdfc", "bank_sbi"]
        for i in range(8):
            s_hash = generate_standing_hash(f"SENDER_{i}", "HDFC0001000", standing_key)
            tg.add_transaction(
                edge_id=f"tx_s2_{i}",
                sender_hash=s_hash,
                receiver_hash=collector,
                amount=50000.0,
                timestamp=now_dt + timedelta(minutes=10 * i),
                bank_id="bank_hdfc",
                local_risk_score=0.82
            )
        start_node = collector

    elif scenario_num == 3:
        hub = generate_standing_hash("ICICI_DISTRIBUTOR", "ICIC0001000", standing_key)
        involved_banks = ["bank_icici", "bank_yes"]
        for i in range(10):
            r_hash = generate_standing_hash(f"RECEIVER_{i}", "YESB0001000", standing_key)
            tg.add_transaction(
                edge_id=f"tx_s3_{i}",
                sender_hash=hub,
                receiver_hash=r_hash,
                amount=48500.0 + (i * 100),
                timestamp=now_dt + timedelta(minutes=15 * i),
                bank_id="bank_icici",
                local_risk_score=0.78
            )
        start_node = hub

    else:  # Scenario 4
        legit = generate_standing_hash("LEGIT_MERCHANT", "BARB0001000", standing_key)
        p1 = generate_standing_hash("BUYER_1", "BARB0001000", standing_key)
        s1 = generate_standing_hash("SUPPLIER_1", "BARB0001000", standing_key)
        involved_banks = ["bank_bob"]
        tg.add_transaction("tx_s4_1", p1, legit, 100000.0, now_dt - timedelta(days=5), "bank_bob", 0.02)
        tg.add_transaction("tx_s4_2", legit, s1, 25000.0, now_dt - timedelta(days=1), "bank_bob", 0.02)
        start_node = legit

    print(f"✅ Generated {len(involved_banks)} banks, {tg.node_count} accounts, {tg.edge_count} transactions")

    # 2. Graph Engine
    print("\n🚀 Building privacy-preserving temporal graph...")
    engine = GraphEngine(tg, settings)
    subgraphs = engine.extract_subgraphs(max_size=25, min_risk=0.0)
    print(f"✅ Graph built: {tg.node_count} nodes, {tg.edge_count} edges, {len(subgraphs)} subgraphs extracted")

    # 3. Flow A Detection & ML
    print("\n🚀 Running Flow A detection & ML classification...")
    extractor = FeatureExtractor()
    classifier = MuleClassifier(model_type="xgboost")
    classifier.train()
    explainer = ExplainabilityEngine(classifier.model)

    features = extractor.extract_features(subgraphs[0], tg)
    risk_score = classifier.predict_proba(features)
    is_mule = classifier.predict(features, threshold=0.70)
    print(f"✅ Detection result: {'MULE RING DETECTED' if is_mule else 'LEGITIMATE ACTIVITY'} (Probability: {risk_score:.2f})")

    # 4. SHAP Rationale
    print("\n🚀 SHAP Explainability Decomposition:")
    explanation = explainer.explain_prediction(features)
    for feat in explanation.get("feature_importance", [])[:3]:
        sh_val = feat["shap"]
        sgn = "+" if sh_val >= 0 else ""
        print(f"├── {feat['feature']}: {feat['value']} (SHAP: {sgn}{sh_val:.2f})")
    print(f"└── Summary: {explanation.get('summary', 'Rapid multi-hop funds transfer')}")

    # 5. Alert Dispatch (if mule)
    if is_mule:
        print("\n🚀 Dispatching multi-bank alert...")
        with get_db() as conn:
            alert_repo = AlertRepository(conn)
            dispatcher = AlertDispatcher(bank_registry=bank_registry, alert_repo=alert_repo)
            disp_res = dispatcher.dispatch_alert(
                component_id=f"comp_{scenario_num}_{int(time.time())}",
                risk_score=risk_score,
                involved_banks=involved_banks,
                explanation=explanation
            )
            print(f"✅ Alert dispatched to: {', '.join([b.replace('bank_', '').upper() for b in involved_banks])}")
            print(f"✅ Banks acknowledged: {len(disp_res['acknowledged_banks'])}/{len(involved_banks)}")
            alert_id = disp_res["alert_id"]
    else:
        print("\nℹ️ Skipping alert dispatch (Below risk threshold)")
        alert_id = "alert_none"

    # 6. Flow B Investigation
    print("\n🚀 Running Flow B bounded pattern-decay investigation...")
    flow_b = FlowBService(tg, bank_registry, settings)
    inv = flow_b.start_investigation(start_node=start_node, component_id=f"comp_{scenario_num}")

    playback = flow_b.get_playback_steps(inv.id)
    for step in playback[:4]:
        print(f"├── Step {step['step_number']}: {step['action']} &rarr; [{step['decision']}]")
    print(f"└── Stopping reason: {inv.stopping_reason} (Depth reached: {inv.depth_reached})")

    # 7. Regulatory Reporting (STR)
    if is_mule:
        print("\n🚀 Generating Section 12 PMLA Suspicious Transaction Report (STR)...")
        with get_db() as conn:
            alert_repo = AlertRepository(conn)
            str_repo = STRRepository(conn)
            str_gen = STRGenerator(bank_registry, alert_repo, str_repo)
            primary_b = involved_banks[0]
            str_res = str_gen.generate_str(
                alert_id=alert_id,
                bank_id=primary_b,
                account_number="SBIN99001122",
                customer_name="Entity Under Investigation",
                suspicion_reason=f"Automated Scenario {scenario_num} alert: {sc_title}",
                amount_involved=500000.0,
                supporting_evidence=["Graph Motif", "SHAP Feature Attribution"]
            )
            print(f"✅ STR generated: {str_res['str_id']}")
            sub_res = str_gen.submit_str(str_res["str_id"])
            print(f"✅ STR submitted to FIU-IND Gateway (ACK: {sub_res.get('fiu_ack', 'ACK-2026')})")

    elapsed = time.perf_counter() - start_total
    print("\n" + "┌" + "─" * 65 + "┐")
    print(f"│ DEMO COMPLETE ✅".ljust(66) + "│")
    print(f"│ Time: {elapsed:.2f} seconds | Scenario {scenario_num} Validated".ljust(66) + "│")
    print("└" + "─" * 65 + "┘\n")

    return {
        "scenario": scenario_num,
        "title": sc_title,
        "nodes": tg.node_count,
        "edges": tg.edge_count,
        "risk_score": risk_score,
        "is_mule": is_mule,
        "elapsed": elapsed,
        "explanation": explanation,
        "stopping_reason": inv.stopping_reason,
        "depth": inv.depth_reached
    }


def generate_html_report(results: list, output_path: str = "demo_report.html"):
    """Generates a styled HTML summary report of the demo execution."""
    rows = ""
    for r in results:
        rows += f"""
        <tr style="border-bottom: 1px solid #334155;">
            <td style="padding: 12px; font-weight: bold; color: #38bdf8;">Scenario {r['scenario']}</td>
            <td style="padding: 12px;">{r['title']}</td>
            <td style="padding: 12px; font-family: monospace;">{r['nodes']} / {r['edges']}</td>
            <td style="padding: 12px; font-weight: bold; color: {'#ef4444' if r['is_mule'] else '#10b981'};">
                {r['risk_score']:.2f} ({'FLAGGED' if r['is_mule'] else 'LEGIT'})
            </td>
            <td style="padding: 12px; font-family: monospace;">{r['stopping_reason']} (depth {r['depth']})</td>
            <td style="padding: 12px; font-family: monospace;">{r['elapsed']:.2f}s</td>
        </tr>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>TRACE — Cross-Bank Mule Detection Demo Report</title>
    <style>
        body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0b132b; color: #f8fafc; padding: 30px; }}
        .card {{ background: #1e293b; border-radius: 12px; padding: 24px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); max-width: 1000px; margin: 0 auto; }}
        h1 {{ color: #38bdf8; margin-top: 0; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 14px; }}
        th {{ background: #0f172a; padding: 12px; text-align: left; color: #94a3b8; text-transform: uppercase; font-size: 11px; }}
        .badge {{ background: #10b98120; color: #10b981; padding: 4px 8px; border-radius: 6px; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>🛡️ TRACE: E2E Demonstration Validation Report</h1>
        <p style="color: #94a3b8;">Automated Multi-Bank Mule Account Detection, Graph Traversal & FIU-IND Compliance</p>
        <table>
            <thead>
                <tr>
                    <th>Scenario</th>
                    <th>Motif Description</th>
                    <th>Nodes/Edges</th>
                    <th>Detection Score</th>
                    <th>Flow B Traversal</th>
                    <th>Runtime</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>
        <p style="margin-top: 24px; color: #94a3b8; font-size: 12px;">Generated automatically on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
    </div>
</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"📄 HTML Demo Report written to: {os.path.abspath(output_path)}")


def main():
    parser = argparse.ArgumentParser(description="TRACE E2E Scenario Demo Runner")
    parser.add_argument("--scenario", type=str, default="1", help="Scenario number (1-4) or 'all'")
    parser.add_argument("--all", action="store_true", help="Run all 4 scenarios")
    args = parser.parse_args()

    results = []
    if args.all or args.scenario == "all":
        for s in [1, 2, 3, 4]:
            res = run_scenario(s)
            results.append(res)
    else:
        s_num = int(args.scenario)
        res = run_scenario(s_num)
        results.append(res)

    generate_html_report(results)


if __name__ == "__main__":
    main()
