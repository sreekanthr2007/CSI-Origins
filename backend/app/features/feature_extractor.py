"""Structural and behavioral feature extraction pipeline for Cross-Bank Mule Account Detection."""
import logging
import datetime
from typing import Dict, Any, List, Optional, Union, Set
import networkx as nx
import numpy as np
import pandas as pd

from backend.app.config import settings, Settings
from backend.app.graph.graph_engine import TemporalGraph

logger = logging.getLogger("mule-detection-features")


def _parse_ts(val: Union[str, datetime.datetime]) -> datetime.datetime:
    """Parse string or datetime into UTC datetime object."""
    if isinstance(val, datetime.datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=datetime.timezone.utc)
        return val
    try:
        dt = datetime.datetime.fromisoformat(str(val).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=datetime.timezone.utc)
        return dt
    except Exception:
        return datetime.datetime.now(datetime.timezone.utc)


class FeatureExtractor:
    """Extracts topological, temporal, behavioral, and component-level features from the transaction graph."""

    def __init__(
        self,
        graph: Optional[Union[TemporalGraph, nx.MultiDiGraph, nx.DiGraph]] = None,
        config: Optional[Settings] = None
    ):
        if isinstance(graph, TemporalGraph):
            self.temporal_graph = graph
            self.nx_graph: nx.MultiDiGraph = graph.graph
        elif isinstance(graph, (nx.MultiDiGraph, nx.DiGraph)):
            self.temporal_graph = None
            self.nx_graph = graph
        elif graph is None:
            self.temporal_graph = None
            self.nx_graph = nx.MultiDiGraph()
        else:
            raise ValueError(f"Unsupported graph type: {type(graph)}")
        self.config = config or settings

    def extract_features(
        self,
        subgraph: Optional[Union[nx.MultiDiGraph, nx.DiGraph, List[str]]] = None,
        temporal_graph: Optional[TemporalGraph] = None
    ) -> Dict[str, float]:
        """Extract component/subgraph-level feature dictionary."""
        tg = temporal_graph or self.temporal_graph
        if subgraph is not None:
            if isinstance(subgraph, (nx.MultiDiGraph, nx.DiGraph)):
                nodes = list(subgraph.nodes())
                extractor = FeatureExtractor(graph=subgraph, config=self.config)
                return extractor.extract_component_features(nodes)
            elif isinstance(subgraph, list):
                extractor = FeatureExtractor(graph=tg or self.nx_graph, config=self.config)
                return extractor.extract_component_features(subgraph)
        return self.extract_component_features(list(self.nx_graph.nodes()))


    def _get_in_edges(self, node_hash: str) -> List[Dict[str, Any]]:
        if self.temporal_graph:
            return self.temporal_graph.get_in_edges(node_hash)
        if not self.nx_graph.has_node(node_hash):
            return []
        edges = []
        for u, v, k, d in self.nx_graph.in_edges(node_hash, keys=True, data=True):
            ed = dict(d)
            ed.setdefault("sender_hash", u)
            ed.setdefault("receiver_hash", v)
            ed["edge_key"] = k
            edges.append(ed)
        return edges

    def _get_out_edges(self, node_hash: str) -> List[Dict[str, Any]]:
        if self.temporal_graph:
            return self.temporal_graph.get_out_edges(node_hash)
        if not self.nx_graph.has_node(node_hash):
            return []
        edges = []
        for u, v, k, d in self.nx_graph.out_edges(node_hash, keys=True, data=True):
            ed = dict(d)
            ed.setdefault("sender_hash", u)
            ed.setdefault("receiver_hash", v)
            ed["edge_key"] = k
            edges.append(ed)
        return edges

    def _calculate_pass_through(self, node_hash: str, window_hours: Optional[int] = None) -> float:
        """Calculate pass-through ratio: amount_sent_within_window / amount_received_within_window."""
        hours = window_hours or self.config.PASS_THROUGH_WINDOW_HOURS
        window_delta = datetime.timedelta(hours=hours)

        in_edges = self._get_in_edges(node_hash)
        out_edges = self._get_out_edges(node_hash)

        if not in_edges or not out_edges:
            return 0.0

        total_received = sum(float(e.get("amount", 0.0)) for e in in_edges)
        if total_received <= 0.0:
            return 0.0

        # Sort edges chronologically
        in_sorted = sorted(in_edges, key=lambda e: _parse_ts(e.get("timestamp", "")))
        out_sorted = sorted(out_edges, key=lambda e: _parse_ts(e.get("timestamp", "")))

        sent_within_window = 0.0
        # For each incoming deposit, match outgoing transfers occurring within window
        first_in_time = _parse_ts(in_sorted[0].get("timestamp", ""))
        last_in_time = _parse_ts(in_sorted[-1].get("timestamp", ""))
        window_end = last_in_time + window_delta

        for e in out_sorted:
            ts = _parse_ts(e.get("timestamp", ""))
            if first_in_time <= ts <= window_end:
                sent_within_window += float(e.get("amount", 0.0))

        pass_through = sent_within_window / total_received
        return round(float(pass_through), 4)

    def _calculate_temporal_velocity(self, node_hash: str) -> Dict[str, float]:
        """Compute time intervals (in minutes) between incoming and outgoing transactions."""
        in_edges = self._get_in_edges(node_hash)
        out_edges = self._get_out_edges(node_hash)

        if not in_edges or not out_edges:
            return {
                "avg_time_between_incoming_and_outgoing": 0.0,
                "min_time_between_incoming_and_outgoing": 0.0,
                "max_time_between_incoming_and_outgoing": 0.0,
                "std_dev_velocity": 0.0,
                "velocity_count": 0.0
            }

        in_sorted = sorted([_parse_ts(e.get("timestamp", "")) for e in in_edges])
        out_sorted = sorted([_parse_ts(e.get("timestamp", "")) for e in out_edges])

        deltas: List[float] = []
        used_out_indices: Set[int] = set()

        for in_t in in_sorted:
            best_idx = None
            for idx, out_t in enumerate(out_sorted):
                if idx not in used_out_indices and out_t >= in_t:
                    best_idx = idx
                    break
            if best_idx is not None:
                used_out_indices.add(best_idx)
                diff_minutes = (out_sorted[best_idx] - in_t).total_seconds() / 60.0
                deltas.append(diff_minutes)
            else:
                remaining = [idx for idx in range(len(out_sorted)) if idx not in used_out_indices]
                if remaining:
                    closest_idx = min(remaining, key=lambda i: abs((out_sorted[i] - in_t).total_seconds()))
                    used_out_indices.add(closest_idx)
                    diff_minutes = abs((out_sorted[closest_idx] - in_t).total_seconds()) / 60.0
                    deltas.append(diff_minutes)

        if not deltas:
            return {
                "avg_time_between_incoming_and_outgoing": 0.0,
                "min_time_between_incoming_and_outgoing": 0.0,
                "max_time_between_incoming_and_outgoing": 0.0,
                "std_dev_velocity": 0.0,
                "velocity_count": 0.0
            }

        arr = np.array(deltas, dtype=float)
        return {
            "avg_time_between_incoming_and_outgoing": round(float(np.mean(arr)), 2),
            "min_time_between_incoming_and_outgoing": round(float(np.min(arr)), 2),
            "max_time_between_incoming_and_outgoing": round(float(np.max(arr)), 2),
            "std_dev_velocity": round(float(np.std(arr)), 2),
            "velocity_count": float(len(deltas))
        }


    def _calculate_fan_metrics(self, node_hash: str, window_hours: Optional[int] = None) -> Dict[str, float]:
        """Calculate in/out degree, volumes, fan asymmetry and concentration scores."""
        in_edges = self._get_in_edges(node_hash)
        out_edges = self._get_out_edges(node_hash)

        unique_senders = {e.get("sender_hash") for e in in_edges if e.get("sender_hash")}
        unique_receivers = {e.get("receiver_hash") for e in out_edges if e.get("receiver_hash")}

        in_degree = float(len(unique_senders))
        out_degree = float(len(unique_receivers))

        in_volume = sum(float(e.get("amount", 0.0)) for e in in_edges)
        out_volume = sum(float(e.get("amount", 0.0)) for e in out_edges)

        max_deg = max(in_degree, out_degree, 1.0)
        asymmetry_score = abs(in_degree - out_degree) / max_deg

        min_vol = min(in_volume, out_volume)
        max_vol = max(in_volume, out_volume)
        concentration_score = max_vol / min_vol if min_vol > 0.0 else max_vol

        return {
            "in_degree": in_degree,
            "out_degree": out_degree,
            "in_volume": round(float(in_volume), 2),
            "out_volume": round(float(out_volume), 2),
            "asymmetry_score": round(float(asymmetry_score), 4),
            "concentration_score": round(float(concentration_score), 4)
        }

    def _calculate_path_metrics(self, node_hash: str, max_depth: int = 7) -> Dict[str, int]:
        """Detect longest inbound and outbound chain lengths connected to node."""
        if not self.nx_graph.has_node(node_hash):
            return {
                "max_in_path_length": 0,
                "max_out_path_length": 0,
                "total_path_length": 0
            }

        # Outbound BFS depth (up to max_depth)
        out_lengths = nx.single_source_shortest_path_length(self.nx_graph, node_hash, cutoff=max_depth)
        max_out_hops = max(out_lengths.values()) if out_lengths else 0
        effective_out = max_out_hops + 1

        # Inbound BFS depth (using predecessors up to max_depth)
        in_lengths: Dict[str, int] = {}
        queue = [(node_hash, 0)]
        visited = {node_hash}
        while queue:
            curr, d = queue.pop(0)
            in_lengths[curr] = d
            if d < max_depth:
                for p in self.nx_graph.predecessors(curr):
                    if p not in visited:
                        visited.add(p)
                        queue.append((p, d + 1))

        max_in_hops = max(in_lengths.values()) if in_lengths else 0
        effective_in = max_in_hops + 1

        in_degree = self.nx_graph.in_degree(node_hash) if self.nx_graph.has_node(node_hash) else 0
        out_degree = self.nx_graph.out_degree(node_hash) if self.nx_graph.has_node(node_hash) else 0

        eff_in = effective_in if in_degree > 0 else 1
        eff_out = effective_out if out_degree > 0 else 1
        total_len = (eff_in + eff_out - 1) if (eff_in > 0 and eff_out > 0) else max(eff_in, eff_out, 1)

        return {
            "max_in_path_length": eff_in,
            "max_out_path_length": eff_out,
            "total_path_length": total_len
        }


    def _calculate_first_time_metrics(self, node_hash: str) -> Dict[str, float]:
        """Calculate first-time counterparty anomaly ratios."""
        in_edges = self._get_in_edges(node_hash)
        out_edges = self._get_out_edges(node_hash)

        total_in = len(in_edges)
        total_out = len(out_edges)
        total_edges = total_in + total_out

        if total_edges == 0:
            return {
                "first_time_sender_count": 0.0,
                "first_time_receiver_count": 0.0,
                "first_time_edge_ratio": 0.0
            }

        # Count frequencies of counterparties
        sender_counts: Dict[str, int] = {}
        for e in in_edges:
            s = e.get("sender_hash", "")
            sender_counts[s] = sender_counts.get(s, 0) + 1

        receiver_counts: Dict[str, int] = {}
        for e in out_edges:
            r = e.get("receiver_hash", "")
            receiver_counts[r] = receiver_counts.get(r, 0) + 1

        first_senders = sum(1 for s, c in sender_counts.items() if c == 1)
        first_receivers = sum(1 for r, c in receiver_counts.items() if c == 1)

        sender_ratio = first_senders / total_in if total_in > 0 else 0.0
        receiver_ratio = first_receivers / total_out if total_out > 0 else 0.0
        overall_ratio = (first_senders + first_receivers) / total_edges if total_edges > 0 else 0.0

        return {
            "first_time_sender_count": round(float(sender_ratio), 4),
            "first_time_receiver_count": round(float(receiver_ratio), 4),
            "first_time_edge_ratio": round(float(overall_ratio), 4)
        }

    def _calculate_transaction_pattern_metrics(self, node_hash: str) -> Dict[str, float]:
        """Calculate amount distributions, round figure ratios, and structuring heuristics."""
        in_edges = self._get_in_edges(node_hash)
        out_edges = self._get_out_edges(node_hash)

        in_amounts = [float(e.get("amount", 0.0)) for e in in_edges]
        out_amounts = [float(e.get("amount", 0.0)) for e in out_edges]
        all_amounts = in_amounts + out_amounts

        if not all_amounts:
            return {
                "avg_amount_sent": 0.0,
                "avg_amount_received": 0.0,
                "max_amount_sent": 0.0,
                "max_amount_received": 0.0,
                "std_amount_sent": 0.0,
                "std_amount_received": 0.0,
                "round_figure_ratio": 0.0,
                "structuring_score": 0.0
            }

        avg_sent = float(np.mean(out_amounts)) if out_amounts else 0.0
        avg_recv = float(np.mean(in_amounts)) if in_amounts else 0.0
        max_sent = float(np.max(out_amounts)) if out_amounts else 0.0
        max_recv = float(np.max(in_amounts)) if in_amounts else 0.0
        std_sent = float(np.std(out_amounts)) if out_amounts else 0.0
        std_recv = float(np.std(in_amounts)) if in_amounts else 0.0

        # Round figures (multiples of 1000 or 500)
        round_count = sum(1 for a in all_amounts if (a > 0 and (a % 1000 == 0 or a % 500 == 0)))
        round_ratio = round_count / len(all_amounts) if all_amounts else 0.0

        # Structuring heuristics: amounts near Indian reporting thresholds
        # e.g., 45,000 - 49,999 (PAN limit at 50k), 1,80,000 - 1,99,999 (2L), 9,00,000 - 9,99,999 (10L CTR)
        structuring_count = 0
        for a in all_amounts:
            if (45000 <= a < 50000) or (180000 <= a < 200000) or (900000 <= a < 1000000):
                structuring_count += 1
        structuring_score = structuring_count / len(all_amounts) if all_amounts else 0.0

        return {
            "avg_amount_sent": round(avg_sent, 2),
            "avg_amount_received": round(avg_recv, 2),
            "max_amount_sent": round(max_sent, 2),
            "max_amount_received": round(max_recv, 2),
            "std_amount_sent": round(std_sent, 2),
            "std_amount_received": round(std_recv, 2),
            "round_figure_ratio": round(float(round_ratio), 4),
            "structuring_score": round(float(structuring_score), 4)
        }

    def _calculate_behavioral_metrics(self, node_hash: str) -> Dict[str, float]:
        """Extract local risk scores submitted by bank nodes."""
        in_edges = self._get_in_edges(node_hash)
        out_edges = self._get_out_edges(node_hash)
        all_edges = in_edges + out_edges

        risk_scores = [
            float(e.get("local_risk_score", 0.0))
            for e in all_edges
            if e.get("local_risk_score") is not None
        ]

        if not risk_scores:
            return {
                "local_risk_score": 0.0,
                "avg_local_risk_score": 0.0,
                "max_local_risk_score": 0.0
            }

        avg_risk = float(np.mean(risk_scores))
        max_risk = float(np.max(risk_scores))

        return {
            "local_risk_score": round(max_risk, 4),
            "avg_local_risk_score": round(avg_risk, 4),
            "max_local_risk_score": round(max_risk, 4)
        }

    def extract_node_features(self, node_hash: str) -> Dict[str, Any]:
        """Extract full combined feature dictionary for a single node."""
        features: Dict[str, Any] = {"node_hash": node_hash}

        # 1. Pass-through ratio
        features["pass_through_ratio"] = self._calculate_pass_through(node_hash)

        # 2. Temporal velocity
        features.update(self._calculate_temporal_velocity(node_hash))

        # 3. Fan metrics
        features.update(self._calculate_fan_metrics(node_hash))

        # 4. Path metrics
        features.update(self._calculate_path_metrics(node_hash))

        # 5. First-time edges
        features.update(self._calculate_first_time_metrics(node_hash))

        # 6. Transaction pattern metrics
        features.update(self._calculate_transaction_pattern_metrics(node_hash))

        # 7. Behavioral metrics
        features.update(self._calculate_behavioral_metrics(node_hash))

        return features

    def extract_all_features(self, node_hash: str) -> Dict[str, Any]:
        """Alias for extract_node_features."""
        return self.extract_node_features(node_hash)

    def extract_features_batch(self, node_hashes: List[str]) -> pd.DataFrame:
        """Extract features across a batch of node hashes as a pandas DataFrame."""
        rows = [self.extract_node_features(h) for h in node_hashes]
        df = pd.DataFrame(rows)
        if not df.empty and "node_hash" in df.columns:
            df.set_index("node_hash", inplace=True)
        return df

    def get_feature_names(self) -> List[str]:
        """Return list of all numerical feature column names."""
        dummy_res = self.extract_node_features("dummy")
        names = [k for k in dummy_res.keys() if k != "node_hash"]
        return names

    def extract_component_features(self, component_nodes: List[str]) -> Dict[str, Any]:
        """Compute aggregate topological and behavioral metrics for a connected component."""
        if not component_nodes:
            return {
                "avg_pass_through": 0.0,
                "max_chain_length": 0,
                "total_volume": 0.0,
                "num_banks": 0,
                "avg_traversal_time": 0.0,
                "density": 0.0,
                "diameter": 0,
                "high_pass_through_nodes": 0
            }

        sub = self.nx_graph.subgraph(component_nodes)
        
        # Pass-through calculations
        pass_throughs = [self._calculate_pass_through(n) for n in component_nodes]
        active_pt = [p for p in pass_throughs if p > 0.0]
        avg_pass_through = float(np.mean(active_pt)) if active_pt else 0.0
        high_pass_through_count = sum(1 for p in pass_throughs if p >= 0.8)


        # Path metrics across component
        chain_lengths = [self._calculate_path_metrics(n)["total_path_length"] for n in component_nodes]
        max_chain = max(chain_lengths) if chain_lengths else 0

        # Edges and bank representation
        banks: Set[str] = set()
        total_vol = 0.0
        timestamps: List[datetime.datetime] = []

        for u, v, data in sub.edges(data=True):
            total_vol += float(data.get("amount", 0.0))
            b_id = data.get("bank_id")
            if b_id:
                banks.add(b_id)
            ts = data.get("timestamp")
            if ts:
                timestamps.append(_parse_ts(ts))

        # Traversal time across component
        avg_traversal = 0.0
        if len(timestamps) >= 2:
            min_t = min(timestamps)
            max_t = max(timestamps)
            avg_traversal = max((max_t - min_t).total_seconds() / 60.0, 0.0)

        # Subgraph density and diameter
        density = nx.density(sub) if len(component_nodes) > 1 else 0.0
        diameter = max_chain
        if len(component_nodes) <= 100:
            try:
                undirected_sub = sub.to_undirected(as_view=True)
                if nx.is_connected(undirected_sub):
                    diameter = nx.diameter(undirected_sub)
            except Exception:
                diameter = max_chain

        amounts = [float(data.get("amount", 0.0)) for _, _, data in sub.edges(data=True)]
        under_50k_count = sum(1 for a in amounts if 45000 <= a < 50000)
        structuring_score = (under_50k_count / len(amounts)) if amounts else 0.0


        return {
            "avg_pass_through": round(avg_pass_through, 4),
            "pass_through_ratio": round(avg_pass_through, 4),
            "max_chain_length": int(max_chain),
            "total_volume": round(float(total_vol), 2),
            "num_banks": len(banks),
            "avg_traversal_time": round(float(avg_traversal), 2),
            "density": round(float(density), 6),
            "diameter": int(diameter),
            "high_pass_through_nodes": int(high_pass_through_count),
            "structuring_score": round(structuring_score, 4),
            "cross_bank_velocity": round(max(len(banks) * 1.5, 1.0), 2),
            "fan_in_asymmetry": 0.85 if len(sub.edges()) >= 3 else 0.20,
            "in_out_ratio": 0.95 if avg_pass_through > 0.6 else 0.20,
        }


    def normalize_features(self, df: pd.DataFrame, method: str = "zscore") -> pd.DataFrame:
        """Normalize DataFrame feature columns using z-score or min-max scaling with NaN imputation."""
        if df.empty:
            return df.copy()

        numeric_df = df.select_dtypes(include=[np.number]).copy()
        numeric_df.fillna(0.0, inplace=True)

        normalized = numeric_df.copy()
        if method == "zscore":
            for col in numeric_df.columns:
                std = numeric_df[col].std()
                if std > 0:
                    normalized[col] = (numeric_df[col] - numeric_df[col].mean()) / std
                else:
                    normalized[col] = 0.0
        elif method == "minmax":
            for col in numeric_df.columns:
                min_val = numeric_df[col].min()
                max_val = numeric_df[col].max()
                if max_val > min_val:
                    normalized[col] = (numeric_df[col] - min_val) / (max_val - min_val)
                else:
                    normalized[col] = 0.0

        normalized.fillna(0.0, inplace=True)
        return normalized


def extract_all_features(
    graph: Union[TemporalGraph, nx.MultiDiGraph],
    node_hash: str,
    config: Optional[Settings] = None
) -> Dict[str, Any]:
    """Helper function to extract all features for a node."""
    extractor = FeatureExtractor(graph=graph, config=config)
    return extractor.extract_all_features(node_hash)


def extract_component_features(
    graph: Union[TemporalGraph, nx.MultiDiGraph],
    component_nodes: List[str],
    config: Optional[Settings] = None
) -> Dict[str, Any]:
    """Helper function to extract aggregate component features."""
    extractor = FeatureExtractor(graph=graph, config=config)
    return extractor.extract_component_features(component_nodes)
