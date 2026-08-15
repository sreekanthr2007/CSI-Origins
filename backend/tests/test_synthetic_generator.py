"""Unit tests for synthetic bank data generation and motif injection."""
import pytest
from backend.app.data_generator.synthetic_banks import get_registered_banks
from backend.app.data_generator.motif_injector import MotifInjector


def test_registered_banks_count():
    banks = get_registered_banks()
    assert len(banks) >= 5
    assert any(b["bank_id"] == "SBI" for b in banks)


def test_motif_injector_instantiation():
    injector = MotifInjector(contamination_rate=0.10)
    data = injector.generate_synthetic_dataset(num_nodes=50, num_edges=100)
    assert "metadata" in data
    assert data["metadata"]["contamination_rate"] == 0.10
