"""Synthetic Data Generator Package."""
from backend.app.data_generator.synthetic_banks import (
    BankMetadata,
    Account,
    Transaction,
    generate_banks,
    generate_accounts,
    generate_transactions,
    BANK_METADATA,
)
from backend.app.data_generator.motif_injector import (
    MotifInjector,
    generate_with_contamination,
    verify_motif_injection,
)

# Alias for backwards compatibility / alternate naming
generate_transactions_with_motifs = generate_with_contamination

__all__ = [
    "BankMetadata",
    "Account",
    "Transaction",
    "generate_banks",
    "generate_accounts",
    "generate_transactions",
    "generate_transactions_with_motifs",
    "generate_with_contamination",
    "MotifInjector",
    "verify_motif_injection",
    "BANK_METADATA",
]
