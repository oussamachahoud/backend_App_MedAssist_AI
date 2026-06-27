"""
app/core/security.py
Security configuration: CORS, trusted hosts, request-size limiting.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from app.core.config import get_settings

settings = get_settings()


def add_security_middleware(app: FastAPI) -> None:
    """
    Attach all security-related middleware to the FastAPI application.

    Order matters: middleware is applied in reverse registration order.
    """

    # ── 1. CORS ───────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    logger.debug(f"CORS enabled for origins: {settings.origins_list}")

    # ── 2. Trusted Hosts ──────────────────────────────────
    # Prevents HTTP Host-header injection attacks
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"],  # Tighten this in production (e.g. ["api.yourdomain.com"])
    )


def add_request_size_limit(app: FastAPI) -> None:
    """
    Middleware that rejects requests larger than MAX_IMAGE_SIZE_MB.
    Must be added AFTER CORSMiddleware so pre-flight requests pass.
    """

    @app.middleware("http")
    async def limit_upload_size(request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            size = int(content_length)
            if size > settings.max_image_size_bytes:
                logger.warning(
                    f"Request rejected: payload {size} bytes exceeds "
                    f"limit {settings.max_image_size_bytes} bytes"
                )
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": (
                            f"Request body too large. "
                            f"Maximum allowed size is {settings.max_image_size_mb} MB."
                        )
                    },
                )
        return await call_next(request)
