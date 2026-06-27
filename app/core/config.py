"""
app/core/config.py
Application configuration using pydantic-settings.
All values are loaded from environment variables or .env file.
"""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the Skin Lesion AI API."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────
    app_name: str = "Skin Lesion AI API"
    api_version: str = "1.0.0"
    debug: bool = False

    # ── Model Paths ───────────────────────────────────────
    model_path: str = "app/ml_models/multimodal_model.pth"
    le_diagnostic_path: str = "app/ml_models/le_diagnostic.pkl"
    le_region_path: str = "app/ml_models/le_region.pkl"

    # ── Server ─────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000

    # ── CORS ───────────────────────────────────────────────
    allowed_origins: str = "http://localhost:3000,http://localhost:8080"

    @property
    def origins_list(self) -> List[str]:
        """Return CORS origins as a Python list."""
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    # ── Upload Limits ──────────────────────────────────────
    max_image_size_mb: int = 10

    @property
    def max_image_size_bytes(self) -> int:
        return self.max_image_size_mb * 1024 * 1024

    # ── Logging ────────────────────────────────────────────
    log_level: str = "INFO"

    # ── Model Architecture ─────────────────────────────────
    image_size: int = 224          # Expected input image size (square)
    num_diagnostic_classes: int = 6
    num_tabular_features: int = 3  # age, sex_encoded, region_encoded


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (singleton)."""
    return Settings()
