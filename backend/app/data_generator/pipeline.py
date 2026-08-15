"""Data Generation Pipeline for synthetic multi-bank data and mule motif injection."""
import pandas as pd
from typing import Dict, Any, Optional
from backend.app.data_generator.motif_injector import generate_with_contamination


class DataGenerationPipeline:
    """End-to-end multi-bank synthetic transaction pipeline."""

    def __init__(self, num_banks: int = 4, accounts_per_bank: int = 50, contamination_rate: float = 0.15, seed: int = 42):
        self.num_banks = num_banks
        self.accounts_per_bank = accounts_per_bank
        self.contamination_rate = contamination_rate
        self.seed = seed

    def generate(self) -> pd.DataFrame:
        """Generates synthetic multi-bank transactions and returns a Pandas DataFrame."""
        from backend.app.config import settings
        from backend.app.privacy.hashing import generate_standing_hash

        result = generate_with_contamination(
            num_banks=self.num_banks,
            num_accounts_per_bank=self.accounts_per_bank,
            contamination_rate=self.contamination_rate,
            seed=self.seed
        )
        edge_list = result.get("edges", [])
        standing_key = settings.get_standing_key()

        enriched = []
        for i, e in enumerate(edge_list):
            item = dict(e)
            s_acc = e.get("sender_account", f"ACC_S_{i}")
            r_acc = e.get("receiver_account", f"ACC_R_{i}")
            s_bank = e.get("sender_bank_id", "bank_sbi")
            r_bank = e.get("receiver_bank_id", "bank_hdfc")
            item.setdefault("sender_hash", generate_standing_hash(s_acc, "SBIN0001000", standing_key))
            item.setdefault("receiver_hash", generate_standing_hash(r_acc, "HDFC0001000", standing_key))
            item.setdefault("bank_id", s_bank)
            item.setdefault("transaction_id", f"tx_{i:06d}")
            item.setdefault("local_risk_score", 0.85 if e.get("is_mule_edge") else 0.1)
            enriched.append(item)

        return pd.DataFrame(enriched)


