"""Bank-side airgapped identity vault for private customer registration and hash de-anonymization."""
import datetime
import logging
from typing import Dict, Any, List, Optional
from backend.app.privacy.hashing import generate_standing_hash

logger = logging.getLogger("mule-detection-bank-vault")


class BankVault:
    """Simulates an isolated bank-internal core banking customer identity repository."""

    def __init__(self, bank_id: str, bank_name: str):
        self.bank_id = bank_id
        self.bank_name = bank_name
        self._local_accounts: Dict[str, Dict[str, Any]] = {}
        self._resolution_log: List[Dict[str, Any]] = []
        logger.debug(f"BankVault initialized for {bank_name} ({bank_id})")

    def register_account(
        self,
        account_number: str,
        ifsc_code: str,
        customer_name: str,
        kyc_status: str = "verified",
        declared_income: float = 25000.0,
        account_age_days: int = 45,
        is_dormant: bool = False
    ) -> Dict[str, Any]:
        """Compute standing hash and register account inside bank's internal storage."""
        standing_hash = generate_standing_hash(account_number, ifsc_code)
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        record = {
            "hash": standing_hash,
            "account_number": str(account_number),
            "ifsc_code": str(ifsc_code),
            "bank_id": self.bank_id,
            "bank_name": self.bank_name,
            "customer_name": customer_name,
            "kyc_status": kyc_status,
            "declared_income": float(declared_income),
            "account_age_days": int(account_age_days),
            "is_dormant": bool(is_dormant),
            "created_at": now
        }
        self._local_accounts[standing_hash] = record
        return record

    def register_accounts(self, accounts: List[Dict[str, Any]]) -> int:
        """Bulk register accounts into internal vault."""
        count = 0
        for acc in accounts:
            self.register_account(
                account_number=acc["account_number"],
                ifsc_code=acc["ifsc_code"],
                customer_name=acc.get("customer_name", "Anonymous User"),
                kyc_status=acc.get("kyc_status", "verified"),
                declared_income=acc.get("declared_income", 30000.0),
                account_age_days=acc.get("account_age_days", 60),
                is_dormant=acc.get("is_dormant", False)
            )
            count += 1
        return count

    def resolve_hash(self, hash_value: str) -> Optional[Dict[str, Any]]:
        """De-anonymize a flagged hash against this bank's private records."""
        account = self._local_accounts.get(hash_value)
        self._resolution_log.append({
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "query_hash": hash_value,
            "resolved": account is not None,
            "bank_id": self.bank_id
        })
        return account

    def get_resolution_log(self) -> List[Dict[str, Any]]:
        """Return compliance audit history of hash lookups."""
        return list(self._resolution_log)

    @property
    def total_accounts(self) -> int:
        """Return count of registered accounts in vault."""
        return len(self._local_accounts)
