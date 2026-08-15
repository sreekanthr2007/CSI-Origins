"""Central graph ingestion and analysis engine for Cross-Bank Mule Account Detection."""
import json
import logging
import datetime
from typing import Dict, Any, List, Optional, Union, Set
import networkx as nx
from networkx.readwrite import json_graph

from backend.app.config import settings, Settings
from backend.app.database.repositories import EdgeRepository, GraphSnapshotRepository

logger = logging.getLogger("mule-detection-graph-engine")


def _parse_datetime(val: Union[str, datetime.datetime]) -> datetime.datetime:
    """Parse string or datetime into UTC datetime object."""
    if isinstance(val, datetime.datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=datetime.timezone.utc)
        return val
    try:
        dt = datetime.datetime.fromisoformat(val.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=datetime.timezone.utc)
        return dt
    except Exception:
        return datetime.datetime.now(datetime.timezone.utc)


class TemporalGraph:
    """Directed temporal multigraph representing cross-bank financial flows."""

    def __init__(self, config: Optional[Settings] = None):
        self.config = config or settings
        self.graph: nx.MultiDiGraph = nx.MultiDiGraph()

    def add_edge(
        self,
        sender_hash: str,
        receiver_hash: str,
        amount: float,
        timestamp: Union[str, datetime.datetime],
        bank_id: str,
        local_risk_score: float = 0.0,
        is_interbank: bool = True,
        **extra_attrs
    ) -> int:
        """Add a directed transaction edge with temporal and risk metadata."""
        ts_str = timestamp.isoformat() if isinstance(timestamp, datetime.datetime) else str(timestamp)
        edge_data = {
            "sender_hash": sender_hash,
            "receiver_hash": receiver_hash,
            "amount": float(amount),
            "timestamp": ts_str,
            "bank_id": str(bank_id),
            "local_risk_score": float(local_risk_score if local_risk_score is not None else 0.0),
            "is_interbank": bool(is_interbank),
            **extra_attrs
        }
        key = self.graph.add_edge(sender_hash, receiver_hash, **edge_data)
        return key

    def add_transaction(
        self,
        edge_id: str,
        sender_hash: str,
        receiver_hash: str,
        amount: float,
        timestamp: Union[str, datetime.datetime],
        bank_id: str,
        local_risk_score: float = 0.0,
        is_interbank: bool = True,
        **extra_attrs
    ) -> int:
        """Convenience alias for adding a transaction edge."""
        return self.add_edge(
            sender_hash=sender_hash,
            receiver_hash=receiver_hash,
            amount=amount,
            timestamp=timestamp,
            bank_id=bank_id,
            local_risk_score=local_risk_score,
            is_interbank=is_interbank,
            edge_id=edge_id,
            **extra_attrs
        )

    @property
    def node_count(self) -> int:
        """Total number of nodes in graph."""
        return self.graph.number_of_nodes()

    @property
    def edge_count(self) -> int:
        """Total number of edges in graph."""
        return self.graph.number_of_edges()

    def to_dict(self) -> Dict[str, Any]:
        """Convert graph to node-link JSON-serializable dictionary."""
        return json_graph.node_link_data(self.graph)

    def nodes(self, *args, **kwargs):
        """Proxy to underlying networkx graph nodes."""
        return self.graph.nodes(*args, **kwargs)

    def edges(self, *args, **kwargs):
        """Proxy to underlying networkx graph edges."""
        return self.graph.edges(*args, **kwargs)


    def add_edges_batch(self, edges: List[Dict[str, Any]]) -> int:
        """Batch insertion of transaction edges for maximum ingestion efficiency."""
        if not edges:
            return 0
        
        count = 0
        for e in edges:
            sender = e.get("sender_hash") or e.get("sender_account") or e.get("sender")
            receiver = e.get("receiver_hash") or e.get("receiver_account") or e.get("receiver")
            if not sender or not receiver:
                continue
            
            amount = float(e.get("amount", 0.0))
            ts = e.get("timestamp", datetime.datetime.now(datetime.timezone.utc).isoformat())
            ts_str = ts.isoformat() if isinstance(ts, datetime.datetime) else str(ts)
            bank_id = str(e.get("bank_id") or e.get("sender_bank_id") or e.get("receiver_bank_id") or "UNKNOWN")
            local_risk = float(e.get("local_risk_score", 0.0) or 0.0)
            is_interbank = bool(e.get("is_interbank", True))

            edge_data = {
                "sender_hash": sender,
                "receiver_hash": receiver,
                "amount": amount,
                "timestamp": ts_str,
                "bank_id": bank_id,
                "local_risk_score": local_risk,
                "is_interbank": is_interbank
            }
            for k, v in e.items():
                if k not in edge_data and k != "id":
                    edge_data[k] = v

            self.graph.add_edge(sender, receiver, **edge_data)
            count += 1
            
        return count


    def build_from_db(
        self,
        start_time: Optional[Union[str, datetime.datetime]] = None,
        end_time: Optional[Union[str, datetime.datetime]] = None,
        db_path: Optional[str] = None
    ) -> int:
        """Query SQLite database and build the multi-bank temporal graph."""
        if start_time and end_time:
            st_str = start_time.isoformat() if isinstance(start_time, datetime.datetime) else str(start_time)
            et_str = end_time.isoformat() if isinstance(end_time, datetime.datetime) else str(end_time)
            edges = EdgeRepository.get_edges_in_time_range(st_str, et_str, db_path=db_path)
        else:
            edges = EdgeRepository.get_all_edges(db_path=db_path)

        return self.add_edges_batch(edges)

    def get_edge_count(self) -> int:
        """Return total number of edges in graph."""
        return self.graph.number_of_edges()

    def get_node_count(self) -> int:
        """Return total number of nodes in graph."""
        return self.graph.number_of_nodes()

    def get_nodes(self) -> List[str]:
        """Return list of all node hash IDs."""
        return list(self.graph.nodes())

    def get_edges_for_node(self, node_hash: str) -> List[Dict[str, Any]]:
        """Return all edges (inbound and outbound) involving this node."""
        if not self.graph.has_node(node_hash):
            return []
        
        results = []
        for u, v, k, data in self.graph.in_edges(node_hash, keys=True, data=True):
            edge_dict = dict(data)
            edge_dict.setdefault("sender_hash", u)
            edge_dict.setdefault("receiver_hash", v)
            edge_dict["edge_key"] = k
            results.append(edge_dict)

        for u, v, k, data in self.graph.out_edges(node_hash, keys=True, data=True):
            edge_dict = dict(data)
            edge_dict.setdefault("sender_hash", u)
            edge_dict.setdefault("receiver_hash", v)
            edge_dict["edge_key"] = k
            results.append(edge_dict)

        return results

    def get_in_edges(self, node_hash: str) -> List[Dict[str, Any]]:
        """Return edges where node is the receiver."""
        if not self.graph.has_node(node_hash):
            return []
        
        results = []
        for u, v, k, data in self.graph.in_edges(node_hash, keys=True, data=True):
            edge_dict = dict(data)
            edge_dict.setdefault("sender_hash", u)
            edge_dict.setdefault("receiver_hash", v)
            edge_dict["edge_key"] = k
            results.append(edge_dict)
        return results

    def get_out_edges(self, node_hash: str) -> List[Dict[str, Any]]:
        """Return edges where node is the sender."""
        if not self.graph.has_node(node_hash):
            return []
        
        results = []
        for u, v, k, data in self.graph.out_edges(node_hash, keys=True, data=True):
            edge_dict = dict(data)
            edge_dict.setdefault("sender_hash", u)
            edge_dict.setdefault("receiver_hash", v)
            edge_dict["edge_key"] = k
            results.append(edge_dict)
        return results

    def get_connected_component(self, node_hash: str) -> "TemporalGraph":
        """Return subgraph of the weakly connected component containing the specified node."""
        subgraph_tg = TemporalGraph(config=self.config)
        if not self.graph.has_node(node_hash):
            return subgraph_tg

        undirected = self.graph.to_undirected(as_view=True)
        component_nodes = nx.node_connected_component(undirected, node_hash)
        
        sub = self.graph.subgraph(component_nodes)
        subgraph_tg.graph = nx.MultiDiGraph(sub)
        return subgraph_tg

    def get_neighbors(self, node_hash: str, direction: str = "both") -> List[str]:
        """Return inbound, outbound, or bidirectional neighbor node IDs."""
        if not self.graph.has_node(node_hash):
            return []

        if direction == "in":
            return list(self.graph.predecessors(node_hash))
        elif direction == "out":
            return list(self.graph.successors(node_hash))
        elif direction == "both":
            preds = set(self.graph.predecessors(node_hash))
            succs = set(self.graph.successors(node_hash))
            return list(preds.union(succs))
        else:
            raise ValueError(f"Invalid direction: {direction}. Must be 'in', 'out', or 'both'.")

    def get_shortest_path(self, source: str, target: str) -> Optional[List[str]]:
        """Return directed shortest path between source and target nodes, or None."""
        if not self.graph.has_node(source) or not self.graph.has_node(target):
            return None
        try:
            return nx.shortest_path(self.graph, source=source, target=target)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    def get_temporal_window(
        self,
        start_time: Union[str, datetime.datetime],
        end_time: Union[str, datetime.datetime]
    ) -> "TemporalGraph":
        """Return subgraph containing only transactions within the specified time window."""
        st = _parse_datetime(start_time)
        et = _parse_datetime(end_time)

        window_graph = TemporalGraph(config=self.config)
        for u, v, k, data in self.graph.edges(keys=True, data=True):
            edge_ts_raw = data.get("timestamp")
            if not edge_ts_raw:
                continue
            edge_dt = _parse_datetime(edge_ts_raw)
            if st <= edge_dt <= et:
                window_graph.graph.add_edge(u, v, key=k, **data)

        return window_graph

    def get_snapshot_at_time(
        self,
        timestamp: Union[str, datetime.datetime],
        window_minutes: int = 60
    ) -> "TemporalGraph":
        """Return subgraph of transactions within a symmetrical window around timestamp."""
        center_dt = _parse_datetime(timestamp)
        half_delta = datetime.timedelta(minutes=window_minutes / 2.0)
        start_time = center_dt - half_delta
        end_time = center_dt + half_delta
        return self.get_temporal_window(start_time, end_time)

    def get_transaction_sequence(self, node_hash: str) -> List[Dict[str, Any]]:
        """Return chronological list of all transactions involving this node."""
        edges = self.get_edges_for_node(node_hash)
        edges.sort(key=lambda e: _parse_datetime(e.get("timestamp", "")))
        return edges

    def get_component_stats(self) -> Dict[str, Any]:
        """Return component-level topology statistics."""
        node_cnt = self.get_node_count()
        edge_cnt = self.get_edge_count()
        if node_cnt == 0:
            return {
                "node_count": 0,
                "edge_count": 0,
                "avg_degree": 0.0,
                "density": 0.0,
                "component_count": 0
            }

        undirected = self.graph.to_undirected(as_view=True)
        components = list(nx.connected_components(undirected))
        component_cnt = len(components)
        avg_deg = (2.0 * edge_cnt) / node_cnt if node_cnt > 0 else 0.0
        density = nx.density(self.graph) if node_cnt > 1 else 0.0

        return {
            "node_count": node_cnt,
            "edge_count": edge_cnt,
            "avg_degree": round(avg_deg, 4),
            "density": round(density, 6),
            "component_count": component_cnt
        }

    def get_graph_stats(self) -> Dict[str, Any]:
        """Return comprehensive graph metrics for monitoring and dashboard display."""
        node_cnt = self.get_node_count()
        edge_cnt = self.get_edge_count()
        if node_cnt == 0:
            return {
                "node_count": 0,
                "edge_count": 0,
                "avg_degree": 0.0,
                "density": 0.0,
                "is_connected": False,
                "component_count": 0,
                "avg_shortest_path_length": 0.0,
                "nodes": [],
                "edges_by_bank": {}
            }

        undirected = self.graph.to_undirected(as_view=True)
        components = list(nx.connected_components(undirected))
        component_cnt = len(components)
        is_connected = (component_cnt == 1) if node_cnt > 0 else False
        avg_deg = (2.0 * edge_cnt) / node_cnt if node_cnt > 0 else 0.0
        density = nx.density(self.graph) if node_cnt > 1 else 0.0

        path_lengths: List[float] = []
        for comp in components:
            if 1 < len(comp) <= 200:
                sub = self.graph.subgraph(comp)
                try:
                    for s in list(sub.nodes()):
                        lengths = nx.single_source_shortest_path_length(sub, s)
                        for t, l in lengths.items():
                            if s != t:
                                path_lengths.append(l)
                except Exception:
                    pass

        avg_path_length = round(sum(path_lengths) / len(path_lengths), 2) if path_lengths else 0.0

        edges_by_bank: Dict[str, int] = {}
        for _, _, data in self.graph.edges(data=True):
            b_id = data.get("bank_id", "UNKNOWN")
            edges_by_bank[b_id] = edges_by_bank.get(b_id, 0) + 1

        return {
            "node_count": node_cnt,
            "edge_count": edge_cnt,
            "avg_degree": round(avg_deg, 4),
            "density": round(density, 6),
            "is_connected": is_connected,
            "component_count": component_cnt,
            "avg_shortest_path_length": avg_path_length,
            "nodes": self.get_nodes(),
            "edges_by_bank": edges_by_bank
        }

    def to_json(self) -> str:
        """Serialize graph to JSON preserving all node and edge metadata."""
        data = json_graph.node_link_data(self.graph, edges="edges")
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_data: Union[str, Dict[str, Any]], config: Optional[Settings] = None) -> "TemporalGraph":
        """Reconstruct TemporalGraph from JSON string or dictionary."""
        if isinstance(json_data, str):
            data = json.loads(json_data)
        else:
            data = json_data

        tg = cls(config=config)
        tg.graph = json_graph.node_link_graph(data, directed=True, multigraph=True, edges="edges")
        return tg


class GraphEngine:
    """Singleton/Manager for real-time graph state, caching, and database synchronization."""

    _instance = None

    def __init__(
        self,
        temporal_graph_or_config: Optional[Union[TemporalGraph, Settings]] = None,
        config: Optional[Settings] = None
    ):
        if isinstance(temporal_graph_or_config, TemporalGraph):
            self.temporal_graph = temporal_graph_or_config
            self.config = config or settings
        else:
            self.config = temporal_graph_or_config or config or settings
            self.temporal_graph = TemporalGraph(config=self.config)

    @classmethod
    def get_instance(cls, config: Optional[Settings] = None) -> "GraphEngine":
        """Get or initialize singleton instance of GraphEngine."""
        if cls._instance is None:
            cls._instance = cls(config=config)
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """Reset the singleton instance (useful in testing)."""
        cls._instance = None

    def get_graph(self) -> TemporalGraph:
        """Return the current active TemporalGraph instance."""
        return self.temporal_graph

    def extract_subgraphs(self, max_size: int = 50, min_risk: float = 0.0, min_nodes: int = 1) -> List[nx.MultiDiGraph]:
        """Extract weakly connected subgraphs from the active temporal graph."""
        if self.temporal_graph.node_count == 0:
            return []
        undirected = self.temporal_graph.graph.to_undirected(as_view=True)
        components = list(nx.connected_components(undirected))
        subgraphs = []
        for comp in components:
            if len(comp) < min_nodes:
                continue
            if len(comp) <= max_size:
                sub = self.temporal_graph.graph.subgraph(comp).copy()
                subgraphs.append(sub)
            else:
                sub = self.temporal_graph.graph.subgraph(list(comp)[:max_size]).copy()
                subgraphs.append(sub)
        return subgraphs if subgraphs else [self.temporal_graph.graph.copy()]

    extract_connected_components = extract_subgraphs



    def ingest_edge(


        self,
        sender_hash: str,
        receiver_hash: str,
        amount: float,
        timestamp: Union[str, datetime.datetime],
        bank_id: str,
        local_risk_score: float = 0.0,
        is_interbank: bool = True
    ) -> int:
        """Ingest a single transaction edge into active graph."""
        return self.temporal_graph.add_edge(
            sender_hash=sender_hash,
            receiver_hash=receiver_hash,
            amount=amount,
            timestamp=timestamp,
            bank_id=bank_id,
            local_risk_score=local_risk_score,
            is_interbank=is_interbank
        )

    def ingest_batch(self, edges: List[Dict[str, Any]]) -> int:
        """Ingest batch of transactions into active graph."""
        return self.temporal_graph.add_edges_batch(edges)

    def reload_from_db(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        db_path: Optional[str] = None
    ) -> int:
        """Clear and rebuild graph from database."""
        self.temporal_graph = TemporalGraph(config=self.config)
        return self.temporal_graph.build_from_db(start_time=start_time, end_time=end_time, db_path=db_path)

    def save_snapshot(self, db_path: Optional[str] = None) -> Dict[str, Any]:
        """Serialize current graph state and persist as snapshot record in database."""
        serialized = self.temporal_graph.to_json()
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        snapshot = GraphSnapshotRepository.save(
            snapshot_time=now_iso,
            node_count=self.temporal_graph.get_node_count(),
            edge_count=self.temporal_graph.get_edge_count(),
            serialized_graph=serialized,
            db_path=db_path
        )
        return snapshot


# Default global instance
graph_engine = GraphEngine.get_instance()

