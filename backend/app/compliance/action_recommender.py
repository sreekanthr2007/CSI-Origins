"""Action recommendation engine based on risk score and compliance impact."""
import logging
from typing import Dict, Any, List, Optional
from backend.app.config import settings, Settings

logger = logging.getLogger("mule-detection-action-recommender")

ACTION_DESCRIPTIONS = {
    "Debit Freeze": "Temporarily restricts outgoing transactions and debits to prevent fund dissipation while allowing incoming credits.",
    "File STR Immediately": "Generates and files an expedited Suspicious Transaction Report directly to FIU-IND/IDPIC.",
    "Escalate to Compliance Officer": "Directs the alert to senior AML/CFT compliance officers for prioritized manual review.",
    "Notify Anti-Fraud Team": "Alerts the internal transaction monitoring and cyber fraud response unit.",
    "Temporary Lien": "Places a temporary hold on specific suspicious funds pending counterparty verification.",
    "Enhanced Monitoring (30 days)": "Enables heightened real-time transaction surveillance and lower velocity anomaly thresholds for 30 days.",
    "Enhanced Monitoring (15 days)": "Enables heightened real-time transaction surveillance for 15 days.",
    "Flag for Review": "Marks the account in the core banking system for risk analyst review.",
    "Notify Relationship Manager": "Alerts the branch relationship manager to verify customer business profile and source of funds.",
    "Monitor for 7 days": "Passive watch period on inbound and outbound transaction velocity."
}

ACTION_PRIORITIES = {
    "Debit Freeze": 1,
    "File STR Immediately": 1,
    "Escalate to Compliance Officer": 2,
    "Temporary Lien": 2,
    "Notify Anti-Fraud Team": 2,
    "Enhanced Monitoring (30 days)": 3,
    "Enhanced Monitoring (15 days)": 3,
    "Notify Relationship Manager": 4,
    "Flag for Review": 4,
    "Monitor for 7 days": 5
}


class ActionRecommender:
    """Recommends standardized, severity-calibrated compliance and risk-mitigation actions."""

    def __init__(self, config: Optional[Settings] = None):
        self.config = config or settings
        self.critical_thresh = getattr(self.config, "CRITICAL_THRESHOLD", 0.85)
        self.high_thresh = getattr(self.config, "HIGH_THRESHOLD", 0.70)
        self.medium_thresh = getattr(self.config, "MEDIUM_THRESHOLD", 0.50)
        self.low_thresh = getattr(self.config, "LOW_THRESHOLD", 0.30)

    def recommend_actions(
        self,
        account_details: Optional[Dict[str, Any]] = None,
        risk_score: float = 0.50
    ) -> List[Dict[str, Any]]:
        """Return prioritized list of regulatory and operational actions based on risk severity."""
        score = float(risk_score)
        actions: List[Dict[str, Any]] = []

        if score >= self.critical_thresh:
            action_names = [
                ("Debit Freeze", f"Critical risk score ({score:.2f}) indicates active high-speed mule laundering"),
                ("File STR Immediately", "Mandatory immediate filing under FIU-IND Section 12 PMLA"),
                ("Escalate to Compliance Officer", "Requires immediate manual sign-off for account restriction"),
                ("Notify Anti-Fraud Team", "Cross-bank coordinated incident response required")
            ]
        elif score >= self.high_thresh:
            action_names = [
                ("Temporary Lien", f"High risk score ({score:.2f}) warrants provisional hold on suspicious inflows"),
                ("File STR Immediately", "Suspicious transaction topology meets STR threshold"),
                ("Enhanced Monitoring (30 days)", "30-day continuous surveillance on all transactions"),
                ("Flag for Review", "Account placed in high-priority review queue")
            ]
        elif score >= self.medium_thresh:
            action_names = [
                ("Enhanced Monitoring (15 days)", f"Medium risk score ({score:.2f}) with anomalous transaction velocity"),
                ("Flag for Review", "Flagged for periodic compliance review"),
                ("Notify Relationship Manager", "Verify customer declared income and business activity")
            ]
        else:
            action_names = [
                ("Flag for Review", f"Low risk score ({score:.2f}) flagged for baseline audit"),
                ("Monitor for 7 days", "Standard 7-day passive monitoring")
            ]

        for name, reason in action_names:
            actions.append({
                "action": name,
                "priority": self.get_action_priority(name),
                "reason": reason,
                "description": self.get_action_description(name)
            })

        # Sort by priority ascending (1 = highest priority)
        actions.sort(key=lambda x: x["priority"])
        return actions

    def get_action_description(self, action: str) -> str:
        """Return detailed compliance impact description for an action."""
        return ACTION_DESCRIPTIONS.get(action, "Standard compliance procedure.")

    def get_action_priority(self, action: str) -> int:
        """Return priority rank (1 = highest, 5 = lowest)."""
        return ACTION_PRIORITIES.get(action, 3)
