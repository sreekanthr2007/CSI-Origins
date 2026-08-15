"""Bank-side isolated local identity store (airgapped from central system)."""
from typing import Dict, Any, Optional


class BankVault:
    """Simulates the bank's internal core banking customer database and local hash lookup."""
    def __init__(self, bank_id: str):
        self.bank_id = bank_id
        self._local_accounts: Dict[str, Dict[str, Any]] = {}

    def register_account(self, account_number: str, ifsc: str, customer_profile: Dict[str, Any]) -> None:
        """Store account in bank's private internal storage."""
        self._local_accounts[account_number] = {
            "account_number": account_number,
            "ifsc": ifsc,
            **customer_profile
        }

    def resolve_identity(self, account_number: str) -> Optional[Dict[str, Any]]:
        """Internal lookup of customer profile."""
        return self._local_accounts.get(account_number)
