"""Central alert routing and dispatching service."""
import uuid
from typing import Dict, Any, List


class AlertDispatcher:
    """Dispatches targeted alerts to affected banks when a high-risk component is detected."""
    def __init__(self):
        self.dispatched_alerts: List[Dict[str, Any]] = []

    def dispatch_alert(self, component_id: str, bank_ids: List[str], risk_score: float, details: Dict[str, Any]) -> Dict[str, Any]:
        """Create and route alert payload to target bank endpoints."""
        alert = {
            "alert_id": str(uuid.uuid4()),
            "component_id": component_id,
            "bank_ids": bank_ids,
            "risk_score": risk_score,
            "details": details
        }
        self.dispatched_alerts.append(alert)
        return alert
