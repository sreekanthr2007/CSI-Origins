"""Configuration management module using Pydantic Settings with runtime key rotation."""
import os
import json
import secrets
import pathlib
from typing import List, Optional, Union
from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base directory and .env resolution
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent.parent
ENV_PATH = BASE_DIR / ".env"

# Load existing .env if present
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)


def save_to_env(key: str, value: str) -> None:
    """Persist or update an environment variable in the .env file."""
    lines = []
    found = False
    if ENV_PATH.exists():
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()

    new_lines = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            new_lines.append(f"{key}={value}\n")
            found = True
        else:
            new_lines.append(line)

    if not found:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines.append("\n")
        new_lines.append(f"{key}={value}\n")

    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    os.environ[key] = value


def _get_or_create_standing_key() -> str:
    """Fetch current HMAC_STANDING_KEY from environment or generate and persist a fresh 32-byte hex key."""
    key = os.getenv("HMAC_STANDING_KEY")
    if not key:
        key = secrets.token_bytes(32).hex()
        save_to_env("HMAC_STANDING_KEY", key)
    return key


class Settings(BaseSettings):
    """Application and Cryptographic Settings."""
    
    # Application & Database Config
    APP_NAME: str = "Cross-Bank Mule Account Detection Network"
    DATABASE_URL: str = Field(default="sqlite:///./data/mule_detection.db")
    DATABASE_ECHO: bool = Field(default=False)

    # Cryptographic Privacy Config
    HMAC_STANDING_KEY: str = Field(default_factory=_get_or_create_standing_key)
    KEY_ROTATION_DAYS: int = Field(default=30)
    KEY_ROTATION_GRACE_PERIOD_DAYS: int = Field(default=7)
    HISTORICAL_KEYS: Union[List[str], str] = Field(default_factory=list)

    # Synthetic Data Generation Config
    NUM_BANKS: int = Field(default=10)
    NUM_ACCOUNTS_PER_BANK: int = Field(default=100)
    NUM_EDGES: int = Field(default=10000)
    CONTAMINATION_RATE: float = Field(default=0.10)
    RANDOM_SEED: int = Field(default=42)

    # Graph Traversal & Feature Config
    PASS_THROUGH_WINDOW_HOURS: int = Field(default=24)
    PASS_THROUGH_THRESHOLD: float = Field(default=0.60)
    MAX_TIME_GAP_HOURS: int = Field(default=72)
    MAX_DEPTH: int = Field(default=7)
    MAX_BANKS_QUERIED: int = Field(default=15)

    # Machine Learning Config
    MODEL_TYPE: str = Field(default="xgboost")
    MODEL_PATH: str = Field(default="./models/mule_classifier.pkl")
    TEST_SIZE: float = Field(default=0.20)
    N_ESTIMATORS: int = Field(default=200)
    MAX_DEPTH_ML: int = Field(default=5)

    # API & Server Config
    API_PREFIX: str = Field(default="/api/v1")
    CORS_ORIGINS: List[str] = Field(default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"])
    LOG_LEVEL: str = Field(default="INFO")

    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @field_validator("HISTORICAL_KEYS", mode="before")
    @classmethod
    def parse_historical_keys(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [k.strip() for k in v.split(",") if k.strip()]
        return v or []

    def get_standing_key(self) -> str:
        """Return current standing HMAC key."""
        return self.HMAC_STANDING_KEY

    def generate_and_save_key(self) -> str:
        """Generate a new HMAC key and write to .env and instance."""
        new_key = secrets.token_bytes(32).hex()
        save_to_env("HMAC_STANDING_KEY", new_key)
        self.HMAC_STANDING_KEY = new_key
        return new_key

    def rotate_standing_key(self) -> str:
        """Move current key to historical list, generate new key, and update .env."""
        old_key = self.HMAC_STANDING_KEY
        if isinstance(self.HISTORICAL_KEYS, str):
            self.HISTORICAL_KEYS = [k.strip() for k in self.HISTORICAL_KEYS.split(",") if k.strip()]
        if old_key and old_key not in self.HISTORICAL_KEYS:
            self.HISTORICAL_KEYS.append(old_key)
            if len(self.HISTORICAL_KEYS) > 5:
                self.HISTORICAL_KEYS = self.HISTORICAL_KEYS[-5:]
            save_to_env("HISTORICAL_KEYS", json.dumps(self.HISTORICAL_KEYS))

        new_key = self.generate_and_save_key()
        return new_key

    def get_historical_keys(self) -> List[str]:
        """Return historical keys valid during rotation grace period."""
        if isinstance(self.HISTORICAL_KEYS, str):
            self.HISTORICAL_KEYS = [k.strip() for k in self.HISTORICAL_KEYS.split(",") if k.strip()]
        return list(self.HISTORICAL_KEYS)


settings = Settings()
