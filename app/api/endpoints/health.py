"""
app/api/endpoints/health.py
Health check endpoint — used by load balancers, Docker, and monitoring tools.

GET /api/v1/health
"""

import time
from datetime import datetime, timezone

from fastapi import APIRouter
from loguru import logger

from app.core.config import get_settings
from app.models.response import HealthResponse
from app.services.model_service import model_service

router = APIRouter(tags=["Health"])
settings = get_settings()

# Track API start time for uptime calculation
_START_TIME: float = time.time()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description=(
        "Returns the current health status of the API and whether "
        "the ML model is loaded and ready to serve predictions."
    ),
)
async def health_check() -> HealthResponse:
    """
    Lightweight health check endpoint.
    Returns HTTP 200 when the API is running (even if the model isn't loaded).
    Callers should check `model_loaded` to confirm readiness.
    """
    uptime = time.time() - _START_TIME
    status = "ok" if model_service.is_loaded else "degraded"

    logger.debug(f"Health check | status={status} | uptime={uptime:.1f}s")

    return HealthResponse(
        status=status,
        model_loaded=model_service.is_loaded,
        uptime_seconds=round(uptime, 2),
        timestamp=datetime.now(timezone.utc),
        version=settings.api_version,
    )
