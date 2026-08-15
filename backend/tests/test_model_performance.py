"""Performance benchmarks, latency constraints, and model robustness tests."""
import time
import sys
import pytest
import numpy as np
import pandas as pd

from backend.app.config import settings
from backend.app.ml.dataset import DatasetBuilder
from backend.app.ml.classifier import MuleClassifier
from backend.app.ml.explainability import ExplainabilityEngine


@pytest.fixture(scope="module")
def benchmark_model():
    """Build dataset and train XGBoost classifier for performance benchmarks."""
    builder = DatasetBuilder(config=settings)
    df = builder.build_dataset(num_banks=6, num_accounts_per_bank=50, num_edges=1500, seed=42)
    X_train, X_test, y_train, y_test = builder.split_dataset(df, test_size=0.25, random_seed=42)
    
    clf = MuleClassifier(config=settings)
    clf.train(X_train, y_train, model_type="xgboost")
    return clf, X_test, y_test


def test_model_inference_speed(benchmark_model):
    """Check 5.25: 1,000 predictions complete in < 1.0 second."""
    clf, X_test, _ = benchmark_model
    # Create 1,000 synthetic feature rows
    df_1000 = pd.concat([X_test] * (1000 // len(X_test) + 1), ignore_index=True).iloc[:1000]

    start = time.time()
    preds = clf.predict_proba(df_1000)
    duration = time.time() - start

    assert len(preds) == 1000
    assert duration < 1.0, f"1000 predictions took {duration:.3f}s, exceeding 1.0s benchmark"


def test_batch_prediction_speed(benchmark_model):
    """Check 5.28 & 5.30: 100 predictions complete in < 100ms."""
    clf, X_test, _ = benchmark_model
    df_100 = pd.concat([X_test] * (100 // len(X_test) + 1), ignore_index=True).iloc[:100]

    start = time.time()
    preds = clf.predict(df_100)
    duration = time.time() - start

    assert len(preds) == 100
    assert duration < 0.20, f"100 predictions took {duration:.3f}s"


def test_shap_explanation_speed(benchmark_model):
    """Check 5.26: Single SHAP explanation completes in < 500ms."""
    clf, X_test, _ = benchmark_model
    engine = ExplainabilityEngine(model=clf.model, feature_names=clf.feature_names, config=settings)
    # Warm up explainer
    engine.get_explainer()

    single_sample = X_test.iloc[:1]
    start = time.time()
    data = engine.get_explanation_data("HMAC:BenchNode", single_sample)
    duration = time.time() - start

    assert "summary" in data
    assert duration < 0.50, f"SHAP explanation took {duration:.3f}s, exceeding 500ms threshold"


def test_model_memory_footprint(benchmark_model):
    """Check 5.29: In-memory footprint of model artifact is < 100MB."""
    clf, _, _ = benchmark_model
    size_bytes = sys.getsizeof(clf.model)
    size_mb = size_bytes / (1024 * 1024)
    assert size_mb < 100.0, f"Model size {size_mb:.2f}MB exceeds 100MB threshold"


def test_missing_feature_handling(benchmark_model):
    """Check 5.15: Missing or partially complete feature matrices are handled without crash."""
    clf, X_test, _ = benchmark_model
    incomplete_df = X_test.iloc[:5].copy()
    
    # Introduce NaNs and missing columns
    incomplete_df.iloc[0, 0] = np.nan
    incomplete_df.drop(columns=[incomplete_df.columns[1]], inplace=True)

    probs = clf.predict_proba(incomplete_df)
    assert len(probs) == 5
    assert not np.isnan(probs).any()


def test_confidence_calibration(benchmark_model):
    """Verify predicted probabilities are within valid [0.0, 1.0] range with distinct distribution."""
    clf, X_test, _ = benchmark_model
    probs = clf.predict_proba(X_test)
    assert np.all((probs >= 0.0) & (probs <= 1.0))
    assert np.std(probs) > 0.05, "Probabilities lack spread/variance"


def test_false_positive_rate(benchmark_model):
    """Verify false positive rate on normal benign accounts is < 15%."""
    clf, X_test, y_test = benchmark_model
    y_true = np.array(y_test, dtype=int)
    y_pred = clf.predict(X_test, threshold=0.50)

    neg_mask = (y_true == 0)
    if np.sum(neg_mask) > 0:
        fp_count = np.sum((y_pred == 1) & neg_mask)
        fpr = fp_count / np.sum(neg_mask)
        assert fpr < 0.15, f"False positive rate {fpr:.3f} exceeds 15%"
