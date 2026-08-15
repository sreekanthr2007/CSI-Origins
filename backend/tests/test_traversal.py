"""Unit tests for bounded pattern-decay traversal."""
import networkx as nx
from backend.app.investigation.traversal import BoundedTraversal


def test_traversal_empty():
    g = nx.MultiDiGraph()
    traversal = BoundedTraversal(max_hops=5)
    res = traversal.traverse_neighborhood(g, "nonexistent")
    assert res["traversal_depth"] == 0
