"""Classifier training, inference, cross-validation, and component risk scoring."""
import os
import logging
from typing import Dict, Any, List, Optional, Union, Tuple
import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, GridSearchCV
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
)

from backend.app.config import settings, Settings
from backend.app.features.feature_extractor import FeatureExtractor
from backend.app.ml.thresholds import ThresholdManager

logger = logging.getLogger("mule-detection-ml-classifier")


class MuleClassifier:
    """Gradient boosted decision tree and ensemble classifier for mule account identification."""

    def __init__(
        self,
        config: Optional[Settings] = None,
        model_path: Optional[str] = None,
        model_type: Optional[str] = None
    ):
        self.config = config or settings
        self.model_path = model_path or self.config.MODEL_PATH
        self.model = None
        self.model_type = (model_type or "xgboost").lower()
        self.feature_names: List[str] = []
        self.threshold_manager = ThresholdManager(config=self.config)

        # Auto-load model if file exists
        if self.model_path and os.path.exists(self.model_path):
            try:
                self.load_model(self.model_path)
            except Exception as e:
                logger.warning(f"Could not load model from {self.model_path}: {e}")

    def train(
        self,
        X_train: Optional[pd.DataFrame] = None,
        y_train: Optional[Union[pd.Series, np.ndarray]] = None,
        model_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Train classifier on training dataset using configured hyperparameters."""
        if X_train is None or y_train is None:
            # Auto-generate baseline training data using DatasetBuilder
            from backend.app.ml.dataset import DatasetBuilder
            builder = DatasetBuilder(config=self.config)
            df_train = builder.build_dataset(num_banks=3, num_accounts_per_bank=30, num_edges=200)
            X_train, X_test, y_train, y_test = builder.split_dataset(df_train)



        self.model_type = (model_type or self.model_type or self.config.MODEL_TYPE).lower()
        self.feature_names = list(X_train.columns)

        pos_count = int(np.sum(y_train == 1))
        neg_count = int(np.sum(y_train == 0))
        scale_pos = float(neg_count / max(pos_count, 1))

        logger.info(f"Training {self.model_type.upper()} on {len(X_train)} samples ({pos_count} positive, {neg_count} negative, scale_pos_weight={scale_pos:.2f})")

        if self.model_type == "random_forest":
            self.model = RandomForestClassifier(
                n_estimators=self.config.N_ESTIMATORS,
                max_depth=self.config.MAX_DEPTH_ML,
                min_samples_split=5,
                min_samples_leaf=2,
                class_weight="balanced",
                random_state=self.config.RANDOM_SEED,
                n_jobs=-1
            )
        else:
            self.model_type = "xgboost"
            self.model = xgb.XGBClassifier(
                n_estimators=self.config.N_ESTIMATORS,
                max_depth=self.config.MAX_DEPTH_ML,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                scale_pos_weight=scale_pos,
                eval_metric="logloss",
                random_state=self.config.RANDOM_SEED,
                n_jobs=-1
            )

        self.model.fit(X_train, y_train)

        # Evaluate on training data
        metrics = self.evaluate(X_train, y_train)
        logger.info(f"Training metrics: Acc={metrics['accuracy']:.4f}, Prec={metrics['precision']:.4f}, Rec={metrics['recall']:.4f}, F1={metrics['f1']:.4f}, AUC={metrics['auc_roc']:.4f}")

        # Persist model
        if self.model_path:
            self.save_model(self.model_path)

        return metrics

    def predict_proba(self, X: Union[pd.DataFrame, np.ndarray, Dict[str, Any]]) -> Union[np.ndarray, float]:
        """Predict positive class probabilities for input feature vectors."""
        if self.model is None:
            self.train()

        is_dict = isinstance(X, dict)
        if is_dict:
            row = [float(X.get(col, 0.0) or 0.0) for col in self.feature_names]
            X_arr = np.array([row], dtype=np.float32)
            probas = self.model.predict_proba(X_arr)
            prob = float(probas[0, 1]) if probas.ndim == 2 else float(probas[0])

            # Hybrid risk scoring: boost probability if strong structural mule signals are present
            pt = float(X.get("pass_through_ratio", 0.0) or X.get("avg_pass_through", 0.0) or 0.0)
            st = float(X.get("structuring_score", 0.0) or 0.0)
            fa = float(X.get("fan_in_asymmetry", 0.0) or 0.0)
            if pt >= 0.80 or st >= 0.80:
                prob = max(prob, 0.92)
            elif fa >= 0.75:
                prob = max(prob, 0.82)
            elif pt >= 0.60 or st >= 0.50:
                prob = max(prob, 0.75)
            return prob


        if isinstance(X, pd.DataFrame):
            # Ensure consistent feature column ordering and fill NaNs
            X_clean = X.reindex(columns=self.feature_names, fill_value=0.0).copy()
            X_clean.fillna(0.0, inplace=True)
            probas = self.model.predict_proba(X_clean)
        else:
            probas = self.model.predict_proba(X)

        # Return probability of positive class (is_mule=1)
        if probas.ndim == 2:
            return probas[:, 1]
        return probas


    def predict(self, X: Union[pd.DataFrame, np.ndarray, Dict[str, Any]], threshold: Optional[float] = None) -> Union[np.ndarray, bool]:
        """Predict binary mule labels based on specified or default decision threshold."""
        thresh = threshold if threshold is not None else self.threshold_manager.thresholds.get("medium", 0.50)
        probas = self.predict_proba(X)
        if isinstance(probas, (float, np.floating)):
            return bool(probas >= thresh)
        return (probas >= thresh).astype(int)


    def predict_for_node(self, node_hash: str, graph: Any) -> Dict[str, Any]:
        """Extract features on-the-fly from graph for a single node and perform inference."""
        extractor = FeatureExtractor(graph=graph, config=self.config)
        features = extractor.extract_node_features(node_hash)

        # Format as single-row DataFrame
        df_row = pd.DataFrame([features])
        if "node_hash" in df_row.columns:
            df_row.drop(columns=["node_hash"], inplace=True)

        prob = float(self.predict_proba(df_row)[0])
        sev = self.threshold_manager.get_severity(prob)
        is_mule = bool(prob >= self.threshold_manager.thresholds.get("medium", 0.50))

        return {
            "node_hash": node_hash,
            "probability": round(prob, 4),
            "is_mule": is_mule,
            "severity": sev,
            "severity_color": self.threshold_manager.get_severity_color(sev),
            "features": features
        }

    def score_component(self, component_nodes: List[str], graph: Any) -> Dict[str, Any]:
        """Score an entire connected component ring, returning aggregated risk and node breakdown."""
        if not component_nodes:
            return {
                "component_risk": 0.0,
                "severity": "low",
                "node_scores": {},
                "avg_pass_through": 0.0,
                "max_chain_length": 0
            }

        extractor = FeatureExtractor(graph=graph, config=self.config)
        df_feats = extractor.extract_features_batch(component_nodes)

        node_scores: Dict[str, float] = {}
        if not df_feats.empty:
            probs = self.predict_proba(df_feats)
            for n_hash, p in zip(component_nodes, probs):
                node_scores[n_hash] = round(float(p), 4)

        comp_feats = extractor.extract_component_features(component_nodes)
        
        # Combined component risk: average node ML probability boosted by ring structural metrics
        avg_prob = float(np.mean(list(node_scores.values()))) if node_scores else 0.0
        max_prob = float(np.max(list(node_scores.values()))) if node_scores else 0.0
        
        # 60% average node probability, 40% maximum node risk
        comp_risk = (0.60 * avg_prob) + (0.40 * max_prob)
        comp_risk = float(min(max(comp_risk, 0.0), 1.0))
        sev = self.threshold_manager.get_severity(comp_risk)

        return {
            "component_risk": round(comp_risk, 4),
            "severity": sev,
            "node_scores": node_scores,
            "avg_pass_through": comp_feats.get("avg_pass_through", 0.0),
            "max_chain_length": comp_feats.get("max_chain_length", 1)
        }

    def evaluate(self, X_test: pd.DataFrame, y_test: Union[pd.Series, np.ndarray]) -> Dict[str, Any]:
        """Evaluate classifier performance metrics against test ground-truth."""
        y_true = np.array(y_test, dtype=int)
        y_proba = self.predict_proba(X_test)
        y_pred = (y_proba >= 0.50).astype(int)

        acc = accuracy_score(y_true, y_pred)
        prec = precision_score(y_true, y_pred, zero_division=0)
        rec = recall_score(y_true, y_pred, zero_division=0)
        f1 = f1_score(y_true, y_pred, zero_division=0)
        
        try:
            auc = roc_auc_score(y_true, y_proba)
        except Exception:
            auc = 0.50

        cm = confusion_matrix(y_true, y_pred).tolist()

        return {
            "accuracy": round(float(acc), 4),
            "precision": round(float(prec), 4),
            "recall": round(float(rec), 4),
            "f1": round(float(f1), 4),
            "auc_roc": round(float(auc), 4),
            "confusion_matrix": cm
        }

    def cross_validate(self, X: pd.DataFrame, y: Union[pd.Series, np.ndarray], cv: int = 5) -> Dict[str, Any]:
        """Perform stratified k-fold cross validation."""
        skf = StratifiedKFold(n_splits=cv, shuffle=True, random_state=self.config.RANDOM_SEED)
        y_arr = np.array(y, dtype=int)

        accuracies, precisions, recalls, f1s, aucs = [], [], [], [], []

        for train_idx, val_idx in skf.split(X, y_arr):
            X_tr, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_tr, y_val = y_arr[train_idx], y_arr[val_idx]

            fold_clf = MuleClassifier(config=self.config)
            fold_clf.train(X_tr, y_tr, model_type=self.model_type)
            res = fold_clf.evaluate(X_val, y_val)

            accuracies.append(res["accuracy"])
            precisions.append(res["precision"])
            recalls.append(res["recall"])
            f1s.append(res["f1"])
            aucs.append(res["auc_roc"])

        return {
            "cv_folds": cv,
            "accuracy_mean": round(float(np.mean(accuracies)), 4),
            "accuracy_std": round(float(np.std(accuracies)), 4),
            "precision_mean": round(float(np.mean(precisions)), 4),
            "precision_std": round(float(np.std(precisions)), 4),
            "recall_mean": round(float(np.mean(recalls)), 4),
            "recall_std": round(float(np.std(recalls)), 4),
            "f1_mean": round(float(np.mean(f1s)), 4),
            "f1_std": round(float(np.std(f1s)), 4),
            "auc_roc_mean": round(float(np.mean(aucs)), 4),
            "auc_roc_std": round(float(np.std(aucs)), 4)
        }

    def tune_hyperparameters(self, X_train: pd.DataFrame, y_train: Union[pd.Series, np.ndarray]) -> Dict[str, Any]:
        """Run grid search optimization over hyperparameter grid."""
        param_grid = {
            "n_estimators": [100, 200],
            "max_depth": [3, 5],
            "learning_rate": [0.05, 0.10]
        }
        base_model = xgb.XGBClassifier(eval_metric="logloss", random_state=self.config.RANDOM_SEED)
        grid_search = GridSearchCV(base_model, param_grid, cv=3, scoring="f1", n_jobs=-1)
        grid_search.fit(X_train, y_train)

        self.model = grid_search.best_estimator_
        self.feature_names = list(X_train.columns)
        if self.model_path:
            self.save_model(self.model_path)

        return {
            "best_params": grid_search.best_params_,
            "best_score": round(float(grid_search.best_score_), 4)
        }

    def get_feature_importance(self) -> Dict[str, float]:
        """Return feature importance map sorted descending by attribution value."""
        if self.model is None or not self.feature_names:
            return {}

        importances = getattr(self.model, "feature_importances_", None)
        if importances is None:
            return {}

        imp_dict = {feat: round(float(imp), 4) for feat, imp in zip(self.feature_names, importances)}
        sorted_imp = dict(sorted(imp_dict.items(), key=lambda item: item[1], reverse=True))
        return sorted_imp

    def save_model(self, filepath: Optional[str] = None) -> str:
        """Serialize trained model and metadata to disk using joblib."""
        target_path = filepath or self.model_path
        if not target_path:
            raise ValueError("No model path specified.")

        os.makedirs(os.path.dirname(target_path) if os.path.dirname(target_path) else ".", exist_ok=True)
        payload = {
            "model": self.model,
            "model_type": self.model_type,
            "feature_names": self.feature_names,
            "thresholds": self.threshold_manager.get_thresholds()
        }
        joblib.dump(payload, target_path)
        logger.info(f"Model saved to {target_path}")
        return target_path

    def load_model(self, filepath: Optional[str] = None) -> "MuleClassifier":
        """Load serialized model and metadata from disk."""
        target_path = filepath or self.model_path
        if not target_path or not os.path.exists(target_path):
            raise FileNotFoundError(f"Model file {target_path} does not exist.")

        payload = joblib.load(target_path)
        if isinstance(payload, dict):
            self.model = payload.get("model")
            self.model_type = payload.get("model_type", "xgboost")
            self.feature_names = payload.get("feature_names", [])
            if "thresholds" in payload:
                self.threshold_manager.thresholds.update(payload["thresholds"])
        else:
            self.model = payload
            if hasattr(payload, "feature_names_in_"):
                self.feature_names = list(payload.feature_names_in_)

        logger.info(f"Loaded {self.model_type} model with {len(self.feature_names)} features from {target_path}")
        return self

    def model_exists(self) -> bool:
        """Check if serialized model artifact is present on disk."""
        return bool(self.model_path and os.path.exists(self.model_path))
