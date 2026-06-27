"""
app/api/endpoints/model_info.py
Returns metadata about the loaded ML model.

GET /api/v1/model/info
"""

from fastapi import APIRouter
from loguru import logger

from app.core.config import get_settings
from app.models.response import ModelInfoResponse
from app.models.schemas import LABEL_FULL_NAME
from app.services.model_service import model_service

router = APIRouter(tags=["Model"])
settings = get_settings()


@router.get(
    "/model/info",
    response_model=ModelInfoResponse,
    summary="Model Information",
    description=(
        "Returns metadata about the loaded multimodal skin lesion classification model, "
        "including input specification, supported classes, and architecture summary."
    ),
)
async def get_model_info() -> ModelInfoResponse:
    """
    Returns model architecture details and supported diagnostic classes.
    Does NOT require the model to be loaded — returns is_loaded=False if missing.
    """
    logger.debug("Model info requested.")

    # Build class mapping from loaded label encoder (or fallback to enum)
    diagnostic_classes = {
        label: LABEL_FULL_NAME.get(label, label)
        for label in model_service.diagnostic_classes
    }

    return ModelInfoResponse(
        model_name="Multimodal Skin Lesion Classifier",
        architecture="CNN ImageEncoder + Tabular MLP → Fusion Head",
        input_image_size=settings.image_size,
        input_channels=3,
        tabular_features=["age (normalised)", "sex (encoded)", "localization (encoded)"],
        diagnostic_classes=diagnostic_classes,
        version=settings.api_version,
        is_loaded=model_service.is_loaded,
    )
