"""Dataset building, feature matrix preparation, and train/test splitting for ML detection."""
import os
import logging
from typing import Dict, Any, List, Tuple, Optional, Union
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split

from backend.app.config import settings, Settings
from backend.app.privacy.hashing import generate_standing_hash
from backend.app.data_generator.motif_injector import generate_with_contamination
from backend.app.graph.graph_engine import TemporalGraph
from backend.app.features.feature_extractor import FeatureExtractor

logger = logging.getLogger("mule-detection-ml-dataset")


class DatasetBuilder:
    """Constructs training and evaluation datasets by synthesizing cross-bank topologies and extracting features."""

    def __init__(self, config: Optional[Settings] = None):
        self.config = config or settings
        self.target_column = "is_mule"

    def build_dataset(
        self,
        num_banks: Optional[int] = None,
        num_accounts_per_bank: Optional[int] = None,
        num_edges: Optional[int] = None,
        contamination_rate: Optional[float] = None,
        seed: Optional[int] = None
    ) -> pd.DataFrame:
        """Generate synthetic multi-bank transaction data with ground truth motifs and extract feature vectors."""
        n_banks = num_banks or self.config.NUM_BANKS
        n_accs = num_accounts_per_bank or self.config.NUM_ACCOUNTS_PER_BANK
        n_edges = num_edges or self.config.NUM_EDGES
        c_rate = contamination_rate or self.config.CONTAMINATION_RATE
        r_seed = seed or self.config.RANDOM_SEED

        logger.info(f"Synthesizing dataset: {n_banks} banks, {n_accs} accs/bank, {n_edges} edges, {c_rate*100}% contamination")

        # 1. Generate synthetic dataset with ground-truth mule motifs (Phase 3)
        dataset = generate_with_contamination(
            num_banks=n_banks,
            num_accounts_per_bank=n_accs,
            num_edges=n_edges,
            contamination_rate=c_rate,
            seed=r_seed
        )

        standing_key = self.config.get_standing_key()
        raw_mule_nodes = set(dataset["ground_truth"]["mule_nodes"])

        # Map raw account numbers to Flow A HMAC standing hashes
        hash_map: Dict[str, str] = {}
        for acc in dataset["accounts"]:
            acc_num = acc["account_number"]
            ifsc = acc["ifsc_code"]
            h = generate_standing_hash(acc_num, ifsc, standing_key)
            hash_map[acc_num] = h

        hashed_mule_nodes = {hash_map[acc] for acc in raw_mule_nodes if acc in hash_map}

        # 2. Convert edges to hashed representations and ingest into TemporalGraph (Phase 4)
        hashed_edges: List[Dict[str, Any]] = []
        for e in dataset["edges"]:
            s_acc = e.get("sender_account")
            r_acc = e.get("receiver_account")
            s_hash = hash_map.get(s_acc, s_acc)
            r_hash = hash_map.get(r_acc, r_acc)

            hashed_edges.append({
                "sender_hash": s_hash,
                "receiver_hash": r_hash,
                "amount": float(e.get("amount", 0.0)),
                "timestamp": e.get("timestamp"),
                "bank_id": e.get("sender_bank_id") or e.get("bank_id", "UNKNOWN"),
                "local_risk_score": float(e.get("local_risk_score", 0.0) or 0.0),
                "is_interbank": bool(e.get("is_interbank", True))
            })

        tg = TemporalGraph(config=self.config)
        tg.add_edges_batch(hashed_edges)

        # 3. Extract feature matrix for all nodes
        extractor = FeatureExtractor(graph=tg, config=self.config)
        all_nodes = tg.get_nodes()
        df = extractor.extract_features_batch(all_nodes)

        # 4. Attach ground truth is_mule labels
        df.reset_index(inplace=True)
        if "index" in df.columns:
            df.rename(columns={"index": "node_hash"}, inplace=True)

        df[self.target_column] = df["node_hash"].apply(lambda h: 1 if h in hashed_mule_nodes else 0)

        logger.info(f"Dataset constructed: {len(df)} samples, {df[self.target_column].sum()} mules ({df[self.target_column].mean()*100:.1f}%)")
        return df

    def get_feature_columns(self, df: Optional[pd.DataFrame] = None) -> List[str]:
        """Return list of numeric feature column names."""
        if df is not None:
            cols = [c for c in df.columns if c not in ["node_hash", "bank_id", self.target_column]]
            return cols
        dummy_extractor = FeatureExtractor(graph=TemporalGraph(config=self.config))
        return dummy_extractor.get_feature_names()

    def get_target_column(self) -> str:
        """Return target label column name."""
        return self.target_column

    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract and clean numeric feature matrix from dataset DataFrame."""
        feat_cols = self.get_feature_columns(df)
        X = df[feat_cols].copy()
        X = X.select_dtypes(include=[np.number])
        X.fillna(0.0, inplace=True)
        return X

    def split_dataset(
        self,
        df: pd.DataFrame,
        test_size: Optional[float] = None,
        random_seed: Optional[int] = None
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
        """Stratified train/test split preserving target class ratio."""
        t_size = test_size if test_size is not None else self.config.TEST_SIZE
        r_seed = random_seed if random_seed is not None else self.config.RANDOM_SEED

        X = self.prepare_features(df)
        y = df[self.target_column].astype(int)

        # Check if both classes are present for stratification
        stratify = y if len(np.unique(y)) > 1 else None

        X_train, X_test, y_train, y_test = train_test_split(
            X, y,
            test_size=t_size,
            random_state=r_seed,
            stratify=stratify
        )

        return X_train, X_test, y_train, y_test

    def prepare_splits(
        self,
        df: pd.DataFrame,
        test_size: Optional[float] = None,
        random_seed: Optional[int] = None
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
        """Alias for split_dataset."""
        return self.split_dataset(df, test_size=test_size, random_seed=random_seed)


    def compute_class_weights(self, y_train: Union[pd.Series, np.ndarray]) -> float:
        """Calculate scale_pos_weight (ratio of negative to positive samples) for XGBoost."""
        pos_count = np.sum(y_train == 1)
        neg_count = np.sum(y_train == 0)
        if pos_count == 0:
            return 1.0
        return float(neg_count / pos_count)

    def balance_dataset(self, X: pd.DataFrame, y: pd.Series, method: str = "weights") -> Tuple[pd.DataFrame, pd.Series]:
        """Class balancing helper (supports class weighting or SMOTE oversampling)."""
        if method == "smote":
            try:
                import importlib
                imblearn_module = importlib.import_module("imblearn.over_sampling")
                smote_cls = getattr(imblearn_module, "SMOTE")
                sm = smote_cls(random_state=self.config.RANDOM_SEED)
                X_res, y_res = sm.fit_resample(X, y)
                return pd.DataFrame(X_res, columns=X.columns), pd.Series(y_res)
            except (ImportError, AttributeError):
                logger.info("imblearn not available, falling back to class weighting.")
        return X, y

    def save_dataset(self, df: pd.DataFrame, filepath: str) -> None:
        """Persist DataFrame to CSV or Parquet."""
        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)
        if filepath.endswith(".parquet"):
            df.to_parquet(filepath, index=False)
        else:
            df.to_csv(filepath, index=False)

    def load_dataset(self, filepath: str) -> pd.DataFrame:
        """Load dataset from disk."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Dataset file {filepath} not found.")
        if filepath.endswith(".parquet"):
            return pd.read_parquet(filepath)
        return pd.read_csv(filepath)
