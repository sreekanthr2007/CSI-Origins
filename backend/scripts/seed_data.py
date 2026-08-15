"""Seed script to generate and persist synthetic dataset with injected mule motifs."""
import sys
import os
import pathlib

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.app.database.connection import init_db, get_db_path
from backend.app.database.repositories import BankRepository, EdgeRepository
from backend.app.privacy.hashing import generate_standing_hash
from backend.app.privacy.bank_vault import BankVault
from backend.app.data_generator.motif_injector import generate_with_contamination


def seed_synthetic_dataset():
    """Generate 5 banks, 500 accounts, 5,000 edges with 10% contamination and save to DB."""
    try:
        db_path = get_db_path()
        init_db(db_path)

        print("🔄 Generating synthetic multi-bank transaction dataset with 10% mule motifs...")
        dataset = generate_with_contamination(
            num_banks=5,
            num_accounts_per_bank=100,
            num_edges=5000,
            contamination_rate=0.10,
            seed=42
        )

        banks = dataset["banks"]
        accounts = dataset["accounts"]
        edges = dataset["edges"]
        ground_truth = dataset["ground_truth"]

        # 1. Register/Ensure Banks in DB & Vaults
        vaults = {}
        for b in banks:
            existing = BankRepository.get_by_ifsc_prefix(b["ifsc_prefix"], db_path)
            if not existing:
                BankRepository.create(bank_name=b["name"], ifsc_prefix=b["ifsc_prefix"], db_path=db_path)
            vaults[b["id"]] = BankVault(bank_id=b["id"], bank_name=b["name"])

        # 2. Register Accounts in Local Bank Vaults
        for acc in accounts:
            b_id = acc["bank_id"]
            if b_id in vaults:
                vaults[b_id].register_account(
                    account_number=acc["account_number"],
                    ifsc_code=acc["ifsc_code"],
                    customer_name=acc.get("customer_name", "Citizen Account"),
                    kyc_status=acc.get("kyc_status", "verified"),
                    declared_income=acc.get("declared_income", 30000.0)
                )

        # 3. Hash Edges and Batch Insert to Database
        db_bank_map = {b["ifsc_prefix"]: BankRepository.get_by_ifsc_prefix(b["ifsc_prefix"], db_path)["id"] for b in banks}

        hashed_edges = []
        for e in edges:
            sender_hash = generate_standing_hash(e["sender_account"], e["sender_ifsc"])
            receiver_hash = generate_standing_hash(e["receiver_account"], e["receiver_ifsc"])
            
            # Map sender bank prefix to DB bank ID
            sender_prefix = e["sender_ifsc"][:4]
            db_bank_id = db_bank_map.get(sender_prefix, list(db_bank_map.values())[0])

            hashed_edges.append({
                "sender_hash": sender_hash,
                "receiver_hash": receiver_hash,
                "amount": e["amount"],
                "timestamp": e["timestamp"],
                "bank_id": db_bank_id,
                "local_risk_score": e.get("local_risk_score", 0.1),
                "is_interbank": e.get("is_interbank", True)
            })

        inserted_count = EdgeRepository.batch_insert(hashed_edges, db_path=db_path)

        print("✅ Synthetic data seeded successfully!")
        print(f"🏦 Participating Banks: {len(banks)}")
        print(f"👥 Total Customer Accounts: {len(accounts)}")
        print(f"🔗 Total Hashed Edges Inserted: {inserted_count}")
        print(f"🚨 Injected Mule Motifs: {len(dataset['motifs'])}")
        print(f"🎯 Target vs Actual Contamination: 10.0% / {ground_truth['actual_contamination_rate']*100:.1f}%")
        print(f"📁 Database Location: {db_path}")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error seeding synthetic data: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    seed_synthetic_dataset()
