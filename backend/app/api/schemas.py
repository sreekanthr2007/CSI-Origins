"""Pydantic request and response schemas for REST API endpoints."""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Graph Engine Schemas
# ---------------------------------------------------------------------------
class GraphStatsResponse(BaseModel):
    node_count: int = Field(..., examples=[1234])
    edge_count: int = Field(..., examples=[5678])
    avg_degree: float = Field(..., examples=[4.6])
    density: float = Field(..., examples=[0.0037])
    is_connected: bool = Field(..., examples=[False])
    component_count: int = Field(..., examples=[89])
    avg_shortest_path_length: float = Field(..., examples=[3.2])
    nodes: List[str] = Field(default_factory=list)
    edges_by_bank: Dict[str, int] = Field(default_factory=dict)


class EdgeItemSchema(BaseModel):
    sender_hash: str
    receiver_hash: str
    amount: float
    timestamp: str
    bank_id: str
    local_risk_score: Optional[float] = 0.0
    is_interbank: Optional[bool] = True
    edge_key: Optional[int] = None


class EdgeListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    edges: List[EdgeItemSchema]


class NodeListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    nodes: List[str]


class BuildGraphRequest(BaseModel):
    start_time: Optional[str] = Field(None, examples=["2026-08-15T00:00:00"])
    end_time: Optional[str] = Field(None, examples=["2026-08-15T23:59:59"])


class BuildGraphResponse(BaseModel):
    status: str = "built"
    nodes: int
    edges: int


# ---------------------------------------------------------------------------
# Feature Extraction Schemas
# ---------------------------------------------------------------------------
class FeatureVectorResponse(BaseModel):
    node_hash: str
    pass_through_ratio: float = 0.0
    avg_time_between_incoming_and_outgoing: float = 0.0
    min_time_between_incoming_and_outgoing: float = 0.0
    max_time_between_incoming_and_outgoing: float = 0.0
    std_dev_velocity: float = 0.0
    velocity_count: float = 0.0
    in_degree: float = 0.0
    out_degree: float = 0.0
    in_volume: float = 0.0
    out_volume: float = 0.0
    asymmetry_score: float = 0.0
    concentration_score: float = 0.0
    max_in_path_length: int = 0
    max_out_path_length: int = 0
    total_path_length: int = 0
    first_time_sender_count: float = 0.0
    first_time_receiver_count: float = 0.0
    first_time_edge_ratio: float = 0.0
    avg_amount_sent: float = 0.0
    avg_amount_received: float = 0.0
    max_amount_sent: float = 0.0
    max_amount_received: float = 0.0
    std_amount_sent: float = 0.0
    std_amount_received: float = 0.0
    round_figure_ratio: float = 0.0
    structuring_score: float = 0.0
    local_risk_score: float = 0.0
    avg_local_risk_score: float = 0.0
    max_local_risk_score: float = 0.0


class BatchFeatureResponse(BaseModel):
    total_nodes: int
    features: List[FeatureVectorResponse]


# ---------------------------------------------------------------------------
# Component Detection Schemas
# ---------------------------------------------------------------------------
class ComponentResponse(BaseModel):
    nodes: List[str]
    size: int
    banks: List[str]
    total_volume: float
    avg_pass_through: float
    max_chain_length: int
    risk_score: float


class ComponentListResponse(BaseModel):
    total: int
    components: List[ComponentResponse]


# ---------------------------------------------------------------------------
# Privacy & Vault Schemas
# ---------------------------------------------------------------------------
class StandingHashRequest(BaseModel):
    account_number: str = Field(..., examples=["SBIN1234567890"])
    ifsc_code: str = Field(..., examples=["SBIN0001234"])


class StandingHashResponse(BaseModel):
    hash: str = Field(..., examples=["HMAC:8f9a7b3c1d2e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a"])


class EphemeralHashRequest(BaseModel):
    account_number: str = Field(..., examples=["SBIN1234567890"])
    bank_id: str = Field(..., examples=["bank_sbi"])
    salt: str = Field(..., examples=["a1b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef0"])


class EphemeralHashResponse(BaseModel):
    hash: str = Field(..., examples=["INV:7b3c1d2e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0123"])


class SaltGenerateResponse(BaseModel):
    salt: str


class KeyRotationResponse(BaseModel):
    status: str = "rotated"
    new_fingerprint: str


class VaultRegisterRequest(BaseModel):
    bank_id: str
    accounts: List[Dict[str, Any]]


class VaultResolveRequest(BaseModel):
    hash: str
    bank_id: Optional[str] = None


class GenerateTransactionsRequest(BaseModel):
    num_banks: Optional[int] = 10
    num_accounts_per_bank: Optional[int] = 100
    num_edges: Optional[int] = 5000
    contamination_rate: Optional[float] = 0.10
    seed: Optional[int] = 42


class GenerateMotifRequest(BaseModel):
    motif_type: str = Field(..., examples=["chain"])
    params: Optional[Dict[str, Any]] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Machine Learning & Explainability Schemas (Phase 5)
# ---------------------------------------------------------------------------
class TrainModelRequest(BaseModel):
    model_type: Optional[str] = Field("xgboost", examples=["xgboost", "random_forest"])
    dataset_size: Optional[int] = Field(None, examples=[5000])
    num_banks: Optional[int] = Field(None, examples=[10])
    num_accounts_per_bank: Optional[int] = Field(None, examples=[100])
    num_edges: Optional[int] = Field(None, examples=[5000])
    contamination_rate: Optional[float] = Field(None, examples=[0.10])


class TrainModelResponse(BaseModel):
    model_type: str
    training_time_seconds: float
    accuracy: float
    precision: float
    recall: float
    f1: float
    auc_roc: float
    dataset_size: int
    num_features: int
    feature_importance: Dict[str, float]
    thresholds: Dict[str, float]


class PredictNodeRequest(BaseModel):
    node_hash: str = Field(..., examples=["HMAC:8f9a7b3c1d2e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a"])


class PredictNodeResponse(BaseModel):
    node_hash: str
    probability: float
    is_mule: bool
    severity: str
    severity_color: str
    features: Optional[Dict[str, Any]] = None


class PredictBatchRequest(BaseModel):
    node_hashes: List[str] = Field(..., examples=[["HMAC:node1", "HMAC:node2"]])


class BatchPredictionItem(BaseModel):
    hash: str
    probability: float
    is_mule: bool
    severity: str


class PredictBatchResponse(BaseModel):
    total: int
    predictions: List[BatchPredictionItem]


class PredictComponentRequest(BaseModel):
    component_id: Optional[str] = None
    node_hashes: Optional[List[str]] = None


class PredictComponentResponse(BaseModel):
    component_risk: float
    severity: str
    node_scores: Dict[str, float]
    avg_pass_through: float
    max_chain_length: int


class FeatureAttributionItem(BaseModel):
    feature: str
    value: float
    shap: float
    direction: str


class ExplainResponse(BaseModel):
    node_hash: str
    probability: float
    is_mule: bool
    severity: str
    severity_color: str
    feature_importance: List[FeatureAttributionItem]
    top_drivers: List[str]
    summary: str


class FeatureImportanceResponse(BaseModel):
    features: List[str]
    importance: List[float]


class ThresholdUpdateRequest(BaseModel):
    threshold_key: str = Field(..., examples=["high", "critical", "medium", "low"])
    value: float = Field(..., ge=0.0, le=1.0, examples=[0.75])


class ThresholdsResponse(BaseModel):
    status: str = "operational"
    thresholds: Dict[str, float]


class MLStatusResponse(BaseModel):
    model_exists: bool
    model_type: str
    trained_at: Optional[str] = None
    num_features: int
    version: str = "1.0.0"


class MLEvaluateRequest(BaseModel):
    test_size: Optional[float] = Field(0.20, ge=0.05, le=0.50)


class MLEvaluateResponse(BaseModel):
    accuracy: float
    precision: float
    recall: float
    f1: float
    auc_roc: float
    confusion_matrix: List[List[int]]


# ---------------------------------------------------------------------------
# Investigation & Traversal Schemas (Phase 6)
# ---------------------------------------------------------------------------
class StartInvestigationRequest(BaseModel):
    node_hash: str = Field(..., examples=["HMAC:8f9a7b3c1d2e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a"])
    component_id: Optional[str] = Field(None, examples=["comp_1234567890"])


class StartInvestigationResponse(BaseModel):
    investigation_id: str
    status: str = "started"
    target_node: str


class InvestigationStatusResponse(BaseModel):
    investigation_id: str
    status: str
    component_id: Optional[str] = None
    depth_reached: int
    banks_queried: List[str]
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    closed_by: Optional[str] = None


class PlaybackStep(BaseModel):
    step_number: int
    action: str
    description: str
    decision: str
    node: Optional[str] = None
    from_: Optional[str] = Field(None, alias="from")
    to: Optional[str] = None
    bank_id: Optional[str] = None
    amount: Optional[float] = None
    reason: Optional[str] = None

    class Config:
        populate_by_name = True


class PlaybackResponse(BaseModel):
    investigation_id: str
    total_steps: int
    steps: List[Dict[str, Any]]


class CloseInvestigationRequest(BaseModel):
    closed_by: Optional[str] = Field("human_review", examples=["human_review", "compliance_officer"])


class CloseInvestigationResponse(BaseModel):
    status: str = "closed"
    closed_by: str
    investigation_id: str


class DeleteInvestigationResponse(BaseModel):
    status: str = "deleted"
    investigation_id: str
    salt_destroyed: bool = True


class ActiveInvestigationsResponse(BaseModel):
    total: int
    investigations: List[Dict[str, Any]]


# ---------------------------------------------------------------------------
# Bank Integration & Alerting Schemas (Phase 7)
# ---------------------------------------------------------------------------
class BankResponse(BaseModel):
    bank_id: str
    bank_name: str
    ifsc_prefix: str
    is_active: bool = True
    total_accounts: int = 0


class BankListResponse(BaseModel):
    total: int
    banks: List[BankResponse]


class AlertResponse(BaseModel):
    id: str
    component_id: str
    severity: str
    dispatch_time: Optional[str] = None
    dispatched_to: List[str]
    resolution_status: str
    resolved_at: Optional[str] = None
    resolution_notes: Optional[str] = None


class AlertListResponse(BaseModel):
    total: int
    alerts: List[AlertResponse]


class DispatchAlertRequest(BaseModel):
    component_id: str = Field(..., examples=["comp_1234567890"])
    risk_score: Optional[float] = Field(0.85, ge=0.0, le=1.0)


class DispatchAlertResponse(BaseModel):
    alert_id: str
    component_id: str
    severity: str
    dispatched_to: List[str]
    bank_acknowledged: List[str]
    failed: List[str]


class ResolveAlertRequest(BaseModel):
    status: str = Field("resolved", examples=["resolved", "dismissed"])
    notes: Optional[str] = Field(None, examples=["Confirmed mule network with SBI compliance, debit freeze placed"])


class ResolveAlertResponse(BaseModel):
    id: str
    resolution_status: str
    resolved_at: Optional[str] = None
    resolution_notes: Optional[str] = None


class GenerateSTRRequest(BaseModel):
    bank_id: str = Field(..., examples=["bank_sbi"])


class STRResponse(BaseModel):
    str_id: str
    schema_version: str
    filing_bank: str
    bank_id: str
    regulatory_agency: str
    account_number: str
    customer_name: str
    risk_score: float
    severity: str
    suspicion_reason: str
    supporting_evidence: List[str]
    amount_involved: float
    involved_banks: List[str]
    recommended_actions: List[str]
    filing_date: str


class VaultResolveResponse(BaseModel):
    hash: str
    account_number: str
    customer_name: str
    bank_id: str
    bank_name: str
    kyc_status: str
    declared_income: float
    account_age_days: int
    is_dormant: bool



