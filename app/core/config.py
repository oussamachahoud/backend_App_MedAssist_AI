"""
app/core/config.py
Application configuration using pydantic-settings.
All values are loaded from environment variables or .env file.
"""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the MedAssist AI API — V2.0."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ─────────────────────────────────────────────────────────
    app_name: str = "MedAssist AI API"
    api_version: str = "2.0.0"
    debug: bool = False

    # ── Database (PostgreSQL) ────────────────────────────────────────────────
    database_url: str = "postgresql+psycopg2://medassist:secret@localhost:5432/medassist_db"

    # ── Object Storage (MinIO) ──────────────────────────────────────────────
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "medassist"
    minio_secret_key: str = "medassist_secret"
    minio_secure: bool = False
    minio_bucket_analyses: str = "medassist-analyses"

    # ── Security & JWT ───────────────────────────────────────────────────────
    jwt_secret_key: str = "medassist_super_secret_jwt_key_v2_2026_change_in_prod"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    qr_token_expire_days: int = 30

    # ── Initial Admin Seed ──────────────────────────────────────────────────
    initial_admin_email: str = "admin@medassist.dz"
    initial_admin_password: str = "Admin@MedAssist2026!"

    # ── Model Paths ─────────────────────────────────────────────────────────
    # PyTorch checkpoint — trained with MedAssistModel V6.0 (swa_model_V6.0.pth)
    model_path: str = "app/ml_models/multimodal_model.pth"
    # Diagnostic LabelEncoder (diagnostic_encoder.pkl from preprocessing notebook)
    le_diagnostic_path: str = "app/ml_models/diagnostic_encoder.pkl"
    # Imputer medians/modes for the 7 clinical metadata features
    imputer_path: str = "app/ml_models/imputer.pkl"
    # StandardScaler for numeric features (age, diameter_1)
    scaler_path: str = "app/ml_models/scaler.pkl"
    # Per-class optimised thresholds from notebook 04b (thresholds_V6.0.json)
    thresholds_path: str = "app/ml_models/thresholds_V6.0.json"

    # ── Server ──────────────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000

    # ── CORS ────────────────────────────────────────────────────────────────
    allowed_origins: str = "http://localhost:3000,http://localhost:8080,http://localhost:5173"

    @property
    def origins_list(self) -> List[str]:
        """Return CORS origins as a Python list."""
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    # ── Upload Limits ───────────────────────────────────────────────────────
    max_image_size_mb: int = 10

    @property
    def max_image_size_bytes(self) -> int:
        return self.max_image_size_mb * 1024 * 1024

    # ── Logging ─────────────────────────────────────────────────────────────
    log_level: str = "INFO"

    # ── Model Architecture — V6.0 ───────────────────────────────────────────
    image_size: int = 256          # V6.0 uses 256×256 input images
    num_diagnostic_classes: int = 6
    # 7 clinical features: age, gender, grew, bleed, diameter_1,
    #                      skin_cancer_history, elevation
    num_tabular_features: int = 7


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (singleton)."""
    return Settings()
