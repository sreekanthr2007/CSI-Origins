"""Standalone script to execute end-to-end graph construction, feature extraction, and component analysis."""
import sys
import os
import time
import logging

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.app.config import settings
from backend.app.data_generator.motif_injector import generate_with_contamination
from backend.app.graph.graph_engine import TemporalGraph, GraphEngine
from backend.app.features.feature_extractor import FeatureExtractor
from backend.app.features.component_detector import ComponentDetector

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")
logger = logging.getLogger("graph-analysis")


def main():
    print("=" * 70)
    print("CROSS-BANK MULE ACCOUNT DETECTION NETWORK — GRAPH ANALYSIS PIPELINE")
    print("=" * 70)

    # 1. Generate synthetic transactions with mule motifs
    print("\n[Step 1/4] Generating synthetic multi-bank transaction data...")
    t0 = time.time()
    dataset = generate_with_contamination(
        num_banks=8,
        num_accounts_per_bank=50,
        num_edges=2500,
        contamination_rate=0.12,
        seed=42
    )
    gen_time = time.time() - t0
    edges = dataset["edges"]
    motif_types = [m.get("motif_type", m.get("type", "motif")) for m in dataset.get("motifs", [])]
    print(f" -> Generated {len(dataset['banks'])} banks, {len(dataset['accounts'])} accounts, {len(edges)} transaction edges in {gen_time:.2f}s")
    print(f" -> Injected Motifs: {len(dataset['motifs'])} ({motif_types})")


    # 2. Build Temporal Graph
    print("\n[Step 2/4] Ingesting edges into TemporalGraph Engine...")
    t1 = time.time()
    tg = TemporalGraph(config=settings)
    ingested_count = tg.add_edges_batch(edges)
    build_time = time.time() - t1
    stats = tg.get_graph_stats()
    print(f" -> Ingested {ingested_count} edges into graph in {build_time:.3f}s")
    print(f" -> Graph Topology: {stats['node_count']} nodes, {stats['edge_count']} edges, Avg Degree: {stats['avg_degree']}, Density: {stats['density']}")

    # 3. Detect Connected Components and Calculate Risk Scores
    print("\n[Step 3/4] Running ComponentDetector & Mule Subgraph Risk Scoring...")
    t2 = time.time()
    detector = ComponentDetector(graph=tg, config=settings)
    components = detector.get_components_with_risk(min_size=2)
    comp_time = time.time() - t2
    print(f" -> Detected {len(components)} connected components in {comp_time:.3f}s")

    # 4. Extract Feature Vectors across Nodes
    print("\n[Step 4/4] Extracting topological and behavioral feature vectors...")
    t3 = time.time()
    extractor = FeatureExtractor(graph=tg, config=settings)
    nodes = tg.get_nodes()
    df_features = extractor.extract_features_batch(nodes)
    feat_time = time.time() - t3
    print(f" -> Extracted {len(extractor.get_feature_names())} features across {len(nodes)} nodes in {feat_time:.3f}s")

    # Calculate summary metrics
    sizes = [c["size"] for c in components] if components else [0]
    avg_size = sum(sizes) / len(sizes) if sizes else 0.0
    highest_risk_comp = components[0] if components else None
    
    high_pt_count = (df_features["pass_through_ratio"] >= 0.8).sum() if "pass_through_ratio" in df_features.columns else 0
    avg_chain_len = df_features["total_path_length"].mean() if "total_path_length" in df_features.columns else 0.0

    print("\n" + "=" * 70)
    print("GRAPH ANALYTICS & FEATURE EXTRACTION SUMMARY")
    print("=" * 70)
    print(f"  * Total Graph Nodes:               {stats['node_count']:,}")
    print(f"  * Total Graph Edges:               {stats['edge_count']:,}")
    print(f"  * Participating Banks:             {len(stats['edges_by_bank'])}")
    print(f"  * Total Connected Components:      {len(components)}")
    print(f"  * Average Component Size:          {avg_size:.2f} nodes")
    print(f"  * High Pass-Through Nodes (>=0.8): {high_pt_count}")
    print(f"  * Average Chain Length:            {avg_chain_len:.2f}")
    
    if highest_risk_comp:
        print("\n  [HIGHEST RISK COMPONENT]")
        print(f"    - Risk Score:        {highest_risk_comp['risk_score']:.4f}")
        print(f"    - Component Size:    {highest_risk_comp['size']} nodes")
        print(f"    - Banks Involved:    {', '.join(highest_risk_comp['banks'])}")
        print(f"    - Total Flow Volume: INR {highest_risk_comp['total_volume']:,.2f}")
        print(f"    - Avg Pass-Through:  {highest_risk_comp['avg_pass_through']:.4f}")
        print(f"    - Max Chain Length:  {highest_risk_comp['max_chain_length']}")
    
    print("\n[SUCCESS] Phase 4 Graph Engine & Feature Extraction pipeline operational!")
    print("=" * 70)


if __name__ == "__main__":
    main()
