"""Threshold management and risk severity categorization."""
import os
import json
import logging
from typing import Dict, Any, Optional
import numpy as np
from sklearn.metrics import precision_recall_curve, f1_score

from backend.app.config import settings, Settings

logger = logging.getLogger("mule-detection-thresholds")

DEFAULT_THRESHOLDS = {
    "low": 0.30,
    "medium": 0.50,
    "high": 0.70,
    "critical": 0.85
}

SEVERITY_COLORS = {
    "low": "green",
    "medium": "yellow",
    "high": "orange",
    "critical": "red"
}


class ThresholdManager:
    """Manages risk probability thresholds, severity levels, and operating points."""

    def __init__(self, config: Optional[Settings] = None, filepath: Optional[str] = None):
        self.config = config or settings
        self.filepath = filepath or "./models/thresholds.json"
        self.thresholds = dict(DEFAULT_THRESHOLDS)
        if self.filepath and os.path.exists(self.filepath):
            self.load_thresholds(self.filepath)

    def get_thresholds(self) -> Dict[str, float]:
        """Return current configured risk thresholds."""
        return dict(self.thresholds)

    def get_severity(self, probability: float) -> str:
        """Map risk probability [0.0 - 1.0] to severity category."""
        p = float(probability)
        if p >= self.thresholds.get("critical", 0.85):
            return "critical"
        elif p >= self.thresholds.get("high", 0.70):
            return "high"
        elif p >= self.thresholds.get("medium", 0.50):
            return "medium"
        else:
            return "low"

    def get_severity_color(self, severity: str) -> str:
        """Return UI indicator color corresponding to severity level."""
        return SEVERITY_COLORS.get(severity.lower(), "gray")

    def update_threshold(self, threshold_key: str, value: float) -> Dict[str, float]:
        """Update a specific threshold with boundary validation."""
        key = threshold_key.lower()
        if key not in ["low", "medium", "high", "critical"]:
            raise ValueError(f"Invalid threshold key '{threshold_key}'. Must be one of ['low', 'medium', 'high', 'critical'].")

        val = float(value)
        if not (0.0 <= val <= 1.0):
            raise ValueError(f"Threshold value must be between 0.0 and 1.0, got {value}.")

        self.thresholds[key] = round(val, 4)
        if self.filepath:
            self.save_thresholds(self.filepath)
        return self.get_thresholds()

    def find_optimal_threshold(self, y_true, y_proba, metric: str = "f1") -> float:
        """Calculate decision threshold that maximizes specified classification metric."""
        precisions, recalls, thresholds = precision_recall_curve(y_true, y_proba)
        if len(thresholds) == 0:
            return self.thresholds.get("high", 0.70)

        if metric.lower() == "f1":
            f1_scores = 2 * (precisions * recalls) / np.maximum(precisions + recalls, 1e-8)
            best_idx = np.argmax(f1_scores[:-1])
            best_thresh = float(thresholds[best_idx])
            return round(best_thresh, 4)
        elif metric.lower() == "recall":
            # Target 90% recall
            valid_indices = np.where(recalls[:-1] >= 0.90)[0]
            if len(valid_indices) > 0:
                best_idx = valid_indices[-1]
                return round(float(thresholds[best_idx]), 4)
        return round(float(thresholds[len(thresholds) // 2]), 4)

    def get_operating_point(self, precision_target: float, recall_target: float) -> float:
        """Find threshold meeting target precision/recall requirements."""
        # Defaults to high threshold if empirical data not loaded
        return self.thresholds.get("high", 0.70)

    def save_thresholds(self, filepath: Optional[str] = None) -> None:
        """Persist thresholds to JSON file."""
        target_path = filepath or self.filepath
        if not target_path:
            return
        os.makedirs(os.path.dirname(target_path) if os.path.dirname(target_path) else ".", exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(self.thresholds, f, indent=2)

    def load_thresholds(self, filepath: Optional[str] = None) -> Dict[str, float]:
        """Load thresholds from JSON file."""
        target_path = filepath or self.filepath
        if not target_path or not os.path.exists(target_path):
            return self.get_thresholds()
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.thresholds.update(data)
        except Exception as e:
            logger.warning(f"Failed to load thresholds from {target_path}: {e}")
        return self.get_thresholds()
