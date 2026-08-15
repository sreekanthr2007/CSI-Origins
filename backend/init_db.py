"""Standalone database initialization and seeding script."""
import sys
import os
import pathlib

# Set UTF-8 output encoding for Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Ensure workspace root is in sys.path
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.app.database.connection import init_db, get_db_path
from backend.app.database.schema import TABLE_NAMES
from backend.app.database.repositories import BankRepository

SEED_BANKS = [
    {"bank_name": "State Bank of India", "ifsc_prefix": "SBIN", "fingerprint": "SHA256:SBIN-ROOT-KEY-2026"},
    {"bank_name": "HDFC Bank", "ifsc_prefix": "HDFC", "fingerprint": "SHA256:HDFC-ROOT-KEY-2026"},
    {"bank_name": "ICICI Bank", "ifsc_prefix": "ICIC", "fingerprint": "SHA256:ICIC-ROOT-KEY-2026"},
    {"bank_name": "Axis Bank", "ifsc_prefix": "UTIB", "fingerprint": "SHA256:UTIB-ROOT-KEY-2026"},
    {"bank_name": "Punjab National Bank", "ifsc_prefix": "PUNB", "fingerprint": "SHA256:PUNB-ROOT-KEY-2026"},
    {"bank_name": "Bank of Baroda", "ifsc_prefix": "BARB", "fingerprint": "SHA256:BARB-ROOT-KEY-2026"},
    {"bank_name": "Canara Bank", "ifsc_prefix": "CNRB", "fingerprint": "SHA256:CNRB-ROOT-KEY-2026"},
    {"bank_name": "Yes Bank", "ifsc_prefix": "YESB", "fingerprint": "SHA256:YESB-ROOT-KEY-2026"},
    {"bank_name": "Kotak Mahindra Bank", "ifsc_prefix": "KKBK", "fingerprint": "SHA256:KKBK-ROOT-KEY-2026"},
    {"bank_name": "IndusInd Bank", "ifsc_prefix": "INDB", "fingerprint": "SHA256:INDB-ROOT-KEY-2026"},
]


def run_init():
    """Initialize database, create schema, and seed banks."""
    try:
        db_path = get_db_path()
        conn = init_db(db_path)
        conn.close()

        # Seed banks if not already present
        seeded_count = 0
        for bank in SEED_BANKS:
            existing = BankRepository.get_by_ifsc_prefix(bank["ifsc_prefix"], db_path)
            if not existing:
                BankRepository.create(
                    bank_name=bank["bank_name"],
                    ifsc_prefix=bank["ifsc_prefix"],
                    public_key_fingerprint=bank.get("fingerprint"),
                    db_path=db_path
                )
                seeded_count += 1

        rel_path = os.path.relpath(db_path, BASE_DIR).replace("\\", "/")
        tables_str = ", ".join(TABLE_NAMES)

        print("✅ Database initialized successfully")
        print(f"📁 Database location: {rel_path}")
        print(f"📋 Tables created: {tables_str}")
        print(f"🏦 Seeded {len(SEED_BANKS)} banks")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error during database initialization: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    run_init()
