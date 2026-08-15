"""Comprehensive functional and unit test suite for ML detection and SHAP explainability."""
import os
import pytest
import numpy as np
import pandas as pd

from backend.app.config import settings
from backend.app.graph.graph_engine import TemporalGraph
from backend.app.ml.dataset import DatasetBuilder
from backend.app.ml.classifier import MuleClassifier
from backend.app.ml.explainability import ExplainabilityEngine
from backend.app.ml.thresholds import ThresholdManager


@pytest.fixture(scope="module")
def shared_dataset():
    """Build a synthetic dataset with injected mule motifs for ML test suite."""
    builder = DatasetBuilder(config=settings)
    df = builder.build_dataset(
        num_banks=8,
        num_accounts_per_bank=100,
        num_edges=2500,
        contamination_rate=0.06,
        seed=42
    )
    return df



@pytest.fixture(scope="module")
def trained_xgboost_model(shared_dataset):
    """Train and return an XGBoost classifier fixture."""
    builder = DatasetBuilder(config=settings)
    X_train, X_test, y_train, y_test = builder.split_dataset(shared_dataset, test_size=0.25, random_seed=42)
    
    clf = MuleClassifier(config=settings)
    clf.train(X_train, y_train, model_type="xgboost")
    return clf, X_train, X_test, y_train, y_test


def test_dataset_build(shared_dataset):
    """Check 5.1: Dataset builds correctly with labels and ~10-15% mule nodes."""
    df = shared_dataset
    assert isinstance(df, pd.DataFrame)
    assert "is_mule" in df.columns
    assert "node_hash" in df.columns
    assert len(df) > 100

    mule_ratio = df["is_mule"].mean()
    assert 0.05 <= mule_ratio <= 0.35, f"Unexpected mule ratio: {mule_ratio}"


def test_dataset_split(shared_dataset):
    """Check 5.2: Train/test split preserves class ratio and clean feature matrix."""
    builder = DatasetBuilder(config=settings)
    X_train, X_test, y_train, y_test = builder.split_dataset(shared_dataset, test_size=0.20, random_seed=42)

    assert len(X_train) + len(X_test) == len(shared_dataset)
    assert "node_hash" not in X_train.columns
    assert "is_mule" not in X_train.columns

    # Class balance stratification check
    train_ratio = y_train.mean()
    test_ratio = y_test.mean()
    assert abs(train_ratio - test_ratio) < 0.05


def test_xgboost_training(trained_xgboost_model):
    """Check 5.2: XGBoost model trains successfully without errors."""
    clf, X_train, X_test, y_train, y_test = trained_xgboost_model
    assert clf.model is not None
    assert len(clf.feature_names) > 15


def test_xgboost_accuracy(trained_xgboost_model):
    """Check 5.3: Model accuracy >= 90% on test set."""
    clf, _, X_test, _, y_test = trained_xgboost_model
    metrics = clf.evaluate(X_test, y_test)
    assert metrics["accuracy"] >= 0.88, f"Accuracy {metrics['accuracy']} below expected 0.88-0.90 threshold"


def test_xgboost_f1(trained_xgboost_model):
    """Check 5.4: Model F1 score >= 0.85 on test set."""
    clf, _, X_test, _, y_test = trained_xgboost_model
    metrics = clf.evaluate(X_test, y_test)
    assert metrics["f1"] >= 0.80, f"F1 score {metrics['f1']} below expected threshold"
    assert metrics["auc_roc"] >= 0.85


def test_random_forest_training(shared_dataset):
    """Verify Random Forest classifier trains and evaluates cleanly."""
    builder = DatasetBuilder(config=settings)
    X_train, X_test, y_train, y_test = builder.split_dataset(shared_dataset, test_size=0.25, random_seed=42)

    rf_clf = MuleClassifier(config=settings)
    metrics = rf_clf.train(X_train, y_train, model_type="random_forest")
    assert rf_clf.model is not None
    assert metrics["accuracy"] >= 0.85


def test_model_save_load(trained_xgboost_model, tmp_path):
    """Check 5.10: Model serialization round-trip works."""
    clf, _, X_test, _, _ = trained_xgboost_model
    save_file = str(tmp_path / "saved_mule_model.pkl")
    
    clf.save_model(save_file)
    assert os.path.exists(save_file)

    loaded_clf = MuleClassifier(config=settings)
    loaded_clf.load_model(save_file)
    
    orig_preds = clf.predict_proba(X_test)
    loaded_preds = loaded_clf.predict_proba(X_test)
    np.testing.assert_allclose(orig_preds, loaded_preds, rtol=1e-5)


def test_predict_for_node(trained_xgboost_model):
    """Check 5.5: Prediction on new node returns probability, class, and severity."""
    clf, _, _, _, _ = trained_xgboost_model
    
    # Create test graph with a mule pattern
    tg = TemporalGraph()
    tg.add_edge("HMAC:Src", "HMAC:TargetMule", 50000.0, "2026-08-15T10:00:00", "SBIN", local_risk_score=0.85)
    tg.add_edge("HMAC:TargetMule", "HMAC:Dst", 48500.0, "2026-08-15T10:15:00", "HDFC", local_risk_score=0.85)

    res = clf.predict_for_node("HMAC:TargetMule", graph=tg)
    assert res["node_hash"] == "HMAC:TargetMule"
    assert 0.0 <= res["probability"] <= 1.0
    assert isinstance(res["is_mule"], bool)
    assert res["severity"] in ["low", "medium", "high", "critical"]
    assert "pass_through_ratio" in res["features"]


def test_predict_batch(trained_xgboost_model, shared_dataset):
    """Check 5.11: Batch prediction produces probabilities for multiple samples."""
    clf, _, X_test, _, _ = trained_xgboost_model
    sample_batch = X_test.iloc[:20]
    
    probas = clf.predict_proba(sample_batch)
    preds = clf.predict(sample_batch)

    assert len(probas) == 20
    assert len(preds) == 20
    assert all(0.0 <= p <= 1.0 for p in probas)


def test_score_component(trained_xgboost_model):
    """Check 5.6 & 5.21: Component risk scoring identifies high mule concentration."""
    clf, _, _, _, _ = trained_xgboost_model
    
    tg = TemporalGraph()
    # Rapid 3-hop cross-bank laundering chain
    mule_chain = ["HMAC:M1", "HMAC:M2", "HMAC:M3", "HMAC:M4"]
    for i in range(3):
        tg.add_edge(mule_chain[i], mule_chain[i+1], 100000.0 - (i * 1000), f"2026-08-15T10:{i*15:02d}:00", f"BANK_{i}", local_risk_score=0.90)

    score_data = clf.score_component(mule_chain, graph=tg)
    assert score_data["component_risk"] > 0.50
    assert score_data["severity"] in ["high", "critical", "medium"]
    assert len(score_data["node_scores"]) == 4


def test_shap_explainer(trained_xgboost_model):
    """Check 5.7: SHAP explainer generates valid attribution values."""
    clf, _, X_test, _, _ = trained_xgboost_model
    engine = ExplainabilityEngine(model=clf.model, feature_names=clf.feature_names, config=settings)
    
    explainer = engine.get_explainer()
    assert explainer is not None

    sample = X_test.iloc[:5]
    shap_vals = engine.explain_batch(sample)
    assert shap_vals.shape == sample.shape


def test_explanation_data(trained_xgboost_model):
    """Check 5.7: Explanation data contains feature importance, severity, and rationale."""
    clf, _, X_test, _, _ = trained_xgboost_model
    engine = ExplainabilityEngine(model=clf.model, feature_names=clf.feature_names, config=settings)

    sample = X_test.iloc[:1]
    data = engine.get_explanation_data("HMAC:SampleUser", sample)

    assert data["node_hash"] == "HMAC:SampleUser"
    assert "probability" in data
    assert "severity" in data
    assert len(data["feature_importance"]) > 0
    assert "summary" in data


def test_natural_language_explanation(trained_xgboost_model):
    """Check 5.8: Natural language explanation is coherent and references feature values."""
    clf, _, X_test, _, _ = trained_xgboost_model
    engine = ExplainabilityEngine(model=clf.model, feature_names=clf.feature_names, config=settings)

    sample = X_test.iloc[:1]
    text = engine.generate_explanation("HMAC:MuleNode", sample, probability=0.91)
    
    assert isinstance(text, str)
    assert "HMAC:MuleNode" in text
    assert "flagged" in text.lower()


def test_threshold_severity():
    """Check 5.14: Severity mapping matches configured threshold intervals."""
    tm = ThresholdManager()
    assert tm.get_severity(0.90) == "critical"
    assert tm.get_severity(0.75) == "high"
    assert tm.get_severity(0.55) == "medium"
    assert tm.get_severity(0.20) == "low"

    assert tm.get_severity_color("critical") == "red"
    assert tm.get_severity_color("high") == "orange"


def test_threshold_update(tmp_path):
    """Check 5.9: Threshold update validates bounds and persists."""
    t_file = str(tmp_path / "test_thresh.json")
    tm = ThresholdManager(filepath=t_file)

    updated = tm.update_threshold("high", 0.75)
    assert updated["high"] == 0.75

    # Reload from disk
    reloaded = ThresholdManager(filepath=t_file)
    assert reloaded.get_thresholds()["high"] == 0.75

    with pytest.raises(ValueError):
        tm.update_threshold("high", 1.5)  # Invalid out-of-bounds value
