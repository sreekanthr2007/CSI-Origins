"""Bounded pattern-decay graph traversal engine with hard safety caps and stopping rules."""
import time
import json
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Dict, Any, List, Set, Optional, Tuple, Union

import networkx as nx

from backend.app.config import settings, Settings
from backend.app.graph.graph_engine import TemporalGraph
from backend.app.database.repositories import InvestigationRepository

logger = logging.getLogger("mule-detection-traversal")


class TraversalResult:
    """Encapsulates the state, metrics, visited path, and stopping rationale of a graph traversal."""

    def __init__(
        self,
        start_node: str,
        nodes_visited: List[str],
        edges_visited: List[Dict[str, Any]],
        depth_reached: int,
        banks_queried: List[str],
        stopping_reason: str,
        stopping_at_edge: Optional[Dict[str, Any]] = None,
        traversal_time_ms: float = 0.0,
        status: str = "completed",
        decay_metrics: Optional[Dict[str, Any]] = None
    ):
        self.start_node = start_node
        self.nodes_visited = nodes_visited
        self.edges_visited = edges_visited
        self.depth_reached = depth_reached
        self.banks_queried = banks_queried
        self.stopping_reason = stopping_reason
        self.stopping_at_edge = stopping_at_edge
        self.traversal_time_ms = traversal_time_ms
        self.status = status
        self.decay_metrics = decay_metrics or {
            "avg_pass_through": 0.0,
            "min_pass_through": 0.0,
            "avg_time_gap_minutes": 0.0,
            "bank_diversity": len(banks_queried)
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize traversal result to standard JSON dictionary."""
        return {
            "start_node": self.start_node,
            "nodes_visited": self.nodes_visited,
            "edges_visited": self.edges_visited,
            "depth_reached": self.depth_reached,
            "banks_queried": self.banks_queried,
            "stopping_reason": self.stopping_reason,
            "stopping_at_edge": self.stopping_at_edge,
            "traversal_time_ms": round(self.traversal_time_ms, 2),
            "status": self.status,
            "decay_metrics": self.decay_metrics
        }


class PatternDecayTraversal:
    """Executes bounded bidirectional graph exploration driven by mule pattern decay and hard caps."""

    def __init__(
        self,
        graph: Optional[Union[TemporalGraph, nx.MultiDiGraph]] = None,
        config: Optional[Settings] = None
    ):
        self.config = config or settings
        if graph is None:
            self.tg = TemporalGraph(config=self.config)
            self.g = self.tg.graph
        elif isinstance(graph, TemporalGraph):
            self.tg = graph
            self.g = graph.graph
        else:
            self.g = graph
            self.tg = None

        # Configuration parameters
        self.pass_through_threshold = getattr(self.config, "PASS_THROUGH_THRESHOLD", 0.60)
        self.max_time_gap_hours = getattr(self.config, "MAX_TIME_GAP_HOURS", 72.0)
        self.min_historical_edges_to_consider = 3
        self.max_depth_cap = getattr(self.config, "MAX_DEPTH", 7)
        self.max_banks_cap = 15
        self.max_edges_cap = 1000

    def traverse_from_node(
        self,
        start_hash: str,
        direction: str = "both",
        max_depth: Optional[int] = None
    ) -> TraversalResult:
        """Traverse upstream and downstream from start_hash until stopping criteria or hard caps are triggered."""
        t0 = time.perf_counter()
        depth_limit = min(max_depth or self.max_depth_cap, self.max_depth_cap)

        if not self.g.has_node(start_hash):
            return TraversalResult(
                start_node=start_hash,
                nodes_visited=[],
                edges_visited=[],
                depth_reached=0,
                banks_queried=[],
                stopping_reason="node_not_found",
                traversal_time_ms=(time.perf_counter() - t0) * 1000,
                status="completed"
            )

        visited_nodes: Set[str] = {start_hash}
        visited_edges: List[Dict[str, Any]] = []
        queried_banks: Set[str] = set()
        max_depth_reached = 0

        # Extract initial bank of start node
        start_bank = self.g.nodes[start_hash].get("bank_id")
        if start_bank:
            queried_banks.add(start_bank)

        stopping_reason = "completed"
        stopping_at_edge: Optional[Dict[str, Any]] = None

        # Queue items: (current_node, current_depth, traversal_dir, incoming_edge_meta)
        queue = deque([(start_hash, 0, "both", None)])

        while queue:
            curr_node, curr_depth, active_dir, prev_edge = queue.popleft()
            max_depth_reached = max(max_depth_reached, curr_depth)

            # Check Hard Safety Caps
            if curr_depth >= depth_limit:
                stopping_reason = "hard_cap_reached"
                continue

            if len(queried_banks) >= self.max_banks_cap:
                stopping_reason = "hard_cap_reached"
                break

            if len(visited_edges) >= self.max_edges_cap:
                stopping_reason = "hard_cap_reached"
                break

            # 1. Expand Downstream (Forward: Sender -> Receiver)
            if active_dir in ["both", "downstream"]:
                forward_edges = self._get_sorted_out_edges(curr_node)
                for u, v, k, e_data in forward_edges:
                    bank = e_data.get("bank_id", "UNKNOWN")
                    queried_banks.add(bank)

                    edge_record = {
                        "from": u,
                        "to": v,
                        "amount": float(e_data.get("amount", 0.0)),
                        "timestamp": str(e_data.get("timestamp", "")),
                        "bank_id": bank,
                        "direction": "downstream",
                        "depth": curr_depth + 1
                    }

                    eval_decision, reason, pt_val = self._evaluate_edge(u, v, e_data, prev_edge)
                    if eval_decision == "stop":
                        stopping_reason = reason
                        stopping_at_edge = {
                            "from": u,
                            "to": v,
                            "reason": reason,
                            "pass_through": round(pt_val, 4) if pt_val is not None else None,
                            "threshold": self.pass_through_threshold
                        }
                        break

                    visited_edges.append(edge_record)
                    if v not in visited_nodes:
                        visited_nodes.add(v)
                        queue.append((v, curr_depth + 1, "downstream", edge_record))

                if stopping_reason != "completed" and stopping_reason != "hard_cap_reached":
                    break

            # 2. Expand Upstream (Backward: Receiver <- Sender)
            if active_dir in ["both", "upstream"]:
                backward_edges = self._get_sorted_in_edges(curr_node)
                for u, v, k, e_data in backward_edges:
                    bank = e_data.get("bank_id", "UNKNOWN")
                    queried_banks.add(bank)

                    edge_record = {
                        "from": u,
                        "to": v,
                        "amount": float(e_data.get("amount", 0.0)),
                        "timestamp": str(e_data.get("timestamp", "")),
                        "bank_id": bank,
                        "direction": "upstream",
                        "depth": curr_depth + 1
                    }

                    eval_decision, reason, pt_val = self._evaluate_edge(v, u, e_data, prev_edge)
                    if eval_decision == "stop":
                        stopping_reason = reason
                        stopping_at_edge = {
                            "from": u,
                            "to": v,
                            "reason": reason,
                            "pass_through": round(pt_val, 4) if pt_val is not None else None,
                            "threshold": self.pass_through_threshold
                        }
                        break

                    visited_edges.append(edge_record)
                    if u not in visited_nodes:
                        visited_nodes.add(u)
                        queue.append((u, curr_depth + 1, "upstream", edge_record))

                if stopping_reason != "completed" and stopping_reason != "hard_cap_reached":
                    break

        duration_ms = (time.perf_counter() - t0) * 1000
        decay_metrics = self._calculate_decay_metrics(visited_edges, queried_banks)

        return TraversalResult(
            start_node=start_hash,
            nodes_visited=list(visited_nodes),
            edges_visited=visited_edges,
            depth_reached=max_depth_reached,
            banks_queried=list(queried_banks),
            stopping_reason=stopping_reason,
            stopping_at_edge=stopping_at_edge,
            traversal_time_ms=duration_ms,
            status="completed",
            decay_metrics=decay_metrics
        )

    def _evaluate_edge(
        self,
        src: str,
        dst: str,
        edge_data: Dict[str, Any],
        prev_edge: Optional[Dict[str, Any]]
    ) -> Tuple[str, str, Optional[float]]:
        """Evaluate pattern-decay stopping rules for candidate edge."""
        # 1. Historical relationship check (prior high-volume benign interaction)
        if self._has_historical_relationship(src, dst):
            return "stop", "historical_relationship", None

        # 2. Time gap check (exceeds maximum allowed hold duration)
        if prev_edge and prev_edge.get("timestamp") and edge_data.get("timestamp"):
            try:
                t_prev = datetime.fromisoformat(str(prev_edge["timestamp"]).replace("Z", "+00:00"))
                t_curr = datetime.fromisoformat(str(edge_data["timestamp"]).replace("Z", "+00:00"))
                gap_hours = abs((t_curr - t_prev).total_seconds()) / 3600.0
                if gap_hours > self.max_time_gap_hours:
                    return "stop", "time_gap_exceeded", None
            except Exception:
                pass

        # 3. Pass-through ratio check on destination node
        pt_ratio = self._calculate_node_pass_through(dst)
        if pt_ratio is not None and pt_ratio < self.pass_through_threshold:
            # Check if this node has outgoing transfers at all; if it does and pass-through is low -> decay
            out_degree = self.g.out_degree(dst)
            if out_degree > 0 and pt_ratio < self.pass_through_threshold:
                return "stop", "pattern_decay", pt_ratio

        return "pass", "ok", pt_ratio

    def _calculate_node_pass_through(self, node: str) -> Optional[float]:
        """Compute pass-through ratio for node."""
        if not self.g.has_node(node):
            return None

        total_in = 0.0
        for _, _, data in self.g.in_edges(node, data=True):
            total_in += float(data.get("amount", 0.0))

        total_out = 0.0
        for _, _, data in self.g.out_edges(node, data=True):
            total_out += float(data.get("amount", 0.0))

        if total_in <= 0.0:
            return 1.0 if total_out > 0 else None

        return float(total_out / total_in)

    def _has_historical_relationship(self, u: str, v: str) -> bool:
        """Check if established pairwise interaction exists between accounts (> 3 historical transactions)."""
        edge_count = 0
        if self.g.has_edge(u, v):
            edge_count += len(self.g.get_edge_data(u, v))
        if self.g.has_edge(v, u):
            edge_count += len(self.g.get_edge_data(v, u))
        return edge_count >= self.min_historical_edges_to_consider

    def _get_sorted_out_edges(self, node: str) -> List[Tuple[str, str, int, Dict[str, Any]]]:
        """Return outgoing edges sorted chronologically."""
        edges = []
        if self.g.has_node(node):
            for u, v, k, data in self.g.out_edges(node, keys=True, data=True):
                edges.append((u, v, k, data))
        edges.sort(key=lambda x: str(x[3].get("timestamp", "")))
        return edges

    def _get_sorted_in_edges(self, node: str) -> List[Tuple[str, str, int, Dict[str, Any]]]:
        """Return incoming edges sorted chronologically."""
        edges = []
        if self.g.has_node(node):
            for u, v, k, data in self.g.in_edges(node, keys=True, data=True):
                edges.append((u, v, k, data))
        edges.sort(key=lambda x: str(x[3].get("timestamp", "")))
        return edges

    def _calculate_decay_metrics(
        self,
        edges: List[Dict[str, Any]],
        banks: Set[str]
    ) -> Dict[str, Any]:
        """Compute aggregated metrics over the traversed subgraph."""
        if not edges:
            return {
                "avg_pass_through": 0.0,
                "min_pass_through": 0.0,
                "avg_time_gap_minutes": 0.0,
                "bank_diversity": len(banks)
            }

        pts = []
        for e in edges:
            pt = self._calculate_node_pass_through(e["to"])
            if pt is not None:
                pts.append(pt)

        # Time gaps
        gaps = []
        for i in range(len(edges) - 1):
            t1_str = edges[i].get("timestamp")
            t2_str = edges[i + 1].get("timestamp")
            if t1_str and t2_str:
                try:
                    t1 = datetime.fromisoformat(t1_str.replace("Z", "+00:00"))
                    t2 = datetime.fromisoformat(t2_str.replace("Z", "+00:00"))
                    gaps.append(abs((t2 - t1).total_seconds()) / 60.0)
                except Exception:
                    pass

        return {
            "avg_pass_through": round(float(sum(pts) / len(pts)), 4) if pts else 0.0,
            "min_pass_through": round(float(min(pts)), 4) if pts else 0.0,
            "avg_time_gap_minutes": round(float(sum(gaps) / len(gaps)), 2) if gaps else 0.0,
            "bank_diversity": len(banks)
        }

    def save_state(self, investigation_id: str, result: TraversalResult) -> None:
        """Persist traversal results and state to database."""
        InvestigationRepository.update_traversal_state(
            investigation_id=investigation_id,
            depth_reached=result.depth_reached,
            banks_queried=result.banks_queried,
            traversal_path=result.to_dict(),
            status=result.status
        )

    def load_state(self, investigation_id: str) -> Optional[TraversalResult]:
        """Load persisted traversal result from database."""
        rec = InvestigationRepository.get_by_id(investigation_id)
        if not rec or not rec.get("traversal_path"):
            return None
        p = rec["traversal_path"]
        return TraversalResult(
            start_node=p.get("start_node", ""),
            nodes_visited=p.get("nodes_visited", []),
            edges_visited=p.get("edges_visited", []),
            depth_reached=p.get("depth_reached", 0),
            banks_queried=p.get("banks_queried", []),
            stopping_reason=p.get("stopping_reason", "completed"),
            stopping_at_edge=p.get("stopping_at_edge"),
            traversal_time_ms=p.get("traversal_time_ms", 0.0),
            status=p.get("status", "completed"),
            decay_metrics=p.get("decay_metrics")
        )

    def resume_traversal(self, investigation_id: str) -> TraversalResult:
        """Resume an incomplete traversal from loaded checkpoint."""
        prior = self.load_state(investigation_id)
        if prior and prior.start_node:
            return self.traverse_from_node(prior.start_node)
        raise ValueError(f"Cannot resume investigation {investigation_id}: No state found")
