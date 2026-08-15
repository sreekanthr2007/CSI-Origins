"""Application configuration settings."""
import os
import secrets
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Core application settings with dynamic key generation for runtime security."""
    APP_NAME: str = "Cross-Bank Mule Account Detection Network"
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"]
    
    # Cryptographic keys - dynamically generate secure standing key if not provided via env
    HMAC_STANDING_KEY: str = os.getenv("HMAC_STANDING_KEY", secrets.token_hex(32))
    KEY_ROTATION_DAYS: int = 30
    
    # Simulation & ML hyperparameters
    MULE_CONTAMINATION_RATE: float = 0.10
    DEFAULT_SIMULATION_BANKS: int = 5
    DEFAULT_TRANSACTION_COUNT: int = 500
    TRAVERSAL_MAX_HOPS: int = 6
    TRAVERSAL_MAX_BANKS: int = 12
    PASS_THROUGH_DECAY_THRESHOLD: float = 0.70

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
