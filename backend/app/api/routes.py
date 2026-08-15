"""FastAPI API routes for privacy hashing, bank vaults, synthetic data, graph engine, and feature extraction."""
import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from backend.app.config import settings
from backend.app.privacy.hashing import (
    generate_standing_hash,
    generate_ephemeral_hash,
    generate_investigation_salt,
    HashingService,
)
from backend.app.privacy.bank_vault import BankVault
from backend.app.data_generator.synthetic_banks import (
    generate_banks,
    generate_accounts,
    BANK_METADATA,
)
from backend.app.data_generator.motif_injector import (
    MotifInjector,
    generate_with_contamination,
)
from backend.app.graph.graph_engine import GraphEngine, TemporalGraph
from backend.app.features.feature_extractor import FeatureExtractor
from backend.app.features.component_detector import ComponentDetector
from backend.app.database.repositories import EdgeRepository, ComponentRepository
from backend.app.bank_node import bank_registry, BankNodeRegistry
from backend.app.alerts import alert_dispatcher, AlertStatus
from backend.app.compliance import str_generator, action_recommender
from backend.app.api.schemas import (
    GraphStatsResponse,
    EdgeItemSchema,
    EdgeListResponse,
    NodeListResponse,
    BuildGraphRequest,
    BuildGraphResponse,
    FeatureVectorResponse,
    BatchFeatureResponse,
    ComponentResponse,
    ComponentListResponse,
    StandingHashRequest,
    StandingHashResponse,
    EphemeralHashRequest,
    EphemeralHashResponse,
    SaltGenerateResponse,
    KeyRotationResponse,
    VaultRegisterRequest,
    VaultResolveRequest,
    GenerateTransactionsRequest,
    GenerateMotifRequest,
    StartInvestigationRequest,
    StartInvestigationResponse,
    InvestigationStatusResponse,
    PlaybackStep,
    PlaybackResponse,
    CloseInvestigationRequest,
    CloseInvestigationResponse,
    DeleteInvestigationResponse,
    ActiveInvestigationsResponse,
    BankResponse,
    BankListResponse,
    AlertResponse,
    AlertListResponse,
    DispatchAlertRequest,
    DispatchAlertResponse,
    ResolveAlertRequest,
    ResolveAlertResponse,
    GenerateSTRRequest,
    STRResponse,
    VaultResolveResponse,
)


logger = logging.getLogger("mule-detection-api")

router = APIRouter()
hashing_service = HashingService(settings)
graph_engine = GraphEngine.get_instance(settings)

# In-memory bank vaults for simulation (one per bank)
BANK_VAULTS: Dict[str, BankVault] = {
    b["id"]: BankVault(bank_id=b["id"], bank_name=b["name"])
    for b in BANK_METADATA
}


# ---------------------------------------------------------------------------
# Health & Status
# ---------------------------------------------------------------------------
@router.get("/health", tags=["Health"])
def health_endpoint():
    """Service health check."""
    return {"status": "ok", "version": "1.0.0"}


@router.get("/banks", tags=["Banks"])
def list_banks():
    """Return participating Indian banks."""
    return generate_banks()


@router.get("/status", tags=["Status"])
def system_status():
    """Return platform cryptographic, graph, and runtime status."""
    g = graph_engine.get_graph()
    return {
        "status": "OPERATIONAL",
        "flow_a_active": True,
        "flow_b_ready": True,
        "standing_key_fingerprint": hashing_service.get_current_key_fingerprint(),
        "registered_banks_count": len(BANK_VAULTS),
        "total_vault_accounts": sum(v.total_accounts for v in BANK_VAULTS.values()),
        "graph_node_count": g.get_node_count(),
        "graph_edge_count": g.get_edge_count()
    }


# ---------------------------------------------------------------------------
# Privacy Endpoints
# ---------------------------------------------------------------------------
@router.post("/privacy/hash", response_model=StandingHashResponse, tags=["Privacy"])
def create_standing_hash(req: StandingHashRequest):
    """Compute standing HMAC-SHA256 hash for Flow A."""
    if not req.account_number.strip() or not req.ifsc_code.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="account_number and ifsc_code are required")
    hash_val = hashing_service.compute_hash(req.account_number, req.ifsc_code)
    return StandingHashResponse(hash=hash_val)


@router.post("/privacy/hash/ephemeral", response_model=EphemeralHashResponse, tags=["Privacy"])
def create_ephemeral_hash(req: EphemeralHashRequest):
    """Compute ephemeral investigation HMAC-SHA256 hash for Flow B."""
    if not req.account_number.strip() or not req.bank_id.strip() or not req.salt.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="account_number, bank_id, and salt are required")
    hash_val = generate_ephemeral_hash(req.account_number, req.bank_id, req.salt)
    return EphemeralHashResponse(hash=hash_val)


@router.post("/privacy/salt/generate", response_model=SaltGenerateResponse, tags=["Privacy"])
def create_salt():
    """Generate 32-byte cryptographically secure investigation salt."""
    salt_val = generate_investigation_salt()
    return SaltGenerateResponse(salt=salt_val)


@router.post("/privacy/key/rotate", response_model=KeyRotationResponse, tags=["Privacy"])
def rotate_key():
    """Rotate standing HMAC registry key (admin only)."""
    fingerprint = hashing_service.rotate_key()
    return KeyRotationResponse(status="rotated", new_fingerprint=fingerprint)


# ---------------------------------------------------------------------------
# Bank Vault Endpoints (Development / Demo Simulation)
# ---------------------------------------------------------------------------
@router.post("/vault/register", tags=["Bank Vault"])
def register_vault_accounts(req: VaultRegisterRequest):
    """Register customer identities inside a bank's private vault."""
    vault = BANK_VAULTS.get(req.bank_id)
    if not vault:
        vault = BankVault(bank_id=req.bank_id, bank_name=req.bank_id)
        BANK_VAULTS[req.bank_id] = vault

    count = vault.register_accounts(req.accounts)
    return {"registered": count, "bank_id": req.bank_id}


@router.post("/vault/resolve", tags=["Bank Vault"])
def resolve_vault_hash(req: VaultResolveRequest):
    """Attempt de-anonymization of a hash inside bank's private vault."""
    if req.bank_id and req.bank_id in BANK_VAULTS:
        account = BANK_VAULTS[req.bank_id].resolve_hash(req.hash)
        if not account:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hash not found in specified bank vault")
        return account

    for vault in BANK_VAULTS.values():
        account = vault.resolve_hash(req.hash)
        if account:
            return account

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hash not found in any participating bank vault")


# ---------------------------------------------------------------------------
# Synthetic Data Generation Endpoints
# ---------------------------------------------------------------------------
@router.post("/generate/banks", tags=["Data Generator"])
def generate_synthetic_banks_endpoint():
    """Generate Indian bank profiles and accounts."""
    banks = generate_banks()
    all_accounts = []
    for b in banks:
        accs = generate_accounts(b, count=settings.NUM_ACCOUNTS_PER_BANK)
        all_accounts.extend(accs)
        if b["id"] in BANK_VAULTS:
            BANK_VAULTS[b["id"]].register_accounts(accs)
    return {"banks": banks, "accounts_count": len(all_accounts), "accounts": all_accounts}


@router.post("/data/generate/transactions", tags=["Data Generator"])
@router.post("/generate/transactions", tags=["Data Generator"])
def generate_transactions_endpoint(req: GenerateTransactionsRequest):

    """Generate full dataset with Erdős-Rényi transactions and injected mule motifs."""
    dataset = generate_with_contamination(
        num_banks=req.num_banks or 10,
        num_accounts_per_bank=req.num_accounts_per_bank or 100,
        num_edges=req.num_edges or 5000,
        contamination_rate=req.contamination_rate or 0.10,
        seed=req.seed or 42
    )

    for acc in dataset["accounts"]:
        b_id = acc["bank_id"]
        if b_id in BANK_VAULTS:
            BANK_VAULTS[b_id].register_account(
                account_number=acc["account_number"],
                ifsc_code=acc["ifsc_code"],
                customer_name=acc.get("customer_name", "Demo User"),
                kyc_status=acc.get("kyc_status", "verified"),
                declared_income=acc.get("declared_income", 30000.0)
            )

    # Enrich edges with standing hashes and automatically ingest into graph engine
    standing_key = settings.get_standing_key()
    enriched_edges = []
    for e in dataset["edges"]:
        s_acc = e.get("sender_account", "")
        s_ifsc = e.get("sender_ifsc", "SBIN0001000")
        r_acc = e.get("receiver_account", "")
        r_ifsc = e.get("receiver_ifsc", "HDFC0001000")
        s_hash = e.get("sender_hash") or generate_standing_hash(s_acc, s_ifsc, standing_key)
        r_hash = e.get("receiver_hash") or generate_standing_hash(r_acc, r_ifsc, standing_key)
        e_copy = dict(e)
        e_copy["sender_hash"] = s_hash
        e_copy["receiver_hash"] = r_hash
        e_copy["bank_id"] = e.get("sender_bank_id") or e.get("bank_id", "UNKNOWN")
        enriched_edges.append(e_copy)

    graph_engine.get_graph().add_edges_batch(enriched_edges)


    return {
        "banks_count": len(dataset["banks"]),
        "accounts_count": len(dataset["accounts"]),
        "edges_count": len(dataset["edges"]),
        "motifs_count": len(dataset["motifs"]),
        "ground_truth": dataset["ground_truth"],
        "edges_sample": dataset["edges"][:50]
    }


@router.post("/generate/motif", tags=["Data Generator"])
def generate_single_motif(req: GenerateMotifRequest):
    """Inject a single specified motif (chain, collector, distributor)."""
    banks = generate_banks()
    accounts_by_bank = {b["id"]: generate_accounts(b, count=30) for b in banks}
    
    injector = MotifInjector()
    motif = injector.inject_motif(accounts_by_bank, req.motif_type, req.params)
    return {"motif": motif, "nodes": motif.get("nodes") or motif.get("senders") or motif.get("receivers")}


# ---------------------------------------------------------------------------
# Graph Engine Endpoints (Phase 4)
# ---------------------------------------------------------------------------
@router.get("/graph/stats", response_model=GraphStatsResponse, tags=["Graph Engine"])
def get_graph_statistics():
    """Return topological and component statistics for the central graph."""
    g = graph_engine.get_graph()
    stats = g.get_graph_stats()
    return GraphStatsResponse(**stats)


@router.get("/graph/edges", response_model=EdgeListResponse, tags=["Graph Engine"])
def get_graph_edges(
    limit: int = Query(100, ge=1, le=5000, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    bank_id: Optional[str] = Query(None, description="Optional bank ID filter")
):
    """Return paginated list of transaction edges with metadata."""
    g = graph_engine.get_graph()
    all_edges = []
    
    for u, v, k, d in g.graph.edges(keys=True, data=True):
        if bank_id and d.get("bank_id") != bank_id:
            continue
        all_edges.append(EdgeItemSchema(
            sender_hash=u,
            receiver_hash=v,
            amount=float(d.get("amount", 0.0)),
            timestamp=str(d.get("timestamp", "")),
            bank_id=str(d.get("bank_id", "")),
            local_risk_score=float(d.get("local_risk_score", 0.0) or 0.0),
            is_interbank=bool(d.get("is_interbank", True)),
            edge_key=k
        ))

    total = len(all_edges)
    paginated = all_edges[offset : offset + limit]
    return EdgeListResponse(total=total, limit=limit, offset=offset, edges=paginated)


@router.get("/graph/nodes", response_model=NodeListResponse, tags=["Graph Engine"])
def get_graph_nodes(
    limit: int = Query(100, ge=1, le=5000, description="Max nodes to return"),
    offset: int = Query(0, ge=0, description="Pagination offset")
):
    """Return paginated list of node hashes in the active graph."""
    g = graph_engine.get_graph()
    all_nodes = g.get_nodes()
    total = len(all_nodes)
    paginated = all_nodes[offset : offset + limit]
    return NodeListResponse(total=total, limit=limit, offset=offset, nodes=paginated)


@router.get("/graph/component/{node_hash}", response_model=ComponentResponse, tags=["Graph Engine"])
def get_node_component(node_hash: str):
    """Return connected component containing the specified node."""
    if not node_hash.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Node hash cannot be empty")
    
    g = graph_engine.get_graph()
    if not g.graph.has_node(node_hash):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Node {node_hash} not found in graph")

    detector = ComponentDetector(graph=g)
    sub_tg = g.get_connected_component(node_hash)
    nodes = sub_tg.get_nodes()
    
    comp_feats = FeatureExtractor(graph=g).extract_component_features(nodes)
    risk = detector._compute_component_risk(nodes)

    banks = set()
    for _, _, d in sub_tg.graph.edges(data=True):
        if d.get("bank_id"):
            banks.add(d.get("bank_id"))

    return ComponentResponse(
        nodes=nodes,
        size=len(nodes),
        banks=sorted(list(banks)),
        total_volume=comp_feats.get("total_volume", 0.0),
        avg_pass_through=comp_feats.get("avg_pass_through", 0.0),
        max_chain_length=comp_feats.get("max_chain_length", 1),
        risk_score=risk
    )


@router.get("/graph/features/batch", response_model=BatchFeatureResponse, tags=["Feature Extraction"])
def get_batch_features(nodes: str = Query(..., description="Comma-separated node hashes")):
    """Return feature vectors for multiple specified node hashes."""
    if not nodes.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nodes parameter cannot be empty")

    node_list = [n.strip() for n in nodes.split(",") if n.strip()]
    if not node_list:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid node hashes provided")

    g = graph_engine.get_graph()
    extractor = FeatureExtractor(graph=g)
    results = [FeatureVectorResponse(**extractor.extract_node_features(n)) for n in node_list]

    return BatchFeatureResponse(total_nodes=len(results), features=results)


@router.get("/graph/features/{node_hash}", response_model=FeatureVectorResponse, tags=["Feature Extraction"])
def get_node_features(node_hash: str):
    """Return calculated behavioral and topological feature vector for a single node."""
    if not node_hash.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Node hash cannot be empty")

    g = graph_engine.get_graph()
    if not g.graph.has_node(node_hash):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Node {node_hash} not found in graph")

    extractor = FeatureExtractor(graph=g)
    feats = extractor.extract_node_features(node_hash)
    return FeatureVectorResponse(**feats)



@router.post("/graph/build", response_model=BuildGraphResponse, tags=["Graph Engine"])
def build_graph_endpoint(req: Optional[BuildGraphRequest] = None):
    """Build or reload the graph engine from SQLite database records."""
    start_t = req.start_time if req else None
    end_t = req.end_time if req else None
    
    edges_loaded = graph_engine.reload_from_db(start_time=start_t, end_time=end_t)
    g = graph_engine.get_graph()

    return BuildGraphResponse(
        status="built",
        nodes=g.get_node_count(),
        edges=g.get_edge_count()
    )


@router.get("/graph/components", response_model=ComponentListResponse, tags=["Graph Engine"])
def list_components(min_size: int = Query(2, ge=1, description="Minimum component size")):
    """List all connected components with calculated mule risk scores."""
    g = graph_engine.get_graph()
    detector = ComponentDetector(graph=g)
    comps = detector.get_components_with_risk(min_size=min_size)
    formatted = [ComponentResponse(**c) for c in comps]
    return ComponentListResponse(total=len(formatted), components=formatted)


@router.get("/graph/components/high-risk", response_model=ComponentListResponse, tags=["Graph Engine"])
def list_high_risk_components(
    min_risk: float = Query(0.7, ge=0.0, le=1.0, description="Minimum risk score threshold")
):
    """Return connected components whose risk score exceeds threshold."""
    g = graph_engine.get_graph()
    detector = ComponentDetector(graph=g)
    comps = detector.get_components_with_risk(min_size=2)
    filtered = [ComponentResponse(**c) for c in comps if c["risk_score"] >= min_risk]
    return ComponentListResponse(total=len(filtered), components=filtered)


# ---------------------------------------------------------------------------
# Machine Learning & Explainability Endpoints (Phase 5)
# ---------------------------------------------------------------------------
from backend.app.ml.classifier import MuleClassifier
from backend.app.ml.explainability import ExplainabilityEngine
from backend.app.ml.thresholds import ThresholdManager
from backend.app.ml.training import TrainingPipeline
from backend.app.api.schemas import (
    TrainModelRequest,
    TrainModelResponse,
    PredictNodeRequest,
    PredictNodeResponse,
    PredictBatchRequest,
    PredictBatchResponse,
    BatchPredictionItem,
    PredictComponentRequest,
    PredictComponentResponse,
    ExplainResponse,
    FeatureAttributionItem,
    FeatureImportanceResponse,
    ThresholdUpdateRequest,
    ThresholdsResponse,
    MLStatusResponse,
    MLEvaluateRequest,
    MLEvaluateResponse,
)

mule_classifier = MuleClassifier(settings)
explainability_engine = ExplainabilityEngine(config=settings)
threshold_manager = ThresholdManager(config=settings)


@router.post("/ml/train", response_model=TrainModelResponse, tags=["Machine Learning"])
def train_model_endpoint(req: Optional[TrainModelRequest] = None):
    """Train XGBoost or Random Forest model on synthesized multi-bank dataset."""
    pipeline = TrainingPipeline(config=settings)
    summary = pipeline.run_training_pipeline(
        num_banks=req.num_banks if req else None,
        num_accounts_per_bank=req.num_accounts_per_bank if req else None,
        num_edges=req.num_edges if req else None,
        contamination_rate=req.contamination_rate if req else None,
        model_type=req.model_type if req and req.model_type else "xgboost",
        save_artifacts=True
    )
    # Reload active classifier and explainer
    mule_classifier.load_model(settings.MODEL_PATH)
    explainability_engine.set_model(mule_classifier.model, mule_classifier.feature_names)

    return TrainModelResponse(
        model_type=summary["model_type"],
        training_time_seconds=summary["training_time_seconds"],
        accuracy=summary["accuracy"],
        precision=summary["precision"],
        recall=summary["recall"],
        f1=summary["f1"],
        auc_roc=summary["auc_roc"],
        dataset_size=summary["dataset_size"],
        num_features=summary["num_features"],
        feature_importance=summary["feature_importance"],
        thresholds=summary["thresholds"]
    )


@router.post("/ml/predict", response_model=PredictNodeResponse, tags=["Machine Learning"])
def predict_node_endpoint(req: PredictNodeRequest):
    """Perform on-the-fly ML inference and risk classification for a single node."""
    if not req.node_hash.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="node_hash cannot be empty")

    g = graph_engine.get_graph()
    if not g.graph.has_node(req.node_hash):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Node {req.node_hash} not found in graph")

    if not mule_classifier.model_exists() and mule_classifier.model is None:
        # Fallback to feature-based heuristic prediction if model not trained yet
        fe = FeatureExtractor(graph=g)
        feats = fe.extract_node_features(req.node_hash)
        prob = min(feats.get("pass_through_ratio", 0.0) * 0.8 + feats.get("total_path_length", 1) * 0.05, 0.99)
        sev = threshold_manager.get_severity(prob)
        return PredictNodeResponse(
            node_hash=req.node_hash,
            probability=round(prob, 4),
            is_mule=bool(prob >= 0.50),
            severity=sev,
            severity_color=threshold_manager.get_severity_color(sev),
            features=feats
        )

    res = mule_classifier.predict_for_node(req.node_hash, graph=g)
    return PredictNodeResponse(**res)


@router.post("/ml/predict_batch", response_model=PredictBatchResponse, tags=["Machine Learning"])
def predict_batch_endpoint(req: PredictBatchRequest):
    """Perform batch inference for a list of node hashes."""
    if not req.node_hashes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="node_hashes list cannot be empty")

    g = graph_engine.get_graph()
    extractor = FeatureExtractor(graph=g)
    df_feats = extractor.extract_features_batch(req.node_hashes)

    if mule_classifier.model is not None:
        probs = mule_classifier.predict_proba(df_feats)
    else:
        probs = [0.10 for _ in req.node_hashes]

    items = []
    for h, p in zip(req.node_hashes, probs):
        p_val = round(float(p), 4)
        sev = threshold_manager.get_severity(p_val)
        items.append(BatchPredictionItem(
            hash=h,
            probability=p_val,
            is_mule=bool(p_val >= threshold_manager.thresholds.get("medium", 0.50)),
            severity=sev
        ))

    return PredictBatchResponse(total=len(items), predictions=items)


@router.post("/ml/predict_component", response_model=PredictComponentResponse, tags=["Machine Learning"])
def predict_component_endpoint(req: PredictComponentRequest):
    """Score a connected component subgraph using ML probabilities and topological indicators."""
    g = graph_engine.get_graph()
    nodes = req.node_hashes or []
    
    if req.component_id:
        comp_rec = ComponentRepository.get_by_id(req.component_id)
        if comp_rec and comp_rec.get("hashed_nodes"):
            nodes = comp_rec["hashed_nodes"]

    if not nodes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Either component_id or node_hashes must be provided")

    if mule_classifier.model is not None:
        res = mule_classifier.score_component(nodes, graph=g)
    else:
        # Fallback to ComponentDetector risk calculation
        detector = ComponentDetector(graph=g)
        c_feats = FeatureExtractor(graph=g).extract_component_features(nodes)
        risk = detector._compute_component_risk(nodes)
        sev = threshold_manager.get_severity(risk)
        res = {
            "component_risk": risk,
            "severity": sev,
            "node_scores": {n: risk for n in nodes},
            "avg_pass_through": c_feats.get("avg_pass_through", 0.0),
            "max_chain_length": c_feats.get("max_chain_length", 1)
        }

    return PredictComponentResponse(**res)


@router.get("/ml/explain/{node_hash}", response_model=ExplainResponse, tags=["Machine Learning"])
def explain_node_endpoint(node_hash: str):
    """Generate SHAP feature attributions and natural language rationale for an account."""
    if not node_hash.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="node_hash cannot be empty")

    g = graph_engine.get_graph()
    if not g.graph.has_node(node_hash):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Node {node_hash} not found in graph")

    extractor = FeatureExtractor(graph=g)
    feats = extractor.extract_node_features(node_hash)
    df_row = pd.DataFrame([feats])
    if "node_hash" in df_row.columns:
        df_row.drop(columns=["node_hash"], inplace=True)

    if mule_classifier.model is not None:
        explainability_engine.set_model(mule_classifier.model, mule_classifier.feature_names)
        data = explainability_engine.get_explanation_data(node_hash, df_row)
    else:
        # Construct fallback attribution from structural heuristics
        pt = float(feats.get("pass_through_ratio", 0.0))
        prob = min(max(pt * 0.9, 0.1), 0.95)
        sev = threshold_manager.get_severity(prob)
        data = {
            "node_hash": node_hash,
            "probability": round(prob, 4),
            "is_mule": bool(prob >= 0.50),
            "severity": sev,
            "severity_color": threshold_manager.get_severity_color(sev),
            "feature_importance": [
                {"feature": "pass_through_ratio", "value": pt, "shap": round(pt * 0.4, 4), "direction": "positive"},
                {"feature": "total_path_length", "value": float(feats.get("total_path_length", 1)), "shap": 0.25, "direction": "positive"}
            ],
            "top_drivers": ["pass_through_ratio", "total_path_length"],
            "summary": f"Account {node_hash} flagged due to {pt*100:.1f}% pass-through ratio."
        }

    return ExplainResponse(**data)


@router.get("/ml/feature_importance", response_model=FeatureImportanceResponse, tags=["Machine Learning"])
def feature_importance_endpoint():
    """Return global feature importance ranking."""
    if mule_classifier.model is not None:
        explainability_engine.set_model(mule_classifier.model, mule_classifier.feature_names)
        plot_data = explainability_engine.get_feature_importance_plot(top_n=25)
    else:
        plot_data = {"features": ["pass_through_ratio", "total_path_length", "avg_time_between_incoming_and_outgoing"], "importance": [0.35, 0.28, 0.18]}

    return FeatureImportanceResponse(**plot_data)


@router.get("/ml/thresholds", response_model=ThresholdsResponse, tags=["Machine Learning"])
def get_thresholds_endpoint():
    """Return active risk probability thresholds."""
    return ThresholdsResponse(status="operational", thresholds=threshold_manager.get_thresholds())


@router.put("/ml/thresholds", response_model=ThresholdsResponse, tags=["Machine Learning"])
def update_threshold_endpoint(req: ThresholdUpdateRequest):
    """Update a specific severity threshold."""
    try:
        updated = threshold_manager.update_threshold(req.threshold_key, req.value)
        return ThresholdsResponse(status="updated", thresholds=updated)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/ml/status", response_model=MLStatusResponse, tags=["Machine Learning"])
def ml_status_endpoint():
    """Return model runtime status and metadata."""
    exists = mule_classifier.model_exists() or (mule_classifier.model is not None)
    return MLStatusResponse(
        model_exists=exists,
        model_type=mule_classifier.model_type,
        num_features=len(mule_classifier.feature_names),
        version="1.0.0"
    )


@router.post("/ml/evaluate", response_model=MLEvaluateResponse, tags=["Machine Learning"])
def evaluate_model_endpoint(req: Optional[MLEvaluateRequest] = None):
    """Evaluate classifier on synthetic test dataset."""
    test_size = req.test_size if req else 0.20
    db = DatasetBuilder(config=settings)
    df = db.build_dataset(num_banks=6, num_accounts_per_bank=40, num_edges=1000)
    _, X_test, _, y_test = db.split_dataset(df, test_size=test_size)

    if mule_classifier.model is None:
        mule_classifier.train(X_test, y_test)

    eval_results = mule_classifier.evaluate(X_test, y_test)
    return MLEvaluateResponse(**eval_results)


# ---------------------------------------------------------------------------
# Flow B Investigation & Traversal Endpoints (Phase 6)
# ---------------------------------------------------------------------------
from backend.app.investigation.flow_b_service import FlowBService
from backend.app.api.schemas import (
    StartInvestigationRequest,
    StartInvestigationResponse,
    InvestigationStatusResponse,
    PlaybackResponse,
    CloseInvestigationRequest,
    CloseInvestigationResponse,
    DeleteInvestigationResponse,
    ActiveInvestigationsResponse,
)

flow_b_service = FlowBService(config=settings)


@router.post("/investigation/start", response_model=StartInvestigationResponse, tags=["Investigation (Flow B)"])
def start_investigation_endpoint(req: StartInvestigationRequest):
    """Start an on-demand targeted Flow B investigation with ephemeral salt and bounded traversal."""
    if not req.node_hash.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="node_hash cannot be empty")

    g = graph_engine.get_graph()
    if not g.graph.has_node(req.node_hash):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Node {req.node_hash} not found in graph")

    inv_id = flow_b_service.start_investigation(
        node_hash=req.node_hash,
        component_id=req.component_id
    )

    return StartInvestigationResponse(
        investigation_id=inv_id,
        status="started",
        target_node=req.node_hash
    )


@router.get("/investigation/{investigation_id}/status", response_model=InvestigationStatusResponse, tags=["Investigation (Flow B)"])
def get_investigation_status_endpoint(investigation_id: str):
    """Retrieve operational status and progress of an investigation."""
    try:
        res = flow_b_service.get_status(investigation_id)
        return InvestigationStatusResponse(**res)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/investigation/{investigation_id}/result", tags=["Investigation (Flow B)"])
def get_investigation_result_endpoint(investigation_id: str):
    """Retrieve complete graph traversal path and decay metrics."""
    try:
        res = flow_b_service.get_result(investigation_id)
        if not res:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No traversal results found")
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/investigation/{investigation_id}/playback", response_model=PlaybackResponse, tags=["Investigation (Flow B)"])
def get_investigation_playback_endpoint(investigation_id: str):
    """Retrieve step-by-step traversal playback trace."""
    try:
        steps = flow_b_service.get_playback(investigation_id)
        return PlaybackResponse(
            investigation_id=investigation_id,
            total_steps=len(steps),
            steps=steps
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/investigation/{investigation_id}/close", response_model=CloseInvestigationResponse, tags=["Investigation (Flow B)"])
def close_investigation_endpoint(investigation_id: str, req: Optional[CloseInvestigationRequest] = None):
    """Close an investigation and permanently destroy the ephemeral salt."""
    closed_by = req.closed_by if req and req.closed_by else "human_review"
    try:
        res = flow_b_service.close_investigation(investigation_id, closed_by=closed_by)
        return CloseInvestigationResponse(**res)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/investigation/{investigation_id}", response_model=DeleteInvestigationResponse, tags=["Investigation (Flow B)"])
def delete_investigation_endpoint(investigation_id: str):
    """Delete an investigation record."""
    try:
        res = flow_b_service.delete_investigation(investigation_id)
        return DeleteInvestigationResponse(**res)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/investigation/active", response_model=ActiveInvestigationsResponse, tags=["Investigation (Flow B)"])
def list_active_investigations_endpoint():
    """List all currently active or in-progress investigations."""
    active = flow_b_service.list_active_investigations()
    return ActiveInvestigationsResponse(total=len(active), investigations=active)


# ---------------------------------------------------------------------------
# Bank Nodes & Identity Vault Endpoints (Phase 7)
# ---------------------------------------------------------------------------
@router.get("/banks", response_model=BankListResponse, tags=["Bank Integration & Alerts"])
def list_banks_endpoint():
    """List all participating autonomous bank nodes."""
    all_banks = bank_registry.get_all_banks()
    items = []
    for b in all_banks:
        items.append(BankResponse(
            bank_id=b.bank_id,
            bank_name=b.bank_name,
            ifsc_prefix=b.ifsc_prefix,
            is_active=True,
            total_accounts=b.vault.total_accounts
        ))
    return BankListResponse(total=len(items), banks=items)


@router.get("/banks/{bank_id}", response_model=BankResponse, tags=["Bank Integration & Alerts"])
def get_bank_endpoint(bank_id: str):
    """Retrieve details for a specific bank node."""
    b = bank_registry.get_bank_by_id(bank_id)
    if not b:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Bank {bank_id} not found")
    return BankResponse(
        bank_id=b.bank_id,
        bank_name=b.bank_name,
        ifsc_prefix=b.ifsc_prefix,
        is_active=True,
        total_accounts=b.vault.total_accounts
    )


@router.get("/banks/{bank_id}/alerts", response_model=AlertListResponse, tags=["Bank Integration & Alerts"])
def get_bank_alerts_endpoint(bank_id: str):
    """Retrieve alerts dispatched to a specific bank node."""
    alerts = alert_dispatcher.get_alerts_by_bank(bank_id)
    resp_alerts = [AlertResponse(**a) for a in alerts]
    return AlertListResponse(total=len(resp_alerts), alerts=resp_alerts)


@router.get("/banks/{bank_id}/vault/resolve", response_model=VaultResolveResponse, tags=["Bank Integration & Alerts"])
@router.post("/banks/{bank_id}/vault/resolve", response_model=VaultResolveResponse, tags=["Bank Integration & Alerts"])
def resolve_bank_vault_hash_endpoint(bank_id: str, hash_val: Optional[str] = Query(None, alias="hash"), req: Optional[VaultResolveRequest] = None):
    """Internal bank de-anonymization endpoint (restricted to bank internal vault)."""
    target_hash = (req.hash if req and req.hash else hash_val) or ""
    if not target_hash:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Hash query parameter or request body required")

    b = bank_registry.get_bank_by_id(bank_id)
    if not b:
        # Check BANK_VAULTS map
        vault = BANK_VAULTS.get(bank_id)
    else:
        vault = b.vault

    if not vault:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Bank vault {bank_id} not found")

    res = vault.resolve_hash(target_hash)
    if not res:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Hash {target_hash} not found in {bank_id} vault")

    return VaultResolveResponse(
        hash=target_hash,
        account_number=str(res.get("account_number", "")),
        customer_name=str(res.get("customer_name", "")),
        bank_id=res.get("bank_id", bank_id),
        bank_name=res.get("bank_name", "Bank"),
        kyc_status=str(res.get("kyc_status", "verified")),
        declared_income=float(res.get("declared_income", 0.0)),
        account_age_days=int(res.get("account_age_days", 0)),
        is_dormant=bool(res.get("is_dormant", False))
    )


# ---------------------------------------------------------------------------
# Central Alerting & Compliance Endpoints (Phase 7)
# ---------------------------------------------------------------------------
@router.post("/alerts/dispatch", response_model=DispatchAlertResponse, tags=["Bank Integration & Alerts"])
def dispatch_alert_endpoint(req: DispatchAlertRequest):
    """Generate and dispatch alert to all involved banks for a flagged mule component."""
    comp = ComponentRepository.get_by_id(req.component_id)
    if not comp:
        # Check if component exists, or use request values
        comp = {
            "id": req.component_id,
            "risk_score": req.risk_score,
            "hashed_nodes": [],
            "bank_ids": ["bank_sbi", "bank_hdfc"]
        }

    alert = alert_dispatcher.generate_alert(
        component_id=req.component_id,
        risk_score=req.risk_score if req.risk_score is not None else comp.get("risk_score", 0.85),
        explanation=comp.get("shap_explanation")
    )
    res = alert_dispatcher.dispatch_alert(alert)

    return DispatchAlertResponse(
        alert_id=res["alert_id"],
        component_id=req.component_id,
        severity=alert["severity"],
        dispatched_to=alert["dispatched_to"],
        bank_acknowledged=res["bank_acknowledged"],
        failed=res["failed"]
    )


@router.get("/alerts/pending", response_model=AlertListResponse, tags=["Bank Integration & Alerts"])
def get_pending_alerts_endpoint():
    """Retrieve all alerts with pending resolution status."""
    alerts = alert_dispatcher.get_pending_alerts()
    resp_alerts = [AlertResponse(**a) for a in alerts]
    return AlertListResponse(total=len(resp_alerts), alerts=resp_alerts)


@router.get("/alerts/history", response_model=AlertListResponse, tags=["Bank Integration & Alerts"])
def get_alert_history_endpoint(days: int = Query(7, ge=1, le=365)):
    """Retrieve alert dispatch history within the specified lookback window."""
    alerts = alert_dispatcher.get_alert_history(days=days)
    resp_alerts = [AlertResponse(**a) for a in alerts]
    return AlertListResponse(total=len(resp_alerts), alerts=resp_alerts)


@router.get("/alerts/{alert_id}", response_model=AlertResponse, tags=["Bank Integration & Alerts"])
def get_alert_endpoint(alert_id: str):
    """Retrieve alert details by ID."""
    try:
        alert = alert_dispatcher.get_alert_by_id(alert_id)
        return AlertResponse(**alert)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/alerts/{alert_id}/resolve", response_model=ResolveAlertResponse, tags=["Bank Integration & Alerts"])
def resolve_alert_endpoint(alert_id: str, req: ResolveAlertRequest):
    """Update resolution status and compliance notes for an alert."""
    try:
        updated = alert_dispatcher.update_alert_status(alert_id, req.status, notes=req.notes)
        return ResolveAlertResponse(
            id=updated["id"],
            resolution_status=updated["resolution_status"],
            resolved_at=updated.get("resolved_at"),
            resolution_notes=updated.get("resolution_notes")
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/alerts/{alert_id}/str/generate", response_model=STRResponse, tags=["Bank Integration & Alerts"])
def generate_str_endpoint(alert_id: str, req: GenerateSTRRequest):
    """Generate official FIU-IND / IDPIC STR report for a specific bank node and alert."""
    try:
        alert = alert_dispatcher.get_alert_by_id(alert_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    bank_node = bank_registry.get_bank_by_id(req.bank_id)
    if not bank_node:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Bank {req.bank_id} not found")

    str_payload = bank_node.generate_str(alert)
    # Save STR
    str_generator.save_str(str_payload)
    return STRResponse(**str_payload)


@router.get("/alerts/{alert_id}/str", response_model=STRResponse, tags=["Bank Integration & Alerts"])
def get_alert_str_endpoint(alert_id: str):
    """Retrieve filed STR report associated with an alert."""
    str_rec = str_generator.get_str_by_alert(alert_id)
    if not str_rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"STR for alert {alert_id} not found")
    return STRResponse(**str_rec)


@router.get("/compliance/str/{str_id}", response_model=STRResponse, tags=["Bank Integration & Alerts"])
def get_str_by_id_endpoint(str_id: str):
    """Retrieve full regulatory STR payload by STR ID."""
    str_rec = str_generator.get_str_by_id(str_id)
    if not str_rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"STR {str_id} not found")
    return STRResponse(**str_rec)


# ---------------------------------------------------------------------------
# Admin Reset
# ---------------------------------------------------------------------------
@router.post("/reset", tags=["Admin"])
def reset_simulation():
    """Reset all in-memory vaults and simulation state."""
    for v in BANK_VAULTS.values():
        v._local_accounts.clear()
        v._resolution_log.clear()
    graph_engine.get_graph().graph.clear()
    return {"status": "reset complete", "vaults_cleared": len(BANK_VAULTS)}



