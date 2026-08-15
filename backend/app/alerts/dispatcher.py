"""Central Alert Dispatcher for cross-bank mule ring notification and lifecycle management."""
import time
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from backend.app.config import settings, Settings
from backend.app.database.repositories import AlertRepository, ComponentRepository
from backend.app.bank_node.bank_client import BankNodeRegistry, bank_registry as default_bank_registry, initialize_bank_nodes

logger = logging.getLogger("mule-detection-alert-dispatcher")


class AlertStatus:
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class AlertDispatcher:
    """Dispatches actionable, privacy-preserving alerts to involved banks with automated retry and audit tracking."""

    def __init__(
        self,
        registry: Optional[BankNodeRegistry] = None,
        bank_registry: Optional[BankNodeRegistry] = None,
        alert_repo: Optional[Any] = None,
        config: Optional[Settings] = None
    ):
        self.config = config or settings
        self.bank_registry = bank_registry or registry or default_bank_registry or initialize_bank_nodes()
        self.alert_repo = alert_repo



    def _determine_severity(self, risk_score: float) -> str:
        """Map quantitative risk score to categorical severity level."""
        score = float(risk_score)
        if score >= getattr(self.config, "CRITICAL_THRESHOLD", 0.85):
            return "critical"
        elif score >= getattr(self.config, "HIGH_THRESHOLD", 0.70):
            return "high"
        elif score >= getattr(self.config, "MEDIUM_THRESHOLD", 0.50):
            return "medium"
        else:
            return "low"

    def generate_alert(
        self,
        component_id: str,
        risk_score: float,
        explanation: Optional[Dict[str, Any]] = None,
        topology_snapshot: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create, persist, and format an alert record."""
        sev = self._determine_severity(risk_score)
        comp = ComponentRepository.get_by_id(component_id) or {}
        
        involved_banks = comp.get("bank_ids") or []
        if not involved_banks and topology_snapshot:
            involved_banks = list({e.get("bank_id") for e in topology_snapshot.get("edges", []) if e.get("bank_id")})
        if not involved_banks:
            involved_banks = ["bank_sbi", "bank_hdfc"]

        # Persist alert record
        rec = AlertRepository.create(
            component_id=component_id,
            severity=sev,
            dispatched_to=involved_banks
        )
        alert_id = rec["id"]

        now_iso = datetime.now(timezone.utc).isoformat()
        alert_payload = {
            "alert_id": alert_id,
            "id": alert_id,
            "component_id": component_id,
            "severity": sev,
            "risk_score": round(float(risk_score), 4),
            "involved_banks": involved_banks,
            "dispatched_to": involved_banks,
            "explanation": explanation or {"summary": "Anomalous high pass-through cross-bank transaction ring detected"},
            "topology_snapshot": topology_snapshot or {"nodes": comp.get("hashed_nodes", []), "edges": []},
            "dispatch_time": rec.get("dispatch_time", now_iso),
            "status": AlertStatus.PENDING,
            "resolution_status": AlertStatus.PENDING
        }

        logger.info(f"Generated alert {alert_id} (severity: {sev}, banks: {involved_banks})")
        return alert_payload

    def dispatch_alert(self, alert: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """Dispatch alert payload to all participating bank nodes with retry."""
        if alert is None:
            alert = self.generate_alert(
                component_id=kwargs.get("component_id", f"comp_{uuid.uuid4().hex[:8]}"),
                risk_score=kwargs.get("risk_score", 0.85),
                explanation=kwargs.get("explanation"),
                topology_snapshot=kwargs.get("topology_snapshot")
            )
            if "involved_banks" in kwargs:
                alert["involved_banks"] = kwargs["involved_banks"]
                alert["dispatched_to"] = kwargs["involved_banks"]

        alert_id = alert.get("alert_id") or alert.get("id")
        involved_banks = alert.get("involved_banks") or alert.get("dispatched_to", [])

        
        acknowledged: List[str] = []
        failed: List[str] = []

        for bank_id in involved_banks:
            bank_node = self.bank_registry.get_bank_by_id(bank_id)
            if not bank_node:
                # If bank_id format is short like 'SBI', try matching prefix
                for b in self.bank_registry.get_all_banks():
                    if b.bank_id.endswith(bank_id.lower()) or b.ifsc_prefix.lower() == bank_id.lower():
                        bank_node = b
                        break

            if bank_node:
                res = self._dispatch_with_retry(bank_node, alert)
                if res.get("status") == "acknowledged":
                    acknowledged.append(bank_node.bank_id)
                else:
                    failed.append(bank_node.bank_id)
            else:
                logger.warning(f"Bank node {bank_id} not found in registry; assuming offline")
                failed.append(bank_id)

        if acknowledged and alert_id:
            self.update_alert_status(alert_id, AlertStatus.ACKNOWLEDGED, notes=f"Acknowledged by {acknowledged}")

        logger.info(f"Dispatched alert {alert_id}: {len(acknowledged)} acknowledged, {len(failed)} failed")
        return {
            "status": "dispatched",
            "alert_id": alert_id,
            "bank_acknowledged": acknowledged,
            "acknowledged_banks": acknowledged,
            "failed": failed,
            "total_dispatched": len(involved_banks)
        }


    def _send_alert_to_bank(self, bank_node, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send alert to single bank node instance."""
        return bank_node.receive_alert(alert_data)

    def _dispatch_with_retry(self, bank_node, alert_data: Dict[str, Any], max_retries: int = 3) -> Dict[str, Any]:
        """Dispatch alert with exponential backoff on simulated network failure."""
        delay = 0.05
        for attempt in range(1, max_retries + 1):
            try:
                res = self._send_alert_to_bank(bank_node, alert_data)
                return res
            except Exception as e:
                logger.warning(f"Dispatch attempt {attempt}/{max_retries} to {bank_node.bank_id} failed: {e}")
                time.sleep(delay)
                delay *= 2
        return {"status": "failed", "bank_id": bank_node.bank_id}

    def update_alert_status(
        self,
        alert_id: str,
        status: str,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update resolution state of an alert in database."""
        now_iso = datetime.now(timezone.utc).isoformat() if status == AlertStatus.RESOLVED else None
        rec = AlertRepository.update_status(
            alert_id=alert_id,
            status=status,
            resolved_at=now_iso,
            notes=notes
        )
        if not rec:
            raise ValueError(f"Alert {alert_id} not found")
        return rec

    def get_alert_by_id(self, alert_id: str) -> Dict[str, Any]:
        """Retrieve full details of an alert."""
        rec = AlertRepository.get_by_id(alert_id)
        if not rec:
            raise ValueError(f"Alert {alert_id} not found")
        return rec

    def get_pending_alerts(self) -> List[Dict[str, Any]]:
        """Return all pending alerts."""
        return AlertRepository.get_pending_alerts()

    def get_alerts_by_bank(self, bank_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve alerts dispatched to a specific bank ID."""
        return AlertRepository.get_by_bank(bank_id, limit=limit)

    def get_alert_history(self, days: int = 7) -> List[Dict[str, Any]]:
        """Return recent alert history."""
        return AlertRepository.get_history(days=days)

    def get_resolved_alerts(self) -> List[Dict[str, Any]]:
        """Return all resolved alerts."""
        all_hist = self.get_alert_history(days=30)
        return [a for a in all_hist if a.get("resolution_status") == AlertStatus.RESOLVED]


# Global instance
alert_dispatcher = AlertDispatcher()
