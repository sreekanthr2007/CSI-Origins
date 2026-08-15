"""Unit and integration tests for cryptographic privacy layer and bank vaults."""
import pytest
import logging
from backend.app.config import settings
from backend.app.privacy.hashing import (
    generate_standing_hash,
    generate_ephemeral_hash,
    generate_investigation_salt,
    HashingService,
)
from backend.app.privacy.bank_vault import BankVault


def test_standing_hash_deterministic():
    """Verify that hashing identical account+IFSC produces identical hashes."""
    account = "SBIN40991209384"
    ifsc = "SBIN0001234"
    h1 = generate_standing_hash(account, ifsc)
    h2 = generate_standing_hash(account, ifsc)
    assert h1 == h2
    assert len(h1) == 5 + 64  # "HMAC:" + 64 hex chars


def test_standing_hash_changes_on_rotation():
    """Verify that rotating standing key produces different hashes for identical account."""
    account = "HDFC50100234567"
    ifsc = "HDFC0001234"
    
    h1 = generate_standing_hash(account, ifsc, custom_key="key_2026_period_1")
    h2 = generate_standing_hash(account, ifsc, custom_key="key_2026_period_2")
    assert h1 != h2


def test_ephemeral_hash_different_salts():
    """Verify different investigation salts isolate cases."""
    account = "ICIC90011223344"
    bank = "bank_icici"
    salt1 = generate_investigation_salt()
    salt2 = generate_investigation_salt()
    
    h1 = generate_ephemeral_hash(account, bank, salt1)
    h2 = generate_ephemeral_hash(account, bank, salt2)
    assert h1 != h2


def test_ephemeral_hash_consistent_with_same_salt():
    """Verify ephemeral hash is consistent within the same investigation session."""
    account = "UTIB10020030040"
    bank = "bank_axis"
    salt = generate_investigation_salt()
    
    h1 = generate_ephemeral_hash(account, bank, salt)
    h2 = generate_ephemeral_hash(account, bank, salt)
    assert h1 == h2
    assert h1.startswith("INV:")
    assert len(h1) == 4 + 64  # "INV:" + 64 hex chars


def test_no_persistence_service(caplog):
    """Verify HashingService processes hashes in-memory and never logs raw account numbers or IFSCs."""
    service = HashingService(settings)
    raw_account = "CONFIDENTIAL_ACCT_9988776655"
    raw_ifsc = "PUNB0009999"

    with caplog.at_level(logging.DEBUG):
        hash_result = service.compute_hash(raw_account, raw_ifsc)

    assert hash_result.startswith("HMAC:")
    # Ensure raw sensitive values never appear in log records
    for record in caplog.records:
        assert raw_account not in record.message
        assert raw_ifsc not in record.message


def test_investigation_salt_generation():
    """Verify investigation salt is cryptographically random, 32 bytes (64 hex chars)."""
    salts = [generate_investigation_salt() for _ in range(100)]
    assert len(set(salts)) == 100
    for s in salts:
        assert len(s) == 64
        int(s, 16)  # Valid hex string


def test_hash_format():
    """Verify standard format prefixes for standing and ephemeral hashes."""
    s_hash = generate_standing_hash("1234567890", "SBIN0001234")
    e_hash = generate_ephemeral_hash("1234567890", "bank_sbi", generate_investigation_salt())
    assert s_hash.startswith("HMAC:")
    assert e_hash.startswith("INV:")


def test_key_rotation_grace_period():
    """Verify historical keys resolve standing hashes during rotation grace period."""
    service = HashingService(settings)
    account = "YESB9876543210"
    ifsc = "YESB0001122"

    initial_hash = service.compute_hash(account, ifsc)
    service.rotate_key()

    historical_hashes = service.compute_with_historical_keys(account, ifsc)
    assert initial_hash in historical_hashes


def test_bank_vault_register_and_resolve():
    """Verify bank vault registers and de-anonymizes customer record correctly."""
    vault = BankVault(bank_id="bank_sbi", bank_name="State Bank of India")
    reg = vault.register_account(
        account_number="40991209384",
        ifsc_code="SBIN0001234",
        customer_name="Rajesh Kumar",
        kyc_status="verified",
        declared_income=45000.0,
        account_age_days=120
    )

    resolved = vault.resolve_hash(reg["hash"])
    assert resolved is not None
    assert resolved["customer_name"] == "Rajesh Kumar"
    assert resolved["account_number"] == "40991209384"
    assert resolved["kyc_status"] == "verified"


def test_bank_vault_isolation():
    """Verify Vault A cannot resolve Vault B's account hashes."""
    vault_sbi = BankVault(bank_id="bank_sbi", bank_name="State Bank of India")
    vault_hdfc = BankVault(bank_id="bank_hdfc", bank_name="HDFC Bank")

    sbi_acc = vault_sbi.register_account("SBIN11223344", "SBIN0001234", "Amit Sharma")
    hdfc_acc = vault_hdfc.register_account("HDFC99887766", "HDFC0001234", "Priya Patel")

    # SBI cannot resolve HDFC hash
    assert vault_sbi.resolve_hash(hdfc_acc["hash"]) is None
    # HDFC cannot resolve SBI hash
    assert vault_hdfc.resolve_hash(sbi_acc["hash"]) is None


def test_hmac_collision_freedom():
    """Verify 10,000 unique account/IFSC pairs yield 0 hash collisions."""
    hashes = set()
    for i in range(10000):
        h = generate_standing_hash(f"ACCT_{i:06d}", f"IFSC_{i % 10:04d}")
        hashes.add(h)
    assert len(hashes) == 10000
