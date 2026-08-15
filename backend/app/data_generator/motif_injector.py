"""Mule motif injector for synthesizing labeled fraud rings (Chains, Collectors, Distributors)."""
import random
import datetime
from typing import Dict, Any, List, Tuple, Optional
import networkx as nx
from backend.app.data_generator.synthetic_banks import (
    generate_banks,
    generate_accounts,
    generate_transactions
)


def _format_iso(dt: datetime.datetime) -> str:
    """Format datetime as UTC ISO-8601 string."""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class MotifInjector:
    """Injects structured mule motifs into graph topologies with ground-truth labels."""

    def __init__(self, contamination_rate: float = 0.10, seed: int = 42):
        self.contamination_rate = contamination_rate
        self.seed = seed
        random.seed(seed)

    def inject_chain_motif(
        self,
        accounts_by_bank: Dict[str, List[Dict[str, Any]]],
        num_hops: int = 4,
        initial_amount: float = 500000.0,
        speed: str = "fast",
        base_time: Optional[datetime.datetime] = None
    ) -> Dict[str, Any]:
        """
        Inject a multi-bank rapid laundering chain: A -> B -> C -> D -> ...
        Pass-through ratio: 90% - 98% per hop.
        """
        now = base_time or datetime.datetime.now(datetime.timezone.utc)
        available_banks = list(accounts_by_bank.keys())
        if len(available_banks) < 2:
            raise ValueError("Need at least 2 banks to form a cross-bank chain")

        # Pick distinct banks for consecutive hops
        chain_banks = random.sample(available_banks, min(num_hops + 1, len(available_banks)))
        while len(chain_banks) < num_hops + 1:
            chain_banks.append(random.choice(available_banks))

        nodes: List[Dict[str, Any]] = []
        for b_id in chain_banks:
            acc = random.choice(accounts_by_bank[b_id])
            nodes.append(acc)

        edges: List[Dict[str, Any]] = []
        current_amount = float(initial_amount)
        current_time = now - datetime.timedelta(hours=random.randint(1, 48))

        for i in range(num_hops):
            sender = nodes[i]
            receiver = nodes[i + 1]
            
            # 5-30 mins for fast, 1-4 hours for medium
            if speed == "fast":
                delta_minutes = random.randint(5, 30)
            else:
                delta_minutes = random.randint(60, 240)

            current_time += datetime.timedelta(minutes=delta_minutes)
            
            # 90% - 98% pass-through
            pass_through = random.uniform(0.92, 0.98)
            current_amount = round(current_amount * pass_through, 2)

            edges.append({
                "sender_account": sender["account_number"],
                "sender_ifsc": sender["ifsc_code"],
                "receiver_account": receiver["account_number"],
                "receiver_ifsc": receiver["ifsc_code"],
                "sender_bank_id": sender["bank_id"],
                "receiver_bank_id": receiver["bank_id"],
                "amount": current_amount,
                "timestamp": _format_iso(current_time),
                "is_interbank": sender["bank_id"] != receiver["bank_id"],
                "local_risk_score": round(random.uniform(0.65, 0.95), 4),
                "is_mule_edge": True,
                "motif_type": "chain"
            })

        return {
            "motif_type": "chain",
            "num_hops": num_hops,
            "nodes": [n["account_number"] for n in nodes],
            "edges": edges,
            "start_amount": initial_amount,
            "end_amount": current_amount
        }

    def inject_collector_star(
        self,
        accounts_by_bank: Dict[str, List[Dict[str, Any]]],
        num_senders: int = 8,
        amount_per_sender: float = 50000.0,
        base_time: Optional[datetime.datetime] = None
    ) -> Dict[str, Any]:
        """
        Inject collector star: multiple compromised senders funnel into 1 collector.
        All transfers occur within a narrow 2-hour window.
        """
        now = base_time or datetime.datetime.now(datetime.timezone.utc)
        all_accounts = [acc for bank_accs in accounts_by_bank.values() for acc in bank_accs]
        if len(all_accounts) < num_senders + 1:
            raise ValueError("Insufficient accounts to inject collector star")

        collector = random.choice(all_accounts)
        available_senders = [a for a in all_accounts if a["account_number"] != collector["account_number"]]
        senders = random.sample(available_senders, num_senders)

        edges: List[Dict[str, Any]] = []
        cluster_start = now - datetime.timedelta(hours=random.randint(2, 24))

        for sender in senders:
            delta_mins = random.randint(2, 110)
            tx_time = cluster_start + datetime.timedelta(minutes=delta_mins)
            jittered_amount = round(amount_per_sender * random.uniform(0.95, 1.05), 2)

            edges.append({
                "sender_account": sender["account_number"],
                "sender_ifsc": sender["ifsc_code"],
                "receiver_account": collector["account_number"],
                "receiver_ifsc": collector["ifsc_code"],
                "sender_bank_id": sender["bank_id"],
                "receiver_bank_id": collector["bank_id"],
                "amount": jittered_amount,
                "timestamp": _format_iso(tx_time),
                "is_interbank": sender["bank_id"] != collector["bank_id"],
                "local_risk_score": round(random.uniform(0.70, 0.96), 4),
                "is_mule_edge": True,
                "motif_type": "collector_star"
            })

        return {
            "motif_type": "collector_star",
            "collector": collector["account_number"],
            "senders": [s["account_number"] for s in senders],
            "edges": edges,
            "total_funneled": sum(e["amount"] for e in edges)
        }

    def inject_distributor_star(
        self,
        accounts_by_bank: Dict[str, List[Dict[str, Any]]],
        num_receivers: int = 10,
        amount_per_receiver: float = 49500.0,
        base_time: Optional[datetime.datetime] = None
    ) -> Dict[str, Any]:
        """
        Inject distributor star (smurfing/structuring): 1 hub disperses structured funds
        just under the ₹50,000 reporting threshold to multiple fan-out accounts.
        """
        now = base_time or datetime.datetime.now(datetime.timezone.utc)
        all_accounts = [acc for bank_accs in accounts_by_bank.values() for acc in bank_accs]
        if len(all_accounts) < num_receivers + 1:
            raise ValueError("Insufficient accounts to inject distributor star")

        distributor = random.choice(all_accounts)
        available_receivers = [a for a in all_accounts if a["account_number"] != distributor["account_number"]]
        receivers = random.sample(available_receivers, num_receivers)

        edges: List[Dict[str, Any]] = []
        cluster_start = now - datetime.timedelta(hours=random.randint(1, 36))

        for receiver in receivers:
            delta_mins = random.randint(5, 120)
            tx_time = cluster_start + datetime.timedelta(minutes=delta_mins)
            # Structuring just under ₹50,000 (e.g. ₹48,000 - ₹49,900)
            structured_amount = round(random.uniform(48000.0, 49850.0), 2)

            edges.append({
                "sender_account": distributor["account_number"],
                "sender_ifsc": distributor["ifsc_code"],
                "receiver_account": receiver["account_number"],
                "receiver_ifsc": receiver["ifsc_code"],
                "sender_bank_id": distributor["bank_id"],
                "receiver_bank_id": receiver["bank_id"],
                "amount": structured_amount,
                "timestamp": _format_iso(tx_time),
                "is_interbank": distributor["bank_id"] != receiver["bank_id"],
                "local_risk_score": round(random.uniform(0.75, 0.98), 4),
                "is_mule_edge": True,
                "motif_type": "distributor_star"
            })

        return {
            "motif_type": "distributor_star",
            "distributor": distributor["account_number"],
            "receivers": [r["account_number"] for r in receivers],
            "edges": edges,
            "total_dispersed": sum(e["amount"] for e in edges)
        }

    def inject_motif(
        self,
        accounts_by_bank: Dict[str, List[Dict[str, Any]]],
        motif_type: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Dispatch motif injection by type string."""
        p = params or {}
        if motif_type in ("chain", "rapid_chain"):
            return self.inject_chain_motif(
                accounts_by_bank,
                num_hops=p.get("hops", 4),
                initial_amount=p.get("amount", 500000.0),
                speed=p.get("speed", "fast")
            )
        elif motif_type in ("collector", "collector_star"):
            return self.inject_collector_star(
                accounts_by_bank,
                num_senders=p.get("senders", 8),
                amount_per_sender=p.get("amount", 50000.0)
            )
        elif motif_type in ("distributor", "distributor_star", "smurfing"):
            return self.inject_distributor_star(
                accounts_by_bank,
                num_receivers=p.get("receivers", 10),
                amount_per_receiver=p.get("amount", 49500.0)
            )
        else:
            raise ValueError(f"Unknown motif type: {motif_type}")


def generate_with_contamination(
    num_banks: int = 10,
    num_accounts_per_bank: int = 100,
    num_edges: int = 5000,
    contamination_rate: float = 0.10,
    seed: int = 42
) -> Dict[str, Any]:
    """
    Generate a full synthetic dataset with base Erdős-Rényi transactions and injected mule motifs
    reaching the target contamination rate.
    """
    random.seed(seed)
    banks = generate_banks(num_banks)
    
    all_accounts: List[Dict[str, Any]] = []
    accounts_by_bank: Dict[str, List[Dict[str, Any]]] = {}

    for bank in banks:
        accs = generate_accounts(bank, count=num_accounts_per_bank, seed=seed)
        all_accounts.extend(accs)
        accounts_by_bank[bank["id"]] = accs

    # Generate baseline normal edges
    normal_edges_count = int(num_edges * (1.0 - contamination_rate))
    base_transactions = generate_transactions(all_accounts, num_edges=normal_edges_count, seed=seed)

    # Inject mule motifs
    injector = MotifInjector(contamination_rate=contamination_rate, seed=seed)
    target_mule_edges = int(num_edges * contamination_rate)
    
    injected_motifs: List[Dict[str, Any]] = []
    mule_edges: List[Dict[str, Any]] = []
    ground_truth_mule_nodes: set = set()

    while len(mule_edges) < target_mule_edges:
        motif_choice = random.choice(["chain", "collector_star", "distributor_star"])
        if motif_choice == "chain":
            motif = injector.inject_chain_motif(accounts_by_bank, num_hops=random.randint(3, 6))
            ground_truth_mule_nodes.update(motif["nodes"])
        elif motif_choice == "collector_star":
            motif = injector.inject_collector_star(accounts_by_bank, num_senders=random.randint(5, 8))
            ground_truth_mule_nodes.add(motif["collector"])
            ground_truth_mule_nodes.update(motif["senders"])
        else:
            motif = injector.inject_distributor_star(accounts_by_bank, num_receivers=random.randint(6, 10))
            ground_truth_mule_nodes.add(motif["distributor"])
            ground_truth_mule_nodes.update(motif["receivers"])

        injected_motifs.append(motif)
        mule_edges.extend(motif["edges"])

    all_edges = base_transactions + mule_edges
    all_edges.sort(key=lambda x: x["timestamp"])

    actual_contamination = round(len(mule_edges) / max(len(all_edges), 1), 4)

    # Build NetworkX graph representation
    g = nx.MultiDiGraph()
    for acc in all_accounts:
        is_mule = acc["account_number"] in ground_truth_mule_nodes
        g.add_node(acc["account_number"], **acc, is_mule=is_mule)

    for edge in all_edges:
        g.add_edge(edge["sender_account"], edge["receiver_account"], **edge)

    return {
        "banks": banks,
        "accounts": all_accounts,
        "edges": all_edges,
        "motifs": injected_motifs,
        "ground_truth": {
            "mule_node_count": len(ground_truth_mule_nodes),
            "mule_nodes": list(ground_truth_mule_nodes),
            "mule_edge_count": len(mule_edges),
            "total_edges": len(all_edges),
            "actual_contamination_rate": actual_contamination
        },
        "graph": g
    }


def verify_motif_injection(dataset: Dict[str, Any]) -> bool:
    """Verify structural validity and ground-truth labeling of generated dataset."""
    gt = dataset.get("ground_truth", {})
    edges = dataset.get("edges", [])
    mule_edges = [e for e in edges if e.get("is_mule_edge")]
    return len(mule_edges) == gt.get("mule_edge_count", 0) and len(edges) > 0
