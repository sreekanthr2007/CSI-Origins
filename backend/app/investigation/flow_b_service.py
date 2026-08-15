"""Flow B deep targeted investigation service with ephemeral salt lifecycle."""
import secrets
from typing import Dict, Any, Optional


class FlowBInvestigationService:
    """Manages on-demand targeted neighborhood pulls and ephemeral salt lifecycle."""
    def __init__(self):
        self.active_investigations: Dict[str, Dict[str, Any]] = {}

    def start_investigation(self, case_id: str, target_hash: str) -> str:
        """Create a one-time investigation session with fresh ephemeral salt."""
        ephemeral_salt = secrets.token_hex(16)
        self.active_investigations[case_id] = {
            "case_id": case_id,
            "target_hash": target_hash,
            "ephemeral_salt": ephemeral_salt,
            "status": "ACTIVE"
        }
        return ephemeral_salt

    def close_investigation(self, case_id: str) -> bool:
        """Destroy ephemeral salt and close investigation session."""
        if case_id in self.active_investigations:
            del self.active_investigations[case_id]
            return True
        return False
