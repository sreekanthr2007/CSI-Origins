"""Repository classes for SQLite database entities in Cross-Bank Mule Detection."""
import json
import logging
import datetime
from typing import Dict, Any, List, Optional
from backend.app.database.connection import get_db

logger = logging.getLogger("mule-detection-database")


def _row_to_dict(row) -> Optional[Dict[str, Any]]:
    """Convert SQLite Row to dictionary."""
    if row is None:
        return None
    return dict(row)


def _json_serialize(val: Any) -> str:
    """Safely serialize value to JSON string."""
    if isinstance(val, str):
        return val
    return json.dumps(val)


def _json_deserialize(val: Optional[str]) -> Any:
    """Safely parse JSON string into Python structure."""
    if not val:
        return None
    try:
        return json.loads(val)
    except Exception:
        return val


# ---------------------------------------------------------------------------
# Bank Repository
# ---------------------------------------------------------------------------
class BankRepository:
    """Data access repository for Bank entities."""

    @staticmethod
    def create(bank_name: str, ifsc_prefix: str, public_key_fingerprint: Optional[str] = None, db_path: Optional[str] = None) -> Dict[str, Any]:
        """Create a new bank record and return the inserted bank dictionary."""
        with get_db(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO banks (bank_name, ifsc_prefix, public_key_fingerprint)
                VALUES (?, ?, ?)
                RETURNING *;
                """,
                (bank_name, ifsc_prefix.upper(), public_key_fingerprint)
            )
            row = cursor.fetchone()
            conn.commit()
            return _row_to_dict(row)

    @staticmethod
    def get_by_id(bank_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieve bank by primary key ID."""
        with get_db(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM banks WHERE id = ?;", (bank_id,))
            return _row_to_dict(cursor.fetchone())

    @staticmethod
    def get_by_ifsc_prefix(prefix: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieve bank by unique IFSC prefix (e.g. SBIN)."""
        with get_db(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM banks WHERE ifsc_prefix = ?;", (prefix.upper(),))
            return _row_to_dict(cursor.fetchone())

    @staticmethod
    def get_all(active_only: bool = True, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve all banks, optionally filtering by active status."""
        with get_db(db_path) as conn:
            cursor = conn.cursor()
            if active_only:
                cursor.execute("SELECT * FROM banks WHERE is_active = 1 ORDER BY bank_name ASC;")
            else:
                cursor.execute("SELECT * FROM banks ORDER BY bank_name ASC;")
            return [_row_to_dict(r) for r in cursor.fetchall()]

    @staticmethod
    def update(bank_id: str, db_path: Optional[str] = None, **kwargs) -> Optional[Dict[str, Any]]:
        """Update fields on a bank record."""
        if not kwargs:
            return BankRepository.get_by_id(bank_id, db_path)

        fields = []
        values = []
        for k, v in kwargs.items():
            fields.append(f"{k} = ?")
            values.append(v)
        fields.append("updated_at = CURRENT_TIMESTAMP")
        values.append(bank_id)

        query = f"UPDATE banks SET {', '.join(fields)} WHERE id = ? RETURNING *;"
        with get_db(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(values))
            row = cursor.fetchone()
            conn.commit()
            return _row_to_dict(row)

    @staticmethod
    def delete(bank_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Soft delete bank by setting is_active = 0."""
        return BankRepository.update(bank_id, db_path, is_active=0)


# ---------------------------------------------------------------------------
# Edge Repository
# ---------------------------------------------------------------------------
class EdgeRepository:
    """Data access repository for hashed transaction edges."""

    @staticmethod
    def batch_insert(edges: List[Dict[str, Any]], db_path: Optional[str] = None) -> int:
        """Accept a list of edge dicts and insert them efficiently in a single transaction."""
        if not edges:
            return 0

        rows = []
        for e in edges:
            rows.append((
                e.get("sender_hash"),
                e.get("receiver_hash"),
                float(e.get("amount", 0.0)),
                e.get("timestamp"),
                e.get("bank_id"),
                float(e.get("local_risk_score", 0.0)) if e.get("local_risk_score") is not None else 0.0,
                1 if e.get("is_interbank", True) else 0
            ))

        with get_db(db_path) as conn:
            cursor = conn.cursor()
            cursor.executemany(
                """
                INSERT INTO hashed_edges 
                (sender_hash, receiver_hash, amount, timestamp, bank_id, local_risk_score, is_interbank)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                rows
            )
            count = cursor.rowcount
            conn.commit()
            return count

    @staticmethod
    def get_edges_in_time_range(start_ts: str, end_ts: str, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return all edges with timestamp between start_ts and end_ts inclusive."""
        with get_db(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM hashed_edges 
                WHERE timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp ASC;
                """,
                (start_ts, end_ts)
            )
            return [_row_to_dict(r) for r in cursor.fetchall()]

    @staticmethod
    def get_edges_for_node(node_hash: str, limit: int = 100, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return edges where sender_hash OR receiver_hash matches node_hash."""
        with get_db(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM hashed_edges 
                WHERE sender_hash = ? OR receiver_hash = ?
                ORDER BY timestamp DESC
                LIMIT ?;
                """,
                (node_hash, node_hash, limit)
            )
            return [_row_to_dict(r) for r in cursor.fetchall()]

    @staticmethod
    def get_edges_by_bank(bank_id: str, limit: int = 100, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return edges submitted by a specific bank."""
        with get_db(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM hashed_edges WHERE bank_id = ? ORDER BY timestamp DESC LIMIT ?;",
                (bank_id, limit)
            )
            return [_row_to_dict(r) for r in cursor.fetchall()]

    @staticmethod
    def count_edges_between(sender_hash: str, receiver_hash: str, db_path: Optional[str] = None) -> int:
        """Count historical edges between two nodes (used for first-time edge anomaly detection)."""
        with get_db(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) AS total FROM hashed_edges WHERE sender_hash = ? AND receiver_hash = ?;",
                (sender_hash, receiver_hash)
            )
            row = cursor.fetchone()
            return row["total"] if row else 0

    @staticmethod
    def get_edges_for_component(node_hashes: List[str], db_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return all edges where sender OR receiver is in the provided node_hashes list."""
        if not node_hashes:
            return []

        placeholders = ",".join("?" for _ in node_hashes)
        params = list(node_hashes) + list(node_hashes)
        query = f"""
            SELECT * FROM hashed_edges 
            WHERE sender_hash IN ({placeholders}) OR receiver_hash IN ({placeholders})
            ORDER BY timestamp ASC;
        """
        with get_db(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [_row_to_dict(r) for r in cursor.fetchall()]


# ---------------------------------------------------------------------------
# Component Repository
# ---------------------------------------------------------------------------
class ComponentRepository:
    """Data access repository for detected mule graph components."""

    @staticmethod
    def save(component_data: Dict[str, Any], db_path: Optional[str] = None) -> Dict[str, Any]:
        """Save a detected component, serializing nested JSON attributes."""
        detection_time = component_data.get("detection_time", datetime.datetime.now(datetime.timezone.utc).isoformat())
        risk_score = float(component_data.get("risk_score", 0.0))
        hashed_nodes = _json_serialize(component_data.get("hashed_nodes", []))
        bank_ids = _json_serialize(component_data.get("bank_ids", []))
        feature_vector = _json_serialize(component_data.get("feature_vector", {}))
        shap_explanation = _json_serialize(component_data.get("shap_explanation", {}))
        status = component_data.get("status", "active")
        alert_id = component_data.get("alert_id")

        with get_db(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO components 
                (detection_time, risk_score, hashed_nodes, bank_ids, feature_vector, shap_explanation, status, alert_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING *;
                """,
                (detection_time, risk_score, hashed_nodes, bank_ids, feature_vector, shap_explanation, status, alert_id)
            )
            row = cursor.fetchone()
            conn.commit()
            res = _row_to_dict(row)
            if res:
                res["hashed_nodes"] = _json_deserialize(res["hashed_nodes"])
                res["bank_ids"] = _json_deserialize(res["bank_ids"])
                res["feature_vector"] = _json_deserialize(res["feature_vector"])
                res["shap_explanation"] = _json_deserialize(res["shap_explanation"])
            return res

    @staticmethod
    def get_by_id(component_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieve component by ID, deserializing JSON fields."""
        with get_db(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM components WHERE id = ?;", (component_id,))
            res = _row_to_dict(cursor.fetchone())
            if res:
                res["hashed_nodes"] = _json_deserialize(res["hashed_nodes"])
                res["bank_ids"] = _json_deserialize(res["bank_ids"])
                res["feature_vector"] = _json_deserialize(res["feature_vector"])
                res["shap_explanation"] = _json_deserialize(res["shap_explanation"])
            return res

    @staticmethod
    def list_recent(limit: int = 50, min_risk_score: Optional[float] = None, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """List recent detected components with optional minimum risk score filter."""
        with get_db(db_path) as conn:
            cursor = conn.cursor()
            if min_risk_score is not None:
                cursor.execute(
                    "SELECT * FROM components WHERE risk_score >= ? ORDER BY detection_time DESC LIMIT ?;",
                    (min_risk_score, limit)
                )
            else:
                cursor.execute(
                    "SELECT * FROM components ORDER BY detection_time DESC LIMIT ?;",
                    (limit,)
                )
            rows = cursor.fetchall()
            results = []
            for r in rows:
                item = _row_to_dict(r)
                item["hashed_nodes"] = _json_deserialize(item["hashed_nodes"])
                item["bank_ids"] = _json_deserialize(item["bank_ids"])
                item["feature_vector"] = _json_deserialize(item["feature_vector"])
                item["shap_explanation"] = _json_deserialize(item["shap_explanation"])
                results.append(item)
            return results

    @staticmethod
    def update_status(component_id: str, status: str, alert_id: Optional[str] = None, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Update status and optionally link an alert ID."""
        with get_db(db_path) as conn:
            cursor = conn.cursor()
            if alert_id:
                cursor.execute(
                    "UPDATE components SET status = ?, alert_id = ? WHERE id = ? RETURNING *;",
                    (status, alert_id, component_id)
                )
            else:
                cursor.execute(
                    "UPDATE components SET status = ? WHERE id = ? RETURNING *;",
                    (status, component_id)
                )
            row = cursor.fetchone()
            conn.commit()
            res = _row_to_dict(row)
            if res:
                res["hashed_nodes"] = _json_deserialize(res["hashed_nodes"])
                res["bank_ids"] = _json_deserialize(res["bank_ids"])
                res["feature_vector"] = _json_deserialize(res["feature_vector"])
                res["shap_explanation"] = _json_deserialize(res["shap_explanation"])
            return res

    @staticmethod
    def get_by_node_hash(node_hash: str, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """Find components that contain the specified node hash."""
        with get_db(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM components WHERE hashed_nodes LIKE ? ORDER BY detection_time DESC;",
                (f"%{node_hash}%",)
            )
            rows = cursor.fetchall()
            results = []
            for r in rows:
                item = _row_to_dict(r)
                item["hashed_nodes"] = _json_deserialize(item["hashed_nodes"])
                item["bank_ids"] = _json_deserialize(item["bank_ids"])
                item["feature_vector"] = _json_deserialize(item["feature_vector"])
                item["shap_explanation"] = _json_deserialize(item["shap_explanation"])
                if isinstance(item["hashed_nodes"], list) and node_hash in item["hashed_nodes"]:
                    results.append(item)
            return results

    @staticmethod
    def get_active_components(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return components currently in 'active' or 'investigating' state."""
        with get_db(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM components WHERE status IN ('active', 'investigating') ORDER BY risk_score DESC;"
            )
            rows = cursor.fetchall()
            results = []
            for r in rows:
                item = _row_to_dict(r)
                item["hashed_nodes"] = _json_deserialize(item["hashed_nodes"])
                item["bank_ids"] = _json_deserialize(item["bank_ids"])
                item["feature_vector"] = _json_deserialize(item["feature_vector"])
                item["shap_explanation"] = _json_deserialize(item["shap_explanation"])
                results.append(item)
            return results


# ---------------------------------------------------------------------------
# Investigation Repository (Flow B)
# ---------------------------------------------------------------------------
class InvestigationRepository:
    """Data access repository for Flow B investigations."""

    @staticmethod
    def create(component_id: str, investigation_salt: str, banks_queried: Optional[List[str]] = None, db_path: Optional[str] = None) -> Dict[str, Any]:
        """Create a new investigation session with ephemeral salt."""
        banks_json = _json_serialize(banks_queried or [])
        with get_db(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO investigations (component_id, investigation_salt, banks_queried, traversal_path, status)
                VALUES (?, ?, ?, '[]', 'active')
                RETURNING *;
                """,
                (component_id, investigation_salt, banks_json)
            )
            row = cursor.fetchone()
            conn.commit()
            res = _row_to_dict(row)
            if res:
                res["banks_queried"] = _json_deserialize(res["banks_queried"])
                res["traversal_path"] = _json_deserialize(res["traversal_path"])
            return res

    @staticmethod
    def get_by_id(investigation_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieve investigation by ID."""
        with get_db(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM investigations WHERE id = ?;", (investigation_id,))
            res = _row_to_dict(cursor.fetchone())
            if res:
                res["banks_queried"] = _json_deserialize(res["banks_queried"])
                res["traversal_path"] = _json_deserialize(res["traversal_path"])
            return res

    @staticmethod
    def update(investigation_id: str, db_path: Optional[str] = None, **kwargs) -> Optional[Dict[str, Any]]:
        """Update fields on an investigation record."""
        if not kwargs:
            return InvestigationRepository.get_by_id(investigation_id, db_path)

        fields = []
        values = []
        for k, v in kwargs.items():
            if k in ("banks_queried", "traversal_path"):
                v = _json_serialize(v)
            fields.append(f"{k} = ?")
            values.append(v)
        values.append(investigation_id)

        query = f"UPDATE investigations SET {', '.join(fields)} WHERE id = ? RETURNING *;"
        with get_db(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(values))
            row = cursor.fetchone()
            conn.commit()
            res = _row_to_dict(row)
            if res:
                res["banks_queried"] = _json_deserialize(res["banks_queried"])
                res["traversal_path"] = _json_deserialize(res["traversal_path"])
            return res

    @staticmethod
    def close_investigation(investigation_id: str, closed_by: str, status: str = "closed", db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Close an investigation and record the closure reason."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return InvestigationRepository.update(
            investigation_id,
            db_path,
            status=status,
            closed_by=closed_by,
            completed_at=now
        )

    @staticmethod
    def get_by_component(component_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieve most recent investigation for a component."""
        with get_db(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM investigations WHERE component_id = ? ORDER BY started_at DESC LIMIT 1;",
                (component_id,)
            )
            res = _row_to_dict(cursor.fetchone())
            if res:
                res["banks_queried"] = _json_deserialize(res["banks_queried"])
                res["traversal_path"] = _json_deserialize(res["traversal_path"])
            return res

    @staticmethod
    def get_active_investigations(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return all investigations currently active."""
        with get_db(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM investigations WHERE status = 'active' ORDER BY started_at DESC;")
            rows = cursor.fetchall()
            results = []
            for r in rows:
                item = _row_to_dict(r)
                item["banks_queried"] = _json_deserialize(item["banks_queried"])
                item["traversal_path"] = _json_deserialize(item["traversal_path"])
                results.append(item)
            return results


# ---------------------------------------------------------------------------
# Alert Repository
# ---------------------------------------------------------------------------
class AlertRepository:
    """Data access repository for cross-bank alert dispatches."""

    @staticmethod
    def create(component_id: str, severity: str, dispatched_to: List[str], db_path: Optional[str] = None) -> Dict[str, Any]:
        """Create and record an alert dispatch."""
        dispatched_json = _json_serialize(dispatched_to)
        with get_db(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO alerts (component_id, severity, dispatched_to, resolution_status)
                VALUES (?, ?, ?, 'pending')
                RETURNING *;
                """,
                (component_id, severity.lower(), dispatched_json)
            )
            row = cursor.fetchone()
            conn.commit()
            res = _row_to_dict(row)
            if res:
                res["dispatched_to"] = _json_deserialize(res["dispatched_to"])
            return res

    @staticmethod
    def get_by_id(alert_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieve alert by ID."""
        with get_db(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM alerts WHERE id = ?;", (alert_id,))
            res = _row_to_dict(cursor.fetchone())
            if res:
                res["dispatched_to"] = _json_deserialize(res["dispatched_to"])
            return res

    @staticmethod
    def update_status(alert_id: str, status: str, resolved_at: Optional[str] = None, notes: Optional[str] = None, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Update resolution status of an alert."""
        with get_db(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE alerts 
                SET resolution_status = ?, resolved_at = ?, resolution_notes = ?
                WHERE id = ?
                RETURNING *;
                """,
                (status.lower(), resolved_at, notes, alert_id)
            )
            row = cursor.fetchone()
            conn.commit()
            res = _row_to_dict(row)
            if res:
                res["dispatched_to"] = _json_deserialize(res["dispatched_to"])
            return res

    @staticmethod
    def get_by_component(component_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieve alert by associated component ID."""
        with get_db(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM alerts WHERE component_id = ? ORDER BY dispatch_time DESC LIMIT 1;", (component_id,))
            res = _row_to_dict(cursor.fetchone())
            if res:
                res["dispatched_to"] = _json_deserialize(res["dispatched_to"])
            return res

    @staticmethod
    def get_pending_alerts(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return all pending alerts."""
        with get_db(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM alerts WHERE resolution_status = 'pending' ORDER BY dispatch_time DESC;")
            rows = cursor.fetchall()
            results = []
            for r in rows:
                item = _row_to_dict(r)
                item["dispatched_to"] = _json_deserialize(item["dispatched_to"])
                results.append(item)
            return results

    @staticmethod
    def get_by_bank(bank_id: str, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return alerts where bank_id is in dispatched_to list."""
        with get_db(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM alerts WHERE dispatched_to LIKE ? ORDER BY dispatch_time DESC;", (f"%{bank_id}%",))
            rows = cursor.fetchall()
            results = []
            for r in rows:
                item = _row_to_dict(r)
                item["dispatched_to"] = _json_deserialize(item["dispatched_to"])
                if isinstance(item["dispatched_to"], list) and bank_id in item["dispatched_to"]:
                    results.append(item)
            return results


# ---------------------------------------------------------------------------
# STR Repository (Regulatory Reports)
# ---------------------------------------------------------------------------
class STRRepository:
    """Data access repository for Suspicious Transaction Reports (STRs)."""

    @staticmethod
    def create(alert_id: str, bank_id: str, report_payload: Dict[str, Any], db_path: Optional[str] = None) -> Dict[str, Any]:
        """Create and store an STR report."""
        payload_json = _json_serialize(report_payload)
        with get_db(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO str_reports (alert_id, bank_id, report_payload, filed_status)
                VALUES (?, ?, ?, 'draft')
                RETURNING *;
                """,
                (alert_id, bank_id, payload_json)
            )
            row = cursor.fetchone()
            conn.commit()
            res = _row_to_dict(row)
            if res:
                res["report_payload"] = _json_deserialize(res["report_payload"])
            return res

    @staticmethod
    def get_by_id(str_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieve STR report by ID."""
        with get_db(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM str_reports WHERE id = ?;", (str_id,))
            res = _row_to_dict(cursor.fetchone())
            if res:
                res["report_payload"] = _json_deserialize(res["report_payload"])
            return res

    @staticmethod
    def get_by_alert(alert_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieve STR report by alert ID."""
        with get_db(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM str_reports WHERE alert_id = ? ORDER BY generated_at DESC LIMIT 1;", (alert_id,))
            res = _row_to_dict(cursor.fetchone())
            if res:
                res["report_payload"] = _json_deserialize(res["report_payload"])
            return res

    @staticmethod
    def update_status(str_id: str, filed_status: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Update filed status ('draft', 'submitted', 'accepted')."""
        with get_db(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE str_reports SET filed_status = ? WHERE id = ? RETURNING *;",
                (filed_status.lower(), str_id)
            )
            row = cursor.fetchone()
            conn.commit()
            res = _row_to_dict(row)
            if res:
                res["report_payload"] = _json_deserialize(res["report_payload"])
            return res

    @staticmethod
    def generate_str_payload(account_details: Dict[str, Any], component_data: Dict[str, Any]) -> Dict[str, Any]:
        """Helper to format a complete STR payload for regulatory submission."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return {
            "regulatory_agency": "FIU-IND / IDPIC",
            "generation_timestamp": now,
            "account_details": account_details,
            "fraud_indicators": {
                "risk_score": component_data.get("risk_score"),
                "detected_pattern": component_data.get("pattern_type", "RAPID_CHAIN"),
                "top_drivers": component_data.get("top_drivers", []),
                "nodes_in_ring": len(component_data.get("hashed_nodes", [])),
                "banks_involved": component_data.get("bank_ids", [])
            },
            "compliance_officer_review": {
                "action_recommended": "DEBIT_FREEZE",
                "status": "READY_FOR_FILING"
            }
        }
