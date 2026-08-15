"""Unit tests for feature extraction."""
import networkx as nx
from backend.app.features.feature_extractor import FeatureExtractor


def test_feature_extractor_node():
    g = nx.MultiDiGraph()
    g.add_edge("nodeA", "nodeB", amount=1000)
    extractor = FeatureExtractor(g)
    feat_a = extractor.extract_node_features("nodeA")
    feat_b = extractor.extract_node_features("nodeB")
    assert feat_a["out_degree"] == 1
    assert feat_b["in_degree"] == 1
