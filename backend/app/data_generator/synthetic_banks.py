"""Synthetic Indian Bank Registry and Account Profiles."""
from typing import List, Dict, Any

INDIAN_BANKS = [
    {"bank_id": "SBI", "bank_name": "State Bank of India", "ifsc_prefix": "SBIN000"},
    {"bank_id": "HDFC", "bank_name": "HDFC Bank", "ifsc_prefix": "HDFC000"},
    {"bank_id": "ICICI", "bank_name": "ICICI Bank", "ifsc_prefix": "ICIC000"},
    {"bank_id": "AXIS", "bank_name": "Axis Bank", "ifsc_prefix": "UTIB000"},
    {"bank_id": "PNB", "bank_name": "Punjab National Bank", "ifsc_prefix": "PUNB000"},
]


def get_registered_banks() -> List[Dict[str, Any]]:
    """Return simulated participating bank entities."""
    return INDIAN_BANKS
