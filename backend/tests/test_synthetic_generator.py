"""Unit tests for multi-bank synthetic transaction generator and mule motif injector."""
import datetime
import pytest
from backend.app.data_generator.synthetic_banks import (
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


def test_bank_generation():
    """Verify correct number of banks generated with required metadata fields."""
    banks = generate_banks(10)
    assert len(banks) == 10
    for b in banks:
        assert "id" in b
        assert "name" in b
        assert "ifsc_prefix" in b


def test_account_generation():
    """Verify generated accounts have valid IFSC prefixes, customer details, and income."""
    bank = BANK_METADATA[0]  # SBI
    accounts = generate_accounts(bank, count=50, seed=123)
    assert len(accounts) == 50
    for acc in accounts:
        assert acc["ifsc_code"].startswith("SBIN0")
        assert len(acc["account_number"]) >= 11
        assert acc["kyc_status"] in ("verified", "pending")
        assert acc["declared_income"] >= 15000.0


def test_transaction_generation():
    """Verify edge count matches requested count."""
    banks = generate_banks(5)
    accounts = []
    for b in banks:
        accounts.extend(generate_accounts(b, count=20, seed=42))

    txs = generate_transactions(accounts, num_edges=200, seed=42)
    assert len(txs) == 200
    for tx in txs:
        assert tx["amount"] > 0
        assert tx["timestamp"] is not None


def test_interbank_constraint():
    """Verify 100% of generated transactions are inter-bank (different institutions)."""
    banks = generate_banks(5)
    accounts = []
    for b in banks:
        accounts.extend(generate_accounts(b, count=20, seed=42))

    txs = generate_transactions(accounts, num_edges=500, seed=42)
    for tx in txs:
        assert tx["sender_bank_id"] != tx["receiver_bank_id"]
        assert tx["is_interbank"] is True


def test_chain_motif_injection():
    """Verify chain of correct length and pass-through characteristics."""
    banks = generate_banks(5)
    accounts_by_bank = {b["id"]: generate_accounts(b, count=15, seed=42) for b in banks}

    injector = MotifInjector(seed=42)
    chain = injector.inject_chain_motif(accounts_by_bank, num_hops=4, initial_amount=500000.0, speed="fast")

    assert chain["motif_type"] == "chain"
    assert chain["num_hops"] == 4
    assert len(chain["edges"]) == 4
    assert len(chain["nodes"]) == 5
    for e in chain["edges"]:
        assert e["is_mule_edge"] is True
        assert e["local_risk_score"] > 0.50


def test_collector_star_injection():
    """Verify collector star structure with correct fan-in count."""
    banks = generate_banks(5)
    accounts_by_bank = {b["id"]: generate_accounts(b, count=15, seed=42) for b in banks}

    injector = MotifInjector(seed=42)
    star = injector.inject_collector_star(accounts_by_bank, num_senders=6, amount_per_sender=40000.0)

    assert star["motif_type"] == "collector_star"
    assert len(star["senders"]) == 6
    assert len(star["edges"]) == 6
    for e in star["edges"]:
        assert e["receiver_account"] == star["collector"]
        assert e["is_mule_edge"] is True


def test_distributor_star_injection():
    """Verify distributor star structure with structured amounts."""
    banks = generate_banks(5)
    accounts_by_bank = {b["id"]: generate_accounts(b, count=15, seed=42) for b in banks}

    injector = MotifInjector(seed=42)
    star = injector.inject_distributor_star(accounts_by_bank, num_receivers=8, amount_per_receiver=49500.0)

    assert star["motif_type"] == "distributor_star"
    assert len(star["receivers"]) == 8
    assert len(star["edges"]) == 8
    for e in star["edges"]:
        assert e["sender_account"] == star["distributor"]
        assert 45000.0 <= e["amount"] <= 50000.0  # Structuring range
        assert e["is_mule_edge"] is True


def test_contamination_rate():
    """Verify actual contamination rate is within tolerance of target ~10%."""
    dataset = generate_with_contamination(
        num_banks=5,
        num_accounts_per_bank=30,
        num_edges=1000,
        contamination_rate=0.10,
        seed=42
    )

    actual_rate = dataset["ground_truth"]["actual_contamination_rate"]
    assert 0.08 <= actual_rate <= 0.15
    assert verify_motif_injection(dataset) is True


def test_ground_truth_labels():
    """Verify all injected nodes and edges have ground-truth metadata."""
    dataset = generate_with_contamination(
        num_banks=5,
        num_accounts_per_bank=30,
        num_edges=500,
        contamination_rate=0.10,
        seed=42
    )

    mule_nodes = set(dataset["ground_truth"]["mule_nodes"])
    assert len(mule_nodes) > 0

    graph = dataset["graph"]
    for n in mule_nodes:
        assert graph.nodes[n]["is_mule"] is True


def test_temporal_distribution():
    """Verify generated timestamps fall within expected 30-day window."""
    banks = generate_banks(3)
    accounts = []
    for b in banks:
        accounts.extend(generate_accounts(b, count=10, seed=42))

    txs = generate_transactions(accounts, num_edges=100, seed=42)
    now = datetime.datetime.now(datetime.timezone.utc)
    oldest_allowed = now - datetime.timedelta(days=35)

    for tx in txs:
        t = datetime.datetime.fromisoformat(tx["timestamp"].replace("Z", "+00:00"))
        assert oldest_allowed <= t <= now + datetime.timedelta(minutes=5)
