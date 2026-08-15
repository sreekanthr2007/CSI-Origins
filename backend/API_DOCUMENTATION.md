# TRACE API Reference Documentation

This document provides a comprehensive reference for the REST APIs of **TRACE** (*Targeted Routing & Account Cluster Extraction*).

- **Base URL**: `http://localhost:8000/api/v1` (or `http://localhost/api/v1` when served behind Nginx)
- **Interactive Swagger UI**: `http://localhost:8000/docs`
- **ReDoc OpenAPI Documentation**: `http://localhost:8000/redoc`

---

## Table of Contents
1. [System & Health](#1-system--health)
2. [Privacy & Cryptographic Hashing](#2-privacy--cryptographic-hashing)
3. [Graph Engine & Components](#3-graph-engine--components)
4. [ML Inference & Explainability](#4-ml-inference--explainability)
5. [Flow B Deep Investigation](#5-flow-b-deep-investigation)
6. [Alerts & Dispatcher](#6-alerts--dispatcher)
7. [Bank Node Simulation & Vault](#7-bank-node-simulation--vault)
8. [Compliance & STR Reports](#8-compliance--str-reports)

---

## 1. System & Health

### `GET /health`
Returns system health, database connectivity, and active engine states.

**Response (200 OK):**
```json
{
  "status": "ok",
  "app_name": "TRACE",
  "version": "1.0.0",
  "timestamp": "2026-08-15T12:00:00Z",
  "database": "connected",
  "active_banks_registered": 6
}
```

---

## 2. Privacy & Cryptographic Hashing

### `POST /api/v1/privacy/hash/standing`
Generates a deterministic HMAC-SHA256 standing hash for Flow A continuous topology matching without persisting raw account PII.

**Request:**
```json
{
  "account_number": "40991209384",
  "bank_id": "bank_sbi"
}
```

**Response (200 OK):**
```json
{
  "standing_hash": "HMAC:8f3c7a1098b2c45e67890123456789abcdef",
  "bank_id": "bank_sbi",
  "algorithm": "HMAC-SHA256"
}
```

### `POST /api/v1/privacy/hash/ephemeral`
Derives a session-scoped ephemeral salt and hash for Flow B bounded investigation.

**Request:**
```json
{
  "account_number": "40991209384",
  "bank_id": "bank_sbi",
  "investigation_id": "INV-20260815-998811"
}
```

**Response (200 OK):**
```json
{
  "ephemeral_hash": "EPH:7b1a2c3d4e5f6a7b8c9d0e1f2a3b4c5d",
  "investigation_id": "INV-20260815-998811",
  "expiry": "2026-08-16T12:00:00Z"
}
```

---

## 3. Graph Engine & Components

### `GET /api/v1/graph/stats`
Returns global topology graph statistics (nodes, directed edges, density).

**Response (200 OK):**
```json
{
  "total_nodes": 1250,
  "total_edges": 3480,
  "density": 0.0022,
  "banks_represented": ["bank_sbi", "bank_hdfc", "bank_icici", "bank_axis", "bank_pnb", "bank_yes"]
}
```

### `GET /api/v1/graph/components`
Lists extracted weakly connected subgraph clusters exceeding minimum node thresholds.

**Query Parameters:**
- `min_nodes` (integer, default: 3): Minimum nodes in subgraph cluster.
- `limit` (integer, default: 50): Maximum clusters to return.

**Response (200 OK):**
```json
[
  {
    "id": "comp_9988a1b2",
    "detection_time": "2026-08-15T11:45:00Z",
    "risk_score": 0.92,
    "hashed_nodes": ["HMAC:node1", "HMAC:node2", "HMAC:node3"],
    "bank_ids": ["bank_sbi", "bank_hdfc", "bank_icici"],
    "node_count": 3,
    "edge_count": 2
  }
]
```

---

## 4. ML Inference & Explainability

### `POST /api/v1/ml/predict`
Calculates mule probability for a feature vector or graph component ID.

**Request:**
```json
{
  "component_id": "comp_9988a1b2",
  "features": {
    "pass_through_ratio": 0.98,
    "avg_dwell_time_minutes": 24.5,
    "cross_bank_velocity": 3.8,
    "structuring_score": 0.85
  }
}
```

**Response (200 OK):**
```json
{
  "risk_score": 0.924,
  "is_mule": true,
  "classification": "MULE_RING",
  "confidence": 0.94
}
```

### `GET /api/v1/ml/explain/{component_id}`
Returns decomposed SHAP feature attributions and natural-language narrative for compliance audits.

**Response (200 OK):**
```json
{
  "component_id": "comp_9988a1b2",
  "base_value": 0.12,
  "risk_score": 0.924,
  "shap_values": {
    "pass_through_ratio": 0.42,
    "cross_bank_velocity": 0.28,
    "structuring_score": 0.18,
    "avg_dwell_time_minutes": -0.05
  },
  "summary": "Flagged as mule ring (92% probability) due to 98% pass-through velocity within 25 minutes across 3 banks."
}
```

---

## 5. Flow B Deep Investigation

### `POST /api/v1/investigation/start`
Initiates targeted, bounded pattern-decay graph traversal from a flagged node.

**Request:**
```json
{
  "target_node": "HMAC:8f3c7a1098b2c45e",
  "direction": "both",
  "max_depth": 4,
  "window_hours": 24
}
```

**Response (200 OK):**
```json
{
  "investigation_id": "INV-20260815-4B9F2A",
  "status": "completed",
  "depth_reached": 4,
  "nodes_discovered": 5,
  "banks_queried": ["bank_sbi", "bank_hdfc", "bank_icici", "bank_axis"],
  "stopping_reason": "completed"
}
```

### `GET /api/v1/investigation/{investigation_id}/playback`
Returns sequential step-by-step playback events for interactive timeline visualization in the investigator workbench.

**Response (200 OK):**
```json
[
  {
    "step_number": 1,
    "action": "START",
    "node": "HMAC:8f3c7a1098b2c45e",
    "description": "Initialized investigation on target node",
    "decision": "ACCEPT"
  },
  {
    "step_number": 2,
    "action": "EXPAND_DOWNSTREAM",
    "from": "HMAC:8f3c7a1098b2c45e",
    "to": "HMAC:1a2b3c4d5e6f7a8b",
    "amount": 500000.0,
    "bank_id": "bank_hdfc",
    "description": "Expanded downstream to HDFC node (INR 500,000.00)",
    "decision": "ACCEPT"
  }
]
```

---

## 6. Alerts & Dispatcher

### `POST /api/v1/alerts/dispatch`
Dispatches a verified multi-bank mule alert to all participating bank nodes.

**Request:**
```json
{
  "component_id": "comp_9988a1b2",
  "risk_score": 0.92,
  "explanation": {
    "summary": "Rapid 4-bank pass-through chain detected"
  }
}
```

**Response (200 OK):**
```json
{
  "alert_id": "ALERT-20260815-77A1F9",
  "status": "dispatched",
  "bank_acknowledged": ["bank_sbi", "bank_hdfc", "bank_icici", "bank_axis"],
  "failed_banks": []
}
```

---

## 7. Bank Node Simulation & Vault

### `GET /api/v1/bank/{bank_id}/alerts`
Retrieves incoming alerts addressed to the specific bank compliance team.

**Response (200 OK):**
```json
[
  {
    "id": "ALERT-20260815-77A1F9",
    "risk_score": 0.92,
    "severity": "critical",
    "dispatch_time": "2026-08-15T11:46:12Z",
    "status": "dispatched"
  }
]
```

### `POST /api/v1/bank/{bank_id}/resolve`
Simulates local de-anonymization within the bank's airgapped vault (bank-internal only).

**Request:**
```json
{
  "node_hash": "HMAC:8f3c7a1098b2c45e"
}
```

**Response (200 OK):**
```json
{
  "account_number": "40991209384",
  "customer_name": "Rajesh Kumar",
  "kyc_status": "verified",
  "bank_name": "State Bank of India",
  "recommended_actions": ["Freeze Account", "File STR Immediately", "Manual Review"]
}
```

---

## 8. Compliance & STR Reports

### `POST /api/v1/compliance/str/generate`
Generates a pre-populated Section 12 PMLA Suspicious Transaction Report.

**Request:**
```json
{
  "alert_id": "ALERT-20260815-77A1F9",
  "bank_id": "bank_sbi",
  "account_details": {
    "account_number": "40991209384",
    "customer_name": "Rajesh Kumar"
  }
}
```

**Response (200 OK):**
```json
{
  "str_id": "STR-20260815-15D348",
  "regulatory_agency": "Financial Intelligence Unit - India (FIU-IND)",
  "statutory_mandate": "Section 12, Prevention of Money Laundering Act (PMLA) 2002",
  "account_number": "40991209384",
  "customer_name": "Rajesh Kumar",
  "amount_involved": 500000.0,
  "status": "draft"
}
```

### `POST /api/v1/compliance/str/submit`
Submits an approved STR report to the FIU-IND regulatory reporting gateway.

**Request:**
```json
{
  "str_id": "STR-20260815-15D348"
}
```

**Response (200 OK):**
```json
{
  "str_id": "STR-20260815-15D348",
  "status": "accepted",
  "submission_id": "SUB-D579BC7B",
  "fiu_ack": "ACK-FIU-D579BC7B",
  "submission_timestamp": "2026-08-15T11:47:05Z"
}
```
