"""Unit tests for ML classifier and explainability engine."""
from backend.app.ml.classifier import MuleClassifier
from backend.app.ml.explainability import ExplainabilityEngine


def test_mule_classifier_default():
    clf = MuleClassifier()
    score = clf.predict_risk_score({"pass_through": 0.95})
    assert 0.0 <= score <= 1.0


def test_explainability_engine_output():
    engine = ExplainabilityEngine()
    explanation = engine.explain({"pass_through": 0.95}, 0.88)
    assert "top_drivers" in explanation
    assert "narrative" in explanation
