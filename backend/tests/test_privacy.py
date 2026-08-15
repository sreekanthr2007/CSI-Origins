"""Unit tests for HMAC-SHA256 privacy and hashing schemes."""
import pytest
from backend.app.privacy.hashing import compute_standing_hash, compute_ephemeral_hash


def test_standing_hash_consistency():
    """Verify identical inputs with same key produce deterministic standing hash."""
    key = "secret_registry_key_123"
    hash1 = compute_standing_hash("1234567890", "SBIN0001234", key)
    hash2 = compute_standing_hash("1234567890", "SBIN0001234", key)
    assert hash1 == hash2
    assert len(hash1) == 64


def test_standing_hash_different_keys():
    """Verify rotated key produces distinct hashes for same account."""
    hash1 = compute_standing_hash("1234567890", "SBIN0001234", "key_period_1")
    hash2 = compute_standing_hash("1234567890", "SBIN0001234", "key_period_2")
    assert hash1 != hash2


def test_ephemeral_hash_uniqueness():
    """Verify ephemeral salt isolates investigations."""
    hash1 = compute_ephemeral_hash("1234567890", "SBI", "salt_case_A")
    hash2 = compute_ephemeral_hash("1234567890", "SBI", "salt_case_B")
    assert hash1 != hash2
