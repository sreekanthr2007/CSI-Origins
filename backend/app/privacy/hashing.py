"""Cryptographic privacy layer using dual-tier HMAC-SHA256 standing and ephemeral hashing."""
import base64
import hashlib
import hmac
import json
import secrets
import logging
from typing import List, Optional
from Crypto.Cipher import AES
from backend.app.config import settings

logger = logging.getLogger("mule-detection-privacy")


def generate_standing_hash(account_number: str, ifsc_code: str, custom_key: Optional[str] = None) -> str:
    """Compute standing rotated HMAC-SHA256 hash for Flow A continuous boundary monitoring."""
    key = custom_key if custom_key is not None else settings.get_standing_key()
    message = f"{account_number.strip()}|{ifsc_code.strip()}".encode("utf-8")
    digest = hmac.new(key.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return f"HMAC:{digest}"


def generate_ephemeral_hash(account_number: str, bank_id: str, salt: str) -> str:
    """Compute ephemeral one-time HMAC-SHA256 hash for Flow B targeted investigation."""
    message = f"{account_number.strip()}|{bank_id.strip()}".encode("utf-8")
    digest = hmac.new(salt.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return f"INV:{digest}"


def hash_for_investigation(account_number: str, bank_id: str, salt: str) -> str:
    """Convenience alias for Flow B investigation hashing (returns INV:<hex>)."""
    return generate_ephemeral_hash(account_number, bank_id, salt)


def generate_investigation_salt() -> str:
    """Generate a 32-byte (64 character hex) cryptographically secure random investigation salt."""
    return secrets.token_bytes(32).hex()


def _get_encryption_key(custom_key: Optional[str] = None) -> bytes:
    """Derive 32-byte AES key from settings or custom key string."""
    k = custom_key if custom_key is not None else settings.get_standing_key()
    return hashlib.sha256(k.encode("utf-8")).digest()


def encrypt_salt(salt: str, key: Optional[str] = None) -> str:
    """Encrypt ephemeral investigation salt using AES-GCM (256-bit) for zero-plain-text database persistence."""
    aes_key = _get_encryption_key(key)
    cipher = AES.new(aes_key, AES.MODE_GCM)
    ciphertext, tag = cipher.encrypt_and_digest(salt.encode("utf-8"))
    payload = {
        "nonce": base64.b64encode(cipher.nonce).decode("utf-8"),
        "tag": base64.b64encode(tag).decode("utf-8"),
        "ciphertext": base64.b64encode(ciphertext).decode("utf-8")
    }
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")


def decrypt_salt(encrypted_str: str, key: Optional[str] = None) -> str:
    """Decrypt persisted AES-GCM encrypted salt string."""
    if not encrypted_str:
        return ""
    try:
        raw_json = base64.b64decode(encrypted_str.encode("utf-8")).decode("utf-8")
        payload = json.loads(raw_json)
        nonce = base64.b64decode(payload["nonce"].encode("utf-8"))
        tag = base64.b64decode(payload["tag"].encode("utf-8"))
        ciphertext = base64.b64decode(payload["ciphertext"].encode("utf-8"))

        aes_key = _get_encryption_key(key)
        cipher = AES.new(aes_key, AES.MODE_GCM, nonce=nonce)
        decrypted = cipher.decrypt_and_verify(ciphertext, tag)
        return decrypted.decode("utf-8")
    except Exception as e:
        logger.error(f"Failed to decrypt salt: {e}")
        raise ValueError("Decryption failed or invalid ciphertext/key")


class HashingService:
    """Stateless, in-memory zero-persistence hashing service for central intelligence."""

    def __init__(self, config=None):
        self.config = config or settings
        self._hash_computation_count = 0
        self._current_key = self.config.get_standing_key()
        logger.info("HashingService initialized with in-memory standing key")

    def compute_hash(self, account_number: str, ifsc_code: str) -> str:
        """Compute standing hash without logging or persisting raw input values."""
        self._hash_computation_count += 1
        return generate_standing_hash(account_number, ifsc_code, custom_key=self._current_key)

    def rotate_key(self) -> str:
        """Trigger standing key rotation and update in-memory reference."""
        new_key = self.config.rotate_standing_key()
        self._current_key = new_key
        logger.warning("Standing HMAC key rotated in HashingService")
        return self.get_current_key_fingerprint()

    def get_current_key_fingerprint(self) -> str:
        """Return SHA-256 fingerprint of current standing key for public audit trail."""
        return hashlib.sha256(self._current_key.encode("utf-8")).hexdigest()

    def compute_with_historical_keys(self, account_number: str, ifsc_code: str) -> List[str]:
        """Return standing hashes generated with current key and all active historical keys."""
        keys = [self._current_key] + self.config.get_historical_keys()
        unique_keys = list(dict.fromkeys(keys))
        hashes = [generate_standing_hash(account_number, ifsc_code, custom_key=k) for k in unique_keys]
        return hashes

    @property
    def computation_count(self) -> int:
        """Return count of hashes computed."""
        return self._hash_computation_count
