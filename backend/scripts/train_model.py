"""Standalone CLI script to train, evaluate, and save ML model and SHAP explainability artifacts."""
import sys
import os
import time
import json
import logging

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.app.config import settings
from backend.app.ml.training import TrainingPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("train-model-cli")


def main():
    print("=" * 75)
    print("CROSS-BANK MULE ACCOUNT DETECTION NETWORK — MODEL TRAINING PIPELINE")
    print("=" * 75)

    print("\n[Step 1/3] Synthesizing Cross-Bank Data & Extracting Feature Vectors...")
    t0 = time.time()
    pipeline = TrainingPipeline(config=settings)

    summary = pipeline.run_training_pipeline(
        num_banks=10,
        num_accounts_per_bank=80,
        num_edges=3500,
        contamination_rate=0.15,
        model_type="xgboost",
        save_artifacts=True
    )
    total_time = time.time() - t0

    print("\n" + "=" * 75)
    print("MODEL TRAINING & EVALUATION REPORT")
    print("=" * 75)
    print(f"  * Classifier Model:       {summary['model_type'].upper()}")
    print(f"  * Total Samples:           {summary['dataset_size']:,} accounts")
    print(f"  * Training Set Size:       {summary['train_size']:,}")
    print(f"  * Test Set Size:           {summary['test_size']:,}")
    print(f"  * Total Extracted Features:{summary['num_features']}")
    print(f"  * Accuracy:                {summary['accuracy']*100:.2f}%")
    print(f"  * Precision:               {summary['precision']*100:.2f}%")
    print(f"  * Recall:                  {summary['recall']*100:.2f}%")
    print(f"  * F1-Score:                {summary['f1']:.4f}")
    print(f"  * ROC-AUC:                 {summary['auc_roc']:.4f}")
    print(f"  * Training Duration:       {summary['training_time_seconds']:.2f}s (Total: {total_time:.2f}s)")

    print("\n  [TOP 5 PREDICTIVE GRAPH FEATURES]")
    top_5 = list(summary["feature_importance"].items())[:5]
    for feat, imp in top_5:
        print(f"    - {feat:<35}: {imp:.4f}")

    print("\n  [OPERATIONAL RISK THRESHOLDS]")
    for sev, thresh in summary["thresholds"].items():
        print(f"    - {sev.capitalize():<10}: >= {thresh:.2f}")

    print("\n  [ARTIFACTS GENERATED]")
    print(f"    - Model Artifact:    {settings.MODEL_PATH}")
    print(f"    - SHAP Explainer:    ./models/shap_explainer.pkl")
    print(f"    - Training Report:   ./models/training_report.json")
    print(f"    - Thresholds Config: ./models/thresholds.json")

    print("\n[SUCCESS] Phase 5 Model Training & Explainability pipeline completed!")
    print("=" * 75)


if __name__ == "__main__":
    main()
