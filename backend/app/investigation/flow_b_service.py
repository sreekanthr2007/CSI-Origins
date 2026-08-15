"""Flow B targeted investigation orchestration service with cryptographic lifecycle management."""
import logging
from typing import Dict, Any, List, Optional, Union

from backend.app.config import settings, Settings
from backend.app.graph.graph_engine import TemporalGraph, graph_engine
from backend.app.privacy.hashing import (
    generate_investigation_salt,
    encrypt_salt,
    decrypt_salt,
    hash_for_investigation,
)
from backend.app.privacy.bank_vault import BANK_VAULTS
from backend.app.database.repositories import InvestigationRepository
from backend.app.investigation.traversal import PatternDecayTraversal, TraversalResult

logger = logging.getLogger("mule-detection-flow-b-service")


class InvestigationHandle(str):
    """Wrapper supporting both string/attribute and dictionary access for investigation results."""
    def __new__(cls, inv_id: str, status: str = "completed", depth_reached: int = 0, traversal_result: Any = None):
        obj = super().__new__(cls, str(inv_id))
        obj.id = str(inv_id)
        obj.status = status
        obj.depth_reached = depth_reached
        obj.traversal_result = traversal_result
        obj.stopping_reason = getattr(traversal_result, "stopping_reason", "completed") if traversal_result else "completed"
        return obj

    def __getitem__(self, item):
        if item == "id":
            return self.id
        if item == "status":
            return self.status
        if item == "depth_reached":
            return self.depth_reached
        if item == "stopping_reason":
            return self.stopping_reason
        return getattr(self, item, None)

    def __repr__(self):
        return f"<InvestigationHandle id={self.id} status={self.status} depth={self.depth_reached}>"




class FlowBService:
    """Orchestrates Flow B on-demand targeted investigations, bank neighborhood queries, and ephemeral cryptographic lifecycle."""

    def __init__(
        self,
        graph: Optional[Any] = None,
        bank_registry: Optional[Any] = None,
        config: Optional[Settings] = None,
        *args,
        **kwargs
    ):
        if isinstance(graph, Settings):
            self.config = graph
            self.graph = bank_registry if isinstance(bank_registry, TemporalGraph) else graph_engine.get_graph()
        else:
            self.config = config or settings
            self.graph = graph if isinstance(graph, TemporalGraph) else (bank_registry if isinstance(bank_registry, TemporalGraph) else graph_engine.get_graph())
        self.bank_registry = bank_registry
        self.traversal_engine = PatternDecayTraversal(graph=self.graph, config=self.config)

    def start_investigation(
        self,
        node_hash: Optional[str] = None,
        component_id: Optional[str] = None,
        start_node: Optional[str] = None,
        **kwargs
    ) -> InvestigationHandle:
        """Initialize a targeted investigation session with an encrypted ephemeral salt and execute bounded traversal."""
        target_node = node_hash or start_node or kwargs.get("start_node") or ""
        c_id = component_id or "adhoc_investigation"
        salt = generate_investigation_salt()
        encrypted_salt = encrypt_salt(salt)

        # 1. Create database record
        rec = InvestigationRepository.create(
            component_id=c_id,
            investigation_salt=encrypted_salt
        )
        investigation_id = rec["id"]
        logger.info(f"Started investigation {investigation_id} for target node {target_node}")

        # 2. Run initial bounded graph traversal
        result = self.traversal_engine.traverse_from_node(target_node)

        # 3. Persist traversal checkpoint
        InvestigationRepository.update_traversal_state(
            investigation_id=investigation_id,
            depth_reached=result.depth_reached,
            banks_queried=result.banks_queried,
            traversal_path=result.to_dict(),
            status="completed"
        )

        return InvestigationHandle(
            inv_id=investigation_id,
            status="completed",
            depth_reached=result.depth_reached,
            traversal_result=result
        )


    def request_neighborhood_from_bank(
        self,
        node_hash: str,
        bank_id: str,
        ephemeral_salt: str
    ) -> List[Dict[str, Any]]:
        """Simulate secure, ephemeral-hashed neighborhood discovery query to a participating bank."""
        logger.info(f"Querying neighborhood for {node_hash} from bank {bank_id}")
        results: List[Dict[str, Any]] = []

        # Lookup in bank vault if local simulated bank
        if bank_id in BANK_VAULTS:
            vault = BANK_VAULTS[bank_id]
            resolved = vault.resolve_standing_hash(node_hash)
            if resolved:
                acc_num = resolved["account_number"]
                inv_hash = hash_for_investigation(acc_num, bank_id, ephemeral_salt)
                results.append({
                    "investigation_hash": inv_hash,
                    "bank_id": bank_id,
                    "account_type": resolved.get("account_type", "SAVINGS"),
                    "local_risk_score": resolved.get("local_risk_score", 0.10)
                })

        # Also pull edges connected to node in that bank from graph
        for _, _, data in self.graph.graph.edges(node_hash, data=True):
            if data.get("bank_id") == bank_id:
                results.append({
                    "from": data.get("sender_hash", node_hash),
                    "to": data.get("receiver_hash"),
                    "amount": data.get("amount"),
                    "timestamp": data.get("timestamp"),
                    "bank_id": bank_id
                })

        return results

    def close_investigation(
        self,
        investigation_id: str,
        closed_by: str = "human_review"
    ) -> Dict[str, Any]:
        """Close investigation and permanently delete and overwrite ephemeral salt."""
        updated = InvestigationRepository.close(investigation_id, closed_by=closed_by)
        if not updated:
            raise ValueError(f"Investigation {investigation_id} not found")

        logger.info(f"Closed investigation {investigation_id} and destroyed ephemeral salt (closed by: {closed_by})")
        return {
            "status": "closed",
            "closed_by": closed_by,
            "investigation_id": investigation_id
        }

    def delete_investigation(self, investigation_id: str) -> Dict[str, Any]:
        """Permanently purge investigation record from database."""
        success = InvestigationRepository.delete(investigation_id)
        if not success:
            raise ValueError(f"Investigation {investigation_id} not found")
        return {
            "status": "deleted",
            "investigation_id": investigation_id,
            "salt_destroyed": True
        }

    def get_status(self, investigation_id: str) -> Dict[str, Any]:
        """Retrieve operational progress status of an investigation."""
        rec = InvestigationRepository.get_by_id(investigation_id)
        if not rec:
            raise ValueError(f"Investigation {investigation_id} not found")

        return {
            "investigation_id": rec["id"],
            "status": rec.get("status", "active"),
            "component_id": rec.get("component_id"),
            "depth_reached": rec.get("depth_reached", 0),
            "banks_queried": rec.get("banks_queried", []),
            "started_at": rec.get("started_at"),
            "completed_at": rec.get("completed_at"),
            "closed_by": rec.get("closed_by")
        }

    def get_investigation_result(self, investigation_id: str) -> Dict[str, Any]:
        """Retrieve full investigation state and status."""
        return self.get_status(investigation_id)

    def get_result(self, investigation_id: str) -> Dict[str, Any]:

        """Retrieve full traversal result payload."""
        rec = InvestigationRepository.get_by_id(investigation_id)
        if not rec:
            raise ValueError(f"Investigation {investigation_id} not found")

        path_data = rec.get("traversal_path") or {}
        return path_data

    def get_playback(self, investigation_id: str) -> List[Dict[str, Any]]:
        """Generate animated step-by-step traversal playback trace for investigator frontend."""
        rec = InvestigationRepository.get_by_id(investigation_id)
        if not rec:
            raise ValueError(f"Investigation {investigation_id} not found")

        path_data = rec.get("traversal_path") or {}
        edges = path_data.get("edges_visited", [])
        start_node = path_data.get("start_node", "UNKNOWN")
        stopping_reason = path_data.get("stopping_reason", "completed")
        stopping_at_edge = path_data.get("stopping_at_edge")

        steps: List[Dict[str, Any]] = []
        steps.append({
            "step_number": 1,
            "action": "START",
            "node": start_node,
            "description": f"Initialized investigation from target node {start_node}",
            "decision": "ACCEPT"
        })

        step_idx = 2
        for e in edges:
            dir_label = e.get("direction", "downstream")
            amt = e.get("amount", 0.0)
            bank = e.get("bank_id", "UNKNOWN")
            steps.append({
                "step_number": step_idx,
                "action": f"EXPAND_{dir_label.upper()}",
                "from": e.get("from"),
                "to": e.get("to"),
                "bank_id": bank,
                "amount": amt,
                "description": f"Expanded {dir_label} to {e.get('to')} via {bank} (Amount: INR {amt:,.2f})",
                "decision": "ACCEPT"
            })
            step_idx += 1

        # Add termination step if stopped by pattern decay or rule
        if stopping_at_edge:
            steps.append({
                "step_number": step_idx,
                "action": "HALT_TRAVERSAL",
                "from": stopping_at_edge.get("from"),
                "to": stopping_at_edge.get("to"),
                "reason": stopping_reason,
                "description": f"Traversal halted at edge {stopping_at_edge.get('from')} -> {stopping_at_edge.get('to')} due to {stopping_reason}",
                "decision": "REJECT"
            })
        else:
            steps.append({
                "step_number": step_idx,
                "action": "COMPLETE_TRAVERSAL",
                "reason": stopping_reason,
                "description": f"Traversal completed with stopping reason: {stopping_reason}",
                "decision": "DONE"
            })

        return steps

    get_playback_steps = get_playback

    def list_active_investigations(self) -> List[Dict[str, Any]]:

        """List all active and in-progress investigations."""
        return InvestigationRepository.list_active()

    def cleanup_stale_investigations(self, max_age_hours: int = 24) -> int:
        """Find and automatically close stale investigations, destroying expired salts."""
        stale = InvestigationRepository.get_stale(max_age_hours=max_age_hours)
        count = 0
        for item in stale:
            try:
                self.close_investigation(item["id"], closed_by="auto_cleanup")
                count += 1
            except Exception as e:
                logger.error(f"Failed to auto-cleanup investigation {item['id']}: {e}")
        logger.info(f"Cleaned up {count} stale investigations older than {max_age_hours} hours")
        return count
