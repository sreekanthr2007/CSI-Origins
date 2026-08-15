"""FastAPI API routes for privacy hashing, bank vaults, and synthetic data generation."""
import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.app.config import settings
from backend.app.privacy.hashing import (
    generate_standing_hash,
    generate_ephemeral_hash,
    generate_investigation_salt,
    HashingService,
)
from backend.app.privacy.bank_vault import BankVault
from backend.app.data_generator.synthetic_banks import (
    generate_banks,
    generate_accounts,
    BANK_METADATA,
)
from backend.app.data_generator.motif_injector import (
    MotifInjector,
    generate_with_contamination,
)

logger = logging.getLogger("mule-detection-api")

router = APIRouter()
hashing_service = HashingService(settings)

# In-memory bank vaults for simulation (one per bank)
BANK_VAULTS: Dict[str, BankVault] = {
    b["id"]: BankVault(bank_id=b["id"], bank_name=b["name"])
    for b in BANK_METADATA
}


# ---------------------------------------------------------------------------
# Pydantic Request / Response Models
# ---------------------------------------------------------------------------
class StandingHashRequest(BaseModel):
    account_number: str = Field(..., example="SBIN1234567890")
    ifsc_code: str = Field(..., example="SBIN0001234")


class StandingHashResponse(BaseModel):
    hash: str = Field(..., example="HMAC:8f9a7b3c1d2e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a")


class EphemeralHashRequest(BaseModel):
    account_number: str = Field(..., example="SBIN1234567890")
    bank_id: str = Field(..., example="bank_sbi")
    salt: str = Field(..., example="a1b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef0")


class EphemeralHashResponse(BaseModel):
    hash: str = Field(..., example="INV:7b3c1d2e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0123")


class SaltGenerateResponse(BaseModel):
    salt: str


class KeyRotationResponse(BaseModel):
    status: str = "rotated"
    new_fingerprint: str


class VaultRegisterRequest(BaseModel):
    bank_id: str
    accounts: List[Dict[str, Any]]


class VaultResolveRequest(BaseModel):
    hash: str
    bank_id: Optional[str] = None


class GenerateTransactionsRequest(BaseModel):
    num_banks: Optional[int] = 10
    num_accounts_per_bank: Optional[int] = 100
    num_edges: Optional[int] = 5000
    contamination_rate: Optional[float] = 0.10
    seed: Optional[int] = 42


class GenerateMotifRequest(BaseModel):
    motif_type: str = Field(..., example="chain")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Health & Status
# ---------------------------------------------------------------------------
@router.get("/health", tags=["Health"])
def health_endpoint():
    """Service health check."""
    return {"status": "ok", "version": "1.0.0"}


@router.get("/banks", tags=["Banks"])
def list_banks():
    """Return participating Indian banks."""
    return generate_banks()


@router.get("/status", tags=["Status"])
def system_status():
    """Return platform cryptographic and runtime status."""
    return {
        "status": "OPERATIONAL",
        "flow_a_active": True,
        "flow_b_ready": True,
        "standing_key_fingerprint": hashing_service.get_current_key_fingerprint(),
        "registered_banks_count": len(BANK_VAULTS),
        "total_vault_accounts": sum(v.total_accounts for v in BANK_VAULTS.values())
    }


# ---------------------------------------------------------------------------
# Privacy Endpoints
# ---------------------------------------------------------------------------
@router.post("/privacy/hash", response_model=StandingHashResponse, tags=["Privacy"])
def create_standing_hash(req: StandingHashRequest):
    """Compute standing HMAC-SHA256 hash for Flow A."""
    if not req.account_number.strip() or not req.ifsc_code.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="account_number and ifsc_code are required")
    hash_val = hashing_service.compute_hash(req.account_number, req.ifsc_code)
    return StandingHashResponse(hash=hash_val)


@router.post("/privacy/hash/ephemeral", response_model=EphemeralHashResponse, tags=["Privacy"])
def create_ephemeral_hash(req: EphemeralHashRequest):
    """Compute ephemeral investigation HMAC-SHA256 hash for Flow B."""
    if not req.account_number.strip() or not req.bank_id.strip() or not req.salt.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="account_number, bank_id, and salt are required")
    hash_val = generate_ephemeral_hash(req.account_number, req.bank_id, req.salt)
    return EphemeralHashResponse(hash=hash_val)


@router.post("/privacy/salt/generate", response_model=SaltGenerateResponse, tags=["Privacy"])
def create_salt():
    """Generate 32-byte cryptographically secure investigation salt."""
    salt_val = generate_investigation_salt()
    return SaltGenerateResponse(salt=salt_val)


@router.post("/privacy/key/rotate", response_model=KeyRotationResponse, tags=["Privacy"])
def rotate_key():
    """Rotate standing HMAC registry key (admin only)."""
    fingerprint = hashing_service.rotate_key()
    return KeyRotationResponse(status="rotated", new_fingerprint=fingerprint)


# ---------------------------------------------------------------------------
# Bank Vault Endpoints (Development / Demo Simulation)
# ---------------------------------------------------------------------------
@router.post("/vault/register", tags=["Bank Vault"])
def register_vault_accounts(req: VaultRegisterRequest):
    """Register customer identities inside a bank's private vault."""
    vault = BANK_VAULTS.get(req.bank_id)
    if not vault:
        vault = BankVault(bank_id=req.bank_id, bank_name=req.bank_id)
        BANK_VAULTS[req.bank_id] = vault

    count = vault.register_accounts(req.accounts)
    return {"registered": count, "bank_id": req.bank_id}


@router.post("/vault/resolve", tags=["Bank Vault"])
def resolve_vault_hash(req: VaultResolveRequest):
    """Attempt de-anonymization of a hash inside bank's private vault."""
    if req.bank_id and req.bank_id in BANK_VAULTS:
        account = BANK_VAULTS[req.bank_id].resolve_hash(req.hash)
        if not account:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hash not found in specified bank vault")
        return account

    # Search across vaults for simulation demo
    for vault in BANK_VAULTS.values():
        account = vault.resolve_hash(req.hash)
        if account:
            return account

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hash not found in any participating bank vault")


# ---------------------------------------------------------------------------
# Synthetic Data Generation Endpoints
# ---------------------------------------------------------------------------
@router.post("/generate/banks", tags=["Data Generator"])
def generate_synthetic_banks_endpoint():
    """Generate Indian bank profiles and accounts."""
    banks = generate_banks()
    all_accounts = []
    for b in banks:
        accs = generate_accounts(b, count=settings.NUM_ACCOUNTS_PER_BANK)
        all_accounts.extend(accs)
        # Register in vault for resolution
        if b["id"] in BANK_VAULTS:
            BANK_VAULTS[b["id"]].register_accounts(accs)
    return {"banks": banks, "accounts_count": len(all_accounts), "accounts": all_accounts}


@router.post("/generate/transactions", tags=["Data Generator"])
def generate_transactions_endpoint(req: GenerateTransactionsRequest):
    """Generate full dataset with Erdős-Rényi transactions and injected mule motifs."""
    dataset = generate_with_contamination(
        num_banks=req.num_banks or 10,
        num_accounts_per_bank=req.num_accounts_per_bank or 100,
        num_edges=req.num_edges or 5000,
        contamination_rate=req.contamination_rate or 0.10,
        seed=req.seed or 42
    )

    # Register generated accounts in bank vaults
    for acc in dataset["accounts"]:
        b_id = acc["bank_id"]
        if b_id in BANK_VAULTS:
            BANK_VAULTS[b_id].register_account(
                account_number=acc["account_number"],
                ifsc_code=acc["ifsc_code"],
                customer_name=acc.get("customer_name", "Demo User"),
                kyc_status=acc.get("kyc_status", "verified"),
                declared_income=acc.get("declared_income", 30000.0)
            )

    return {
        "banks_count": len(dataset["banks"]),
        "accounts_count": len(dataset["accounts"]),
        "edges_count": len(dataset["edges"]),
        "motifs_count": len(dataset["motifs"]),
        "ground_truth": dataset["ground_truth"],
        "edges_sample": dataset["edges"][:50]
    }


@router.post("/generate/motif", tags=["Data Generator"])
def generate_single_motif(req: GenerateMotifRequest):
    """Inject a single specified motif (chain, collector, distributor)."""
    banks = generate_banks()
    accounts_by_bank = {b["id"]: generate_accounts(b, count=30) for b in banks}
    
    injector = MotifInjector()
    motif = injector.inject_motif(accounts_by_bank, req.motif_type, req.params)
    return {"motif": motif, "nodes": motif.get("nodes") or motif.get("senders") or motif.get("receivers")}


@router.post("/reset", tags=["Admin"])
def reset_simulation():
    """Reset all in-memory vaults and simulation state."""
    for v in BANK_VAULTS.values():
        v._local_accounts.clear()
        v._resolution_log.clear()
    return {"status": "reset complete", "vaults_cleared": len(BANK_VAULTS)}
