"""End-to-end ML model training pipeline and artifact generation."""
import os
import json
import time
import logging
from typing import Dict, Any, Optional

from backend.app.config import settings, Settings
from backend.app.ml.dataset import DatasetBuilder
from backend.app.ml.classifier import MuleClassifier
from backend.app.ml.explainability import ExplainabilityEngine
from backend.app.ml.thresholds import ThresholdManager

logger = logging.getLogger("mule-detection-ml-training")


class TrainingPipeline:
    """Orchestrates synthetic dataset preparation, classifier training, SHAP attribution, and model artifact persistence."""

    def __init__(self, config: Optional[Settings] = None):
        self.config = config or settings
        self.dataset_builder = DatasetBuilder(config=self.config)
        self.classifier = MuleClassifier(config=self.config)
        self.explainability_engine = ExplainabilityEngine(config=self.config)
        self.threshold_manager = ThresholdManager(config=self.config)

    def run_training_pipeline(
        self,
        num_banks: Optional[int] = None,
        num_accounts_per_bank: Optional[int] = None,
        num_edges: Optional[int] = None,
        contamination_rate: Optional[float] = None,
        model_type: str = "xgboost",
        save_artifacts: bool = True
    ) -> Dict[str, Any]:
        """Execute end-to-end training cycle and persist production artifacts."""
        start_time = time.time()
        logger.info(f"Starting ML training pipeline ({model_type})...")

        # 1. Build Dataset
        df = self.dataset_builder.build_dataset(
            num_banks=num_banks,
            num_accounts_per_bank=num_accounts_per_bank,
            num_edges=num_edges,
            contamination_rate=contamination_rate
        )

        # 2. Train / Test Split
        X_train, X_test, y_train, y_test = self.dataset_builder.split_dataset(df)

        # 3. Train Classifier
        self.classifier.train(X_train, y_train, model_type=model_type)

        # 4. Evaluate Classifier
        metrics = self.classifier.evaluate(X_test, y_test)

        # 5. Build SHAP Explainer
        self.explainability_engine.set_model(self.classifier.model, self.classifier.feature_names)
        try:
            self.explainability_engine.get_explainer()
        except Exception as e:
            logger.warning(f"Explainer initialization notice: {e}")

        # 6. Feature Importance & Thresholds
        feat_imp = self.classifier.get_feature_importance()
        thresholds = self.threshold_manager.get_thresholds()

        duration = round(time.time() - start_time, 2)

        summary = {
            "model_type": self.classifier.model_type,
            "training_time_seconds": duration,
            "accuracy": metrics["accuracy"],
            "precision": metrics["precision"],
            "recall": metrics["recall"],
            "f1": metrics["f1"],
            "auc_roc": metrics["auc_roc"],
            "confusion_matrix": metrics["confusion_matrix"],
            "dataset_size": len(df),
            "train_size": len(X_train),
            "test_size": len(X_test),
            "num_features": len(self.classifier.feature_names),
            "feature_names": self.classifier.feature_names,
            "feature_importance": feat_imp,
            "thresholds": thresholds
        }

        # 7. Save Artifacts
        if save_artifacts:
            models_dir = os.path.dirname(self.config.MODEL_PATH) or "./models"
            os.makedirs(models_dir, exist_ok=True)

            self.classifier.save_model(self.config.MODEL_PATH)

            shap_path = os.path.join(models_dir, "shap_explainer.pkl")
            try:
                self.explainability_engine.save_explainer(shap_path)
            except Exception as e:
                logger.warning(f"Could not persist SHAP explainer: {e}")

            report_path = os.path.join(models_dir, "training_report.json")
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2)

            self.threshold_manager.save_thresholds(os.path.join(models_dir, "thresholds.json"))

            logger.info(f"Training completed successfully in {duration}s. Report saved to {report_path}")

        return summary


def run_training_pipeline(
    config: Optional[Settings] = None,
    num_banks: Optional[int] = None,
    num_accounts_per_bank: Optional[int] = None,
    num_edges: Optional[int] = None,
    contamination_rate: Optional[float] = None,
    model_type: str = "xgboost"
) -> Dict[str, Any]:
    """Convenience function to run training pipeline."""
    pipeline = TrainingPipeline(config=config)
    return pipeline.run_training_pipeline(
        num_banks=num_banks,
        num_accounts_per_bank=num_accounts_per_bank,
        num_edges=num_edges,
        contamination_rate=contamination_rate,
        model_type=model_type
    )
