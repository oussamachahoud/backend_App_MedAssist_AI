"""
app/main.py
FastAPI application entry point.

Responsibilities:
    - Create the FastAPI app with metadata and lifespan
    - Load the ML model at startup via lifespan context manager
    - Register all API routers under /api/v1
    - Add middleware: CORS, request-size limit, request timing
    - Global exception handlers for clean error responses
"""

import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.security import add_request_size_limit, add_security_middleware
from app.api.endpoints import health, model_info, predict
from app.services.model_service import model_service

settings = get_settings()


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Runs on application startup and shutdown.
    Startup  → load model, setup logging
    Shutdown → any cleanup needed
    """
    # ── Startup ───────────────────────────────────────────
    setup_logging(settings.log_level)
    logger.info(f"🚀 Starting {settings.app_name} v{settings.api_version}")
    logger.info(f"   Debug mode : {settings.debug}")
    logger.info(f"   CORS origins: {settings.origins_list}")

    try:
        model_service.load()
    except Exception as exc:
        logger.error(
            f"⚠️  Model failed to load: {exc}. "
            "API will start in degraded mode (predictions unavailable)."
        )

    logger.info(
        f"✅ API ready | model_loaded={model_service.is_loaded} | "
        f"device={model_service.device}"
    )

    yield  # ← application runs here

    # ── Shutdown ──────────────────────────────────────────
    logger.info("🛑 Shutting down API...")


# ── App factory ───────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.api_version,
        description=(
            "### Skin Lesion AI API\n\n"
            "Multimodal deep learning API for skin lesion diagnosis.\n\n"
            "Supported diagnostic classes:\n"
            "- **NEV** — Nevus\n"
            "- **SEK** — Seborrheic Keratosis\n"
            "- **ACK** — Actinic Keratosis\n"
            "- **BCC** — Basal Cell Carcinoma\n"
            "- **SCC** — Squamous Cell Carcinoma\n"
            "- **MEL** — Melanoma\n"
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
        debug=settings.debug,
    )

    # ── Middleware ────────────────────────────────────────
    add_security_middleware(app)
    add_request_size_limit(app)
    _add_request_id_middleware(app)
    _add_timing_middleware(app)

    # ── Routers ───────────────────────────────────────────
    PREFIX = "/api/v1"
    app.include_router(health.router,     prefix=PREFIX)
    app.include_router(model_info.router, prefix=PREFIX)
    app.include_router(predict.router,    prefix=PREFIX)

    # ── Exception handlers ────────────────────────────────
    _add_exception_handlers(app)

    return app


# ── Middleware helpers ─────────────────────────────────────────────────────────

def _add_request_id_middleware(app: FastAPI) -> None:
    """Attach a unique X-Request-ID header to every response."""

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


def _add_timing_middleware(app: FastAPI) -> None:
    """Attach X-Process-Time header (milliseconds) to every response."""

    @app.middleware("http")
    async def timing_middleware(request: Request, call_next):
        t0 = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"
        return response


# ── Exception handlers ────────────────────────────────────────────────────────

def _add_exception_handlers(app: FastAPI) -> None:

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception(
            f"Unhandled exception on {request.method} {request.url}: {exc}"
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "An unexpected internal error occurred. Please try again later."
            },
        )

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc):
        return JSONResponse(
            status_code=404,
            content={"detail": f"Endpoint '{request.url.path}' not found."},
        )


# ── App instance ──────────────────────────────────────────────────────────────

app = create_app()


# ── Root redirect ─────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def root():
    return {
        "message": f"Welcome to {settings.app_name} v{settings.api_version}",
        "docs": "/docs",
        "health": "/api/v1/health",
        "model_info": "/api/v1/model/info",
    }
