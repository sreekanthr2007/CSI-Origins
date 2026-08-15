"""SHAP explainability engine and natural language rationale generation."""
import os
import logging
from typing import Dict, Any, List, Optional, Union
import joblib
import numpy as np
import pandas as pd
import shap

from backend.app.config import settings, Settings
from backend.app.ml.thresholds import ThresholdManager

logger = logging.getLogger("mule-detection-explainability")


class ExplainabilityEngine:
    """Computes SHAP feature attribution values and constructs human-readable audit rationales."""

    def __init__(
        self,
        model: Optional[Any] = None,
        feature_names: Optional[List[str]] = None,
        config: Optional[Settings] = None
    ):
        self.config = config or settings
        self.model = model
        self.feature_names = feature_names or (list(getattr(model, "feature_names_in_", [])) if model else [])
        self.explainer: Optional[shap.Explainer] = None
        self.threshold_manager = ThresholdManager(config=self.config)

    def _align_dataframe(self, X: Union[pd.DataFrame, Dict[str, Any], np.ndarray]) -> pd.DataFrame:
        """Align input features to the exact expected columns of the model."""
        if not self.feature_names and self.model is not None:
            self.feature_names = list(getattr(self.model, "feature_names_in_", []))

        if isinstance(X, dict):
            row = {col: float(X.get(col, 0.0) or 0.0) for col in self.feature_names} if self.feature_names else dict(X)
            return pd.DataFrame([row])
        elif isinstance(X, pd.DataFrame):
            if self.feature_names:
                df = pd.DataFrame(index=X.index)
                for col in self.feature_names:
                    df[col] = X[col] if col in X.columns else 0.0
                return df
            return X
        else:
            return pd.DataFrame(X, columns=self.feature_names if self.feature_names else None)

    def set_model(self, model: Any, feature_names: Optional[List[str]] = None) -> None:
        """Update active model and reset explainer cache."""
        self.model = model
        if feature_names:
            self.feature_names = feature_names
        elif model and hasattr(model, "feature_names_in_"):
            self.feature_names = list(model.feature_names_in_)
        self.explainer = None

    def get_explainer(self) -> shap.Explainer:
        """Create or return cached SHAP TreeExplainer for decision tree models."""
        if self.explainer is not None:
            return self.explainer

        if self.model is None:
            raise RuntimeError("Cannot create SHAP explainer: No model loaded.")

        try:
            # TreeExplainer is optimal for XGBoost and Random Forest
            self.explainer = shap.TreeExplainer(self.model)
        except Exception as e:
            logger.warning(f"TreeExplainer failed ({e}), falling back to generic Explainer.")
            self.explainer = shap.Explainer(self.model)

        return self.explainer

    def explain_prediction(self, X_sample: Union[pd.DataFrame, np.ndarray, Dict[str, Any]]) -> Any:
        """Compute SHAP attribution values for a single sample or return explanation data if dict."""
        if isinstance(X_sample, dict):
            aligned_df = self._align_dataframe(X_sample)
            return self.get_explanation_data(node_hash="component_target", X_sample=aligned_df)

        aligned_df = self._align_dataframe(X_sample)
        explainer = self.get_explainer()
        try:
            vals = explainer.shap_values(aligned_df)
        except Exception as err:
            logger.warning(f"SHAP explainer error ({err}), generating default attributions.")
            return np.zeros((1, len(aligned_df.columns)))

        if isinstance(vals, list):
            # For binary classification where list of [class 0, class 1] is returned
            return np.array(vals[1])
        return np.array(vals)

    def explain_batch(self, X_samples: pd.DataFrame) -> np.ndarray:
        """Compute SHAP values for a batch of samples."""
        return self.explain_prediction(X_samples)

    def get_explanation_data(
        self,
        node_hash: str,
        X_sample: pd.DataFrame,
        probability: Optional[float] = None
    ) -> Dict[str, Any]:
        """Extract formatted SHAP attribution data for UI rendering and audits."""
        aligned_df = self._align_dataframe(X_sample)
        shap_vals = self.explain_prediction(aligned_df)
        if shap_vals.ndim > 1:
            shap_vals = shap_vals[0]

        feature_cols = list(aligned_df.columns)
        sample_vals = aligned_df.iloc[0].to_dict()


        # Compute probability if not passed
        prob = probability
        if prob is None and self.model is not None:
            try:
                prob = float(self.model.predict_proba(X_sample)[:, 1][0])
            except Exception:
                prob = 0.50
        elif prob is None:
            prob = 0.50

        sev = self.threshold_manager.get_severity(prob)
        is_mule = bool(prob >= self.threshold_manager.thresholds.get("medium", 0.50))

        # Build feature attribution list
        attributions: List[Dict[str, Any]] = []
        for feat, val, s_val in zip(feature_cols, [sample_vals.get(c, 0.0) for c in feature_cols], shap_vals):
            direction = "positive" if s_val > 0 else "negative"
            attributions.append({
                "feature": feat,
                "value": round(float(val), 4),
                "shap": round(float(s_val), 4),
                "abs_shap": abs(round(float(s_val), 4)),
                "direction": direction
            })

        # Sort descending by absolute SHAP impact
        attributions.sort(key=lambda item: item["abs_shap"], reverse=True)

        summary_text = self.generate_explanation(node_hash, X_sample, probability=prob, attributions=attributions)

        return {
            "node_hash": node_hash,
            "probability": round(prob, 4),
            "is_mule": is_mule,
            "severity": sev,
            "severity_color": self.threshold_manager.get_severity_color(sev),
            "feature_importance": attributions,
            "top_drivers": [a["feature"] for a in attributions[:5]],
            "summary": summary_text
        }

    def generate_explanation(
        self,
        node_hash: str,
        X_sample: pd.DataFrame,
        probability: Optional[float] = None,
        attributions: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """Generate human-readable natural language audit rationale."""
        if attributions is None:
            data = self.get_explanation_data(node_hash, X_sample, probability=probability)
            attributions = data.get("feature_importance", [])

        prob = probability if probability is not None else 0.85
        prob_pct = int(prob * 100)

        # Sample values lookup
        sample_dict = X_sample.iloc[0].to_dict() if isinstance(X_sample, pd.DataFrame) else {}

        bullet_points: List[str] = []
        
        # 1. Pass-through ratio
        pt = sample_dict.get("pass_through_ratio")
        if pt is not None and pt >= 0.70:
            bullet_points.append(f"{pt*100:.1f}% pass-through ratio (rapid outflow of incoming funds within window)")

        # 2. Path / chain length
        chain = sample_dict.get("total_path_length")
        if chain is not None and chain >= 3:
            bullet_points.append(f"{int(chain)}-hop cross-bank transaction chain detected")

        # 3. Temporal velocity
        vel = sample_dict.get("avg_time_between_incoming_and_outgoing")
        if vel is not None and 0 < vel <= 60.0:
            bullet_points.append(f"{vel:.1f}-minute average hold time between fund receipt and disbursement")

        # 4. Asymmetry / Fan
        asym = sample_dict.get("asymmetry_score")
        if asym is not None and asym >= 0.60:
            bullet_points.append("High fan-in/fan-out counterparty asymmetry (collector/distributor topology)")

        # 5. First-time edges
        ft = sample_dict.get("first_time_edge_ratio")
        if ft is not None and ft >= 0.75:
            bullet_points.append("First-time transaction anomaly across counterparties")

        # 6. Local bank risk score
        risk = sample_dict.get("local_risk_score")
        if risk is not None and risk >= 0.50:
            bullet_points.append(f"Elevated internal bank risk score: {risk:.2f}")

        # 7. Structuring score
        struct = sample_dict.get("structuring_score")
        if struct is not None and struct > 0.30:
            bullet_points.append("Transaction structuring near reporting thresholds (e.g. INR 50,000 PAN limit)")

        if not bullet_points:
            # Fallback to top 3 SHAP drivers
            top_feats = attributions[:3]
            for tf in top_feats:
                bullet_points.append(f"Elevated {tf['feature'].replace('_', ' ')} (impact: {tf['shap']:+.2f})")

        header = f"Account {node_hash} is flagged as a potential mule ({prob_pct}% probability) due to:"
        formatted_bullets = "\n".join([f"- {b}" for b in bullet_points])
        return f"{header}\n{formatted_bullets}"

    def get_feature_importance_plot(self, top_n: int = 10) -> Dict[str, Any]:
        """Return global feature attribution data formatted for UI charting."""
        if self.model is None or not self.feature_names:
            return {"features": [], "importance": []}

        importances = getattr(self.model, "feature_importances_", None)
        if importances is None:
            return {"features": [], "importance": []}

        sorted_pairs = sorted(zip(self.feature_names, importances), key=lambda x: x[1], reverse=True)[:top_n]
        return {
            "features": [p[0] for p in sorted_pairs],
            "importance": [round(float(p[1]), 4) for p in sorted_pairs]
        }

    def get_global_importance(self) -> Dict[str, float]:
        """Return global feature importance mapping."""
        plot_data = self.get_feature_importance_plot(top_n=len(self.feature_names))
        return dict(zip(plot_data["features"], plot_data["importance"]))

    def get_feature_dependence(self, feature_name: str, X_data: pd.DataFrame) -> Dict[str, Any]:
        """Extract SHAP feature dependence data for visualization."""
        if feature_name not in X_data.columns:
            return {"feature": feature_name, "x": [], "y": []}

        shap_vals = self.explain_batch(X_data)
        feat_idx = list(X_data.columns).index(feature_name)
        feat_shap = shap_vals[:, feat_idx]
        feat_raw = X_data[feature_name].values

        return {
            "feature": feature_name,
            "x": [round(float(v), 4) for v in feat_raw[:200]],
            "y": [round(float(v), 4) for v in feat_shap[:200]]
        }

    def save_explainer(self, filepath: str) -> None:
        """Persist SHAP explainer to disk using joblib."""
        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)
        joblib.dump(self.explainer, filepath)
        logger.info(f"SHAP explainer saved to {filepath}")

    def load_explainer(self, filepath: str) -> None:
        """Load SHAP explainer from disk."""
        if os.path.exists(filepath):
            self.explainer = joblib.load(filepath)
            logger.info(f"SHAP explainer loaded from {filepath}")
