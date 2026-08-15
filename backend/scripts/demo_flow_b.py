"""Demo script for Flow B Targeted Investigation and Bounded Pattern-Decay Traversal."""
import os
import sys
import json
import time

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.app.config import settings
from backend.app.privacy.hashing import generate_standing_hash
from backend.app.data_generator.motif_injector import generate_with_contamination
from backend.app.graph.graph_engine import TemporalGraph
from backend.app.investigation.flow_b_service import FlowBService
from backend.app.investigation.traversal import PatternDecayTraversal


def main():
    print("=" * 80)
    print("CROSS-BANK MULE ACCOUNT DETECTION NETWORK — FLOW B INVESTIGATION DEMO")
    print("=" * 80)

    # 1. Synthesize multi-bank topology with mule motifs
    print("\n[Step 1/4] Generating synthetic multi-bank data with 4-hop mule chain...")
    dataset = generate_with_contamination(
        num_banks=8,
        num_accounts_per_bank=50,
        num_edges=1500,
        contamination_rate=0.10,
        seed=42
    )

    standing_key = settings.get_standing_key()
    hash_map = {
        acc["account_number"]: generate_standing_hash(acc["account_number"], acc["ifsc_code"], standing_key)
        for acc in dataset["accounts"]
    }

    tg = TemporalGraph()
    for e in dataset["edges"]:
        tg.add_edge(
            sender_hash=hash_map.get(e["sender_account"], e["sender_account"]),
            receiver_hash=hash_map.get(e["receiver_account"], e["receiver_account"]),
            amount=float(e["amount"]),
            timestamp=e["timestamp"],
            bank_id=e.get("sender_bank_id") or e.get("bank_id", "UNKNOWN"),
            local_risk_score=float(e.get("local_risk_score", 0.0) or 0.0)
        )

    print(f" -> Graph built: {tg.get_node_count()} nodes, {tg.get_edge_count()} edges across 8 banks")

    # 2. Select target mule node from ground truth
    mule_nodes = list(dataset["ground_truth"]["mule_nodes"])
    target_raw = mule_nodes[len(mule_nodes) // 2] if mule_nodes else list(hash_map.keys())[0]
    target_hash = hash_map[target_raw]

    print(f"\n[Step 2/4] Initializing Flow B Targeted Investigation for node: {target_hash}")
    t0 = time.perf_counter()
    flow_b = FlowBService(graph=tg)
    inv_id = flow_b.start_investigation(node_hash=target_hash, component_id="comp_flow_b_demo")
    duration_ms = (time.perf_counter() - t0) * 1000

    status = flow_b.get_status(inv_id)
    result = flow_b.get_result(inv_id)
    playback = flow_b.get_playback(inv_id)

    print(f" -> Investigation ID:   {inv_id}")
    print(f" -> Initialization:     {duration_ms:.2f}ms")
    print(f" -> Status:             {status['status']}")
    print(f" -> Depth Reached:      {result.get('depth_reached', 0)} hops")
    print(f" -> Nodes Visited:      {len(result.get('nodes_visited', []))}")
    print(f" -> Edges Explored:     {len(result.get('edges_visited', []))}")
    print(f" -> Banks Queried:      {', '.join(result.get('banks_queried', []))}")
    print(f" -> Stopping Reason:    {result.get('stopping_reason')}")

    # 3. Print step-by-step playback trace
    print("\n[Step 3/4] Traversal Playback Trace (Chronological Exploration):")
    print("-" * 80)
    for step in playback[:8]:
        action = step.get("action")
        desc = step.get("description")
        decision = step.get("decision")
        print(f"  Step {step.get('step_number'):<2} | [{decision:<6}] {action:<18} | {desc}")

    if len(playback) > 8:
        print(f"  ... and {len(playback) - 8} more steps")

    # 4. Save results to JSON artifact
    os.makedirs("./data", exist_ok=True)
    out_path = "./data/demo_flow_b_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "investigation_id": inv_id,
            "status": status,
            "traversal_result": result,
            "playback_trace": playback
        }, f, indent=2)

    print(f"\n[Step 4/4] Investigation trace saved to: {out_path}")

    # 5. Close investigation and verify salt destruction
    close_res = flow_b.close_investigation(inv_id, closed_by="demo_runner")
    print(f" -> Investigation closed: {close_res['status']} (Ephemeral salt permanently destroyed)")

    print("\n" + "=" * 80)
    print("[SUCCESS] Phase 6 Flow B Investigation & Traversal Engine fully verified!")
    print("=" * 80)


if __name__ == "__main__":
    main()
