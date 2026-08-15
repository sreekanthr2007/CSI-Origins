"""Regulatory compliance, STR reporting, and action recommendation package."""
from backend.app.compliance.str_generator import (
    STRGenerator,
    STR_SCHEMA_VERSION,
    REQUIRED_FIELDS,
)
from backend.app.compliance.action_recommender import ActionRecommender

str_generator = STRGenerator()
action_recommender = ActionRecommender()

__all__ = [
    "STRGenerator",
    "ActionRecommender",
    "STR_SCHEMA_VERSION",
    "REQUIRED_FIELDS",
    "str_generator",
    "action_recommender",
]
