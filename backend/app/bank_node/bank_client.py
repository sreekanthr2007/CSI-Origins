"""Bank node client simulation for alert reception and local action dispatch."""
from typing import Dict, Any, Optional
from backend.app.bank_node.bank_vault import BankVault


class BankClient:
    """Represents a participating bank node in the network."""
    def __init__(self, bank_id: str, bank_name: str):
        self.bank_id = bank_id
        self.bank_name = bank_name
        self.vault = BankVault(bank_id=bank_id)
        self.received_alerts: list[Dict[str, Any]] = []

    def receive_alert(self, alert_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Receive flagged alert from central intelligence and record in compliance queue."""
        self.received_alerts.append(alert_payload)
        return {
            "status": "ALERT_RECEIVED",
            "bank_id": self.bank_id,
            "alert_id": alert_payload.get("alert_id")
        }
