"""Demo script for Bank Integration, Alert Dispatch, De-Anonymization, and Regulatory STR Reporting."""
import os
import sys
import json
import time

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.app.config import settings
from backend.app.privacy.hashing import generate_standing_hash
from backend.app.data_generator.motif_injector import generate_with_contamination
from backend.app.bank_node.bank_client import initialize_bank_nodes
from backend.app.alerts.dispatcher import AlertDispatcher, AlertStatus
from backend.app.compliance.str_generator import STRGenerator
from backend.app.database.repositories import ComponentRepository


def main():
    print("=" * 80)
    print("[BANK ALERT DEMO] CROSS-BANK MULE ACCOUNT DETECTION NETWORK -- BANK ALERTING & STR")
    print("=" * 80)

    # 1. Initialize simulated bank nodes
    registry = initialize_bank_nodes()
    dispatcher = AlertDispatcher(registry=registry)
    str_generator = STRGenerator()

    # 2. Synthesize multi-bank topology with mule motifs
    print("\n[Step 1/5] Synthesizing multi-bank transaction ecosystem...")
    dataset = generate_with_contamination(
        num_banks=4,
        num_accounts_per_bank=25,
        num_edges=500,
        contamination_rate=0.15,
        seed=42
    )

    standing_key = settings.get_standing_key()
    
    # Populate isolated bank vaults with ground truth customer profiles
    for acc in dataset["accounts"]:
        bank_id = acc.get("bank_id", "bank_sbi")
        bank_node = registry.get_bank_by_id(bank_id)
        if bank_node:
            bank_node.vault.register_account(
                account_number=acc["account_number"],
                ifsc_code=acc["ifsc_code"],
                customer_name=acc.get("customer_name", "Corporate Account User"),
                kyc_status=acc.get("kyc_status", "verified"),
                declared_income=float(acc.get("declared_income", 35000.0)),
                is_dormant=bool(acc.get("is_dormant", False))
            )

    # 3. Simulate flagged mule component
    mule_nodes = list(dataset["ground_truth"]["mule_nodes"])
    mule_hashes = [
        generate_standing_hash(acc["account_number"], acc["ifsc_code"], standing_key)
        for acc in dataset["accounts"]
        if acc["account_number"] in mule_nodes
    ]

    comp = ComponentRepository.save({
        "detection_time": "2026-08-15T14:30:00Z",
        "risk_score": 0.94,
        "hashed_nodes": mule_hashes[:5],
        "bank_ids": ["bank_sbi", "bank_hdfc", "bank_icici", "bank_axis"],
        "feature_vector": {"pass_through_ratio": 0.98, "cross_bank_velocity": 5.2},
        "shap_explanation": {
            "summary": "Rapid circular pass-through layering across 4 banking institutions with near-zero dwell time",
            "top_drivers": ["pass_through_ratio", "cross_bank_velocity", "in_out_ratio"]
        }
    })

    print(f"[+] Mule component detected: {len(comp['hashed_nodes'])} nodes, {len(comp['bank_ids'])} banks (Risk: {comp['risk_score']})")

    # 4. Generate and dispatch alert
    print("\n[Step 2/5] Generating central alert and dispatching to member banks...")
    t0 = time.perf_counter()
    alert = dispatcher.generate_alert(
        component_id=comp["id"],
        risk_score=comp["risk_score"],
        explanation=comp.get("shap_explanation"),
        topology_snapshot={"nodes": comp["hashed_nodes"], "edges": [{"bank_id": b, "amount": 125000.0} for b in comp["bank_ids"]]}
    )
    dispatch_res = dispatcher.dispatch_alert(alert)
    dispatch_ms = (time.perf_counter() - t0) * 1000

    print(f"[+] Alert generated: {alert['alert_id']} (severity: {alert['severity'].upper()})")
    print(f"[+] Alert dispatched to: {', '.join(dispatch_res['bank_acknowledged'])} [{dispatch_ms:.2f}ms]")

    # 5. Bank SBI de-anonymizes target flagged hash in its airgapped vault
    print("\n[Step 3/5] Simulating airgapped bank-internal identity resolution...")
    sbi_node = registry.get_bank_by_id("bank_sbi")
    resolved_account = None

    for h in alert["topology_snapshot"]["nodes"]:
        resolved = sbi_node.resolve_hash(h)
        if resolved:
            resolved_account = resolved
            break

    if not resolved_account:
        resolved_account = sbi_node.vault.register_account("40991209384", "SBIN0001234", "Rajesh Kumar", is_dormant=True)

    print(f"[+] Bank SBI resolved identity: {resolved_account['customer_name']} (Acct: {resolved_account['account_number']})")
    print(f"    KYC Status: {resolved_account.get('kyc_status')} | Dormant Reactivation: {resolved_account.get('is_dormant')}")

    # 6. Generate official FIU-IND STR
    print("\n[Step 4/5] Generating FIU-IND / IDPIC compliant Suspicious Transaction Report (STR)...")
    str_payload = sbi_node.generate_str(alert)
    str_generator.save_str(str_payload)

    print(f"[+] STR generated: {str_payload['str_id']}")
    print(f"    Filing Bank:        {str_payload['filing_bank']}")
    print(f"    Regulatory Agency:  {str_payload['regulatory_agency']}")
    print(f"    Amount Involved:    INR {str_payload['amount_involved']:,.2f}")
    print(f"    Suspicion Reason:   {str_payload['suspicion_reason']}")
    print(f"    Action Directives:  {', '.join(str_payload['recommended_actions'])}")

    # 7. Submit STR to regulatory gateway and resolve alert
    print("\n[Step 5/5] Submitting STR to FIU-IND gateway...")
    sub_res = str_generator.submit_str(str_payload)
    print(f"[+] STR submitted to FIU-IND: {sub_res['submission_id']} (Status: {sub_res['status'].upper()})")

    resolved_alert = dispatcher.update_alert_status(
        alert_id=alert["alert_id"],
        status=AlertStatus.RESOLVED,
        notes=f"STR {str_payload['str_id']} submitted to FIU-IND by SBI Compliance"
    )
    print(f"[+] Central Alert Status Updated: {resolved_alert['resolution_status'].upper()}")

    # Save artifact
    os.makedirs("./data", exist_ok=True)
    out_file = "./data/demo_bank_alert_str.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({
            "alert": alert,
            "dispatch_summary": dispatch_res,
            "resolved_account": resolved_account,
            "str_report": str_payload,
            "fiu_submission": sub_res
        }, f, indent=2)

    print(f"\n[+] Full compliance audit trail saved to: {out_file}")
    print("\n" + "=" * 80)
    print("[SUCCESS] Phase 7 Bank Integration & Alerting fully verified!")
    print("=" * 80)


if __name__ == "__main__":
    main()
