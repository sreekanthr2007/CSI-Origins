"""Bank node simulation, airgapped identity vault, and alert acknowledgement client."""
import uuid
import json
import logging
from typing import Dict, Any, List, Optional

from backend.app.privacy.bank_vault import BankVault, BANK_VAULTS
from backend.app.privacy.hashing import hash_for_investigation
from backend.app.compliance.str_generator import str_generator

logger = logging.getLogger("mule-detection-bank-client")

DEFAULT_BANKS = [
    {"bank_id": "bank_sbi", "bank_name": "State Bank of India", "ifsc_prefix": "SBIN"},
    {"bank_id": "bank_hdfc", "bank_name": "HDFC Bank", "ifsc_prefix": "HDFC"},
    {"bank_id": "bank_icici", "bank_name": "ICICI Bank", "ifsc_prefix": "ICIC"},
    {"bank_id": "bank_axis", "bank_name": "Axis Bank", "ifsc_prefix": "UTIB"},
    {"bank_id": "bank_pnb", "bank_name": "Punjab National Bank", "ifsc_prefix": "PUNB"},
    {"bank_id": "bank_bob", "bank_name": "Bank of Baroda", "ifsc_prefix": "BARB"},
    {"bank_id": "bank_canara", "bank_name": "Canara Bank", "ifsc_prefix": "CNRB"},
    {"bank_id": "bank_yes", "bank_name": "Yes Bank", "ifsc_prefix": "YESB"},
    {"bank_id": "bank_kotak", "bank_name": "Kotak Mahindra Bank", "ifsc_prefix": "KKBK"},
    {"bank_id": "bank_indusind", "bank_name": "IndusInd Bank", "ifsc_prefix": "INDB"},
]


class BankNode:
    """Represents a simulated autonomous bank participant with isolated core identity vault and alert reception."""

    def __init__(
        self,
        bank_id: str,
        bank_name: str,
        ifsc_prefix: str,
        vault: Optional[BankVault] = None
    ):
        self.bank_id = bank_id
        self.bank_name = bank_name
        self.ifsc_prefix = ifsc_prefix
        self.vault = vault or BankVault(bank_id=bank_id, bank_name=bank_name)
        self.received_alerts: List[Dict[str, Any]] = []

        # Register in global vault registry
        BANK_VAULTS[bank_id] = self.vault

    def get_neighborhood(self, node_hash: str, ephemeral_salt: str) -> List[Dict[str, Any]]:
        """Return intra-bank edges and ephemeral hashed neighborhood for a target node."""
        results: List[Dict[str, Any]] = []
        resolved = self.resolve_hash(node_hash)
        if resolved:
            acc_num = resolved["account_number"]
            inv_hash = hash_for_investigation(acc_num, self.bank_id, ephemeral_salt)
            results.append({
                "investigation_hash": inv_hash,
                "bank_id": self.bank_id,
                "account_type": resolved.get("account_type", "SAVINGS"),
                "local_risk_score": resolved.get("local_risk_score", 0.10)
            })
        return results

    def resolve_hash(self, hash_value: str) -> Optional[Dict[str, Any]]:
        """De-anonymize a flagged HMAC standing hash against this bank's private records."""
        return self.vault.resolve_hash(hash_value)

    def receive_alert(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """Receive, record, and acknowledge incoming suspicious mule alert from central intelligence."""
        alert_id = alert_data.get("alert_id") or alert_data.get("id", str(uuid.uuid4()))
        self.received_alerts.append(alert_data)
        logger.info(f"Bank {self.bank_name} ({self.bank_id}) received and acknowledged alert {alert_id}")
        return {
            "status": "acknowledged",
            "bank_id": self.bank_id,
            "bank_name": self.bank_name,
            "alert_id": alert_id
        }

    def generate_str(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate official regulatory STR for any account in the alert belonging to this bank."""
        # Find first matching local account
        account_details = None
        for h in alert_data.get("topology_snapshot", {}).get("nodes", []):
            acc = self.resolve_hash(h)
            if acc:
                account_details = acc
                break

        if not account_details:
            account_details = {
                "account_number": f"{self.ifsc_prefix}9990001",
                "customer_name": "Target Account Holder",
                "bank_name": self.bank_name,
                "is_dormant": True
            }

        return str_generator.generate_str(alert_data, self.bank_id, account_details)

    def recommend_actions(
        self,
        account_details: Optional[Dict[str, Any]] = None,
        risk_score: float = 0.50
    ) -> List[str]:
        """Return recommended actions based on risk severity."""
        if risk_score >= 0.85:
            return ["Freeze Account", "File STR Immediately", "Manual Review"]
        elif risk_score >= 0.70:
            return ["Temporary Lien", "Enhanced Monitoring", "Flag for Review"]
        elif risk_score >= 0.50:
            return ["Enhanced Monitoring", "30-day Review"]
        else:
            return ["Flag for Review"]


class BankNodeRegistry:
    """Manages bank node registration, routing, and hash ownership lookup."""

    def __init__(self):
        self._banks_by_id: Dict[str, BankNode] = {}
        self._banks_by_prefix: Dict[str, BankNode] = {}

    def register_bank(self, bank_node: BankNode) -> None:
        """Register a bank node instance."""
        self._banks_by_id[bank_node.bank_id] = bank_node
        self._banks_by_prefix[bank_node.ifsc_prefix.upper()] = bank_node

    def get_bank_by_id(self, bank_id: str) -> Optional[BankNode]:
        """Lookup bank node by ID."""
        return self._banks_by_id.get(bank_id)

    def get_bank_by_hash(self, node_hash: str) -> Optional[BankNode]:
        """Resolve which bank owns a standing hash by querying individual vaults."""
        for bank in self._banks_by_id.values():
            if bank.resolve_hash(node_hash) is not None:
                return bank
        return None

    def get_all_banks(self) -> List[BankNode]:
        """Return list of all registered bank nodes."""
        return list(self._banks_by_id.values())

    def get_active_banks(self) -> List[BankNode]:
        """Return list of all active bank nodes."""
        return list(self._banks_by_id.values())

    def __len__(self) -> int:
        return len(self._banks_by_id)


def initialize_bank_nodes() -> BankNodeRegistry:
    """Create and seed the 10 bank node instances and isolated vaults."""
    registry = BankNodeRegistry()
    for b in DEFAULT_BANKS:
        node = BankNode(
            bank_id=b["bank_id"],
            bank_name=b["bank_name"],
            ifsc_prefix=b["ifsc_prefix"]
        )
        registry.register_bank(node)
    logger.info(f"Initialized {len(registry)} simulated bank nodes")
    return registry


# Global instance
bank_registry = initialize_bank_nodes()
