"""
app/api/dependencies.py
FastAPI dependency injection providers.
Shared dependencies injected into endpoint functions.
"""

from fastapi import HTTPException
from loguru import logger

from app.services.model_service import model_service as _model_service
from app.services.model_service import ModelService


def get_model_service() -> ModelService:
    """
    Dependency that returns the global ModelService singleton.
    In development, if the model isn't loaded, it will generate a mock response later.
    """
    if not _model_service.is_loaded:
        logger.warning("Prediction requested but model is not loaded. Proceeding with MOCK mode.")
    return _model_service
