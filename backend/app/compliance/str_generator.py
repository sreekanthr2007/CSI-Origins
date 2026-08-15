"""Suspicious Transaction Report (STR) generator for FIU-IND / IDPIC compliance."""
import datetime
from typing import Dict, Any


class STRGenerator:
    """Formats detected mule account behaviors into regulatory Suspicious Transaction Report payloads."""
    def __init__(self):
        pass

    def generate_report(self, bank_id: str, account_info: Dict[str, Any], mule_pattern_evidence: Dict[str, Any]) -> Dict[str, Any]:
        """Generate official STR compliant payload."""
        return {
            "str_reference_number": f"STR-{bank_id}-{int(datetime.datetime.now(datetime.timezone.utc).timestamp())}",
            "reporting_entity": bank_id,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "regulatory_body": "FIU-IND / IDPIC",
            "account_summary": account_info,
            "evidence": mule_pattern_evidence,
            "recommended_action": "DEBIT_FREEZE_AND_REGULATORY_ESCALATION"
        }
