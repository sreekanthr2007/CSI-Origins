"""Privacy and cryptographic hashing services."""
from typing import Optional
import hashlib
import hmac


def compute_standing_hash(account_number: str, ifsc_code: str, secret_key: str) -> str:
    """Compute standing rotated HMAC-SHA256 hash for Flow A continuous boundary monitoring."""
    message = f"{account_number.strip()}:{ifsc_code.strip()}".encode("utf-8")
    return hmac.new(secret_key.encode("utf-8"), message, hashlib.sha256).hexdigest()


def compute_ephemeral_hash(account_number: str, bank_id: str, investigation_salt: str) -> str:
    """Compute ephemeral one-time HMAC-SHA256 hash for Flow B targeted investigation."""
    message = f"{account_number.strip()}:{bank_id.strip()}".encode("utf-8")
    return hmac.new(investigation_salt.encode("utf-8"), message, hashlib.sha256).hexdigest()
