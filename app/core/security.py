"""
app/core/security.py
Security configuration: CORS, trusted hosts, request-size limiting,
password hashing (Bcrypt), and JWT authentication token handling.
"""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple, Union

import jwt
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()

# ── Password Hashing (Bcrypt) ────────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


# ── JWT Token Management ─────────────────────────────────────────────────────

def create_access_token(
    user_id: Union[uuid.UUID, str],
    role: str,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Create a signed JWT access token.
    Default expiration: settings.access_token_expire_minutes (15 minutes).
    """
    now = datetime.now(timezone.utc)
    expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def hash_refresh_token(token: str) -> str:
    """Compute SHA-256 hash of a refresh token for secure database storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_refresh_token(
    user_id: Union[uuid.UUID, str],
) -> Tuple[str, str]:
    """
    Create a signed JWT refresh token and its SHA-256 database hash.
    Default expiration: settings.refresh_token_expire_days (7 days).

    Returns:
        tuple[str, str]: (raw_token, token_hash)
    """
    now = datetime.now(timezone.utc)
    expires_delta = timedelta(days=settings.refresh_token_expire_days)
    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    raw_token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return raw_token, hash_refresh_token(raw_token)


def create_qr_token(
    analysis_id: Union[uuid.UUID, str],
) -> str:
    """
    Create a signed JWT token for temporary patient QR code access.
    Default expiration: settings.qr_token_expire_days (30 days).
    """
    now = datetime.now(timezone.utc)
    expires_delta = timedelta(days=settings.qr_token_expire_days)
    payload: Dict[str, Any] = {
        "sub": str(analysis_id),
        "type": "qr_access",
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a signed JWT token.
    Raises HTTPException 401 if invalid or expired.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (jwt.PyJWTError, Exception):
        raise credentials_exception


# ── Middleware ───────────────────────────────────────────────────────────────

def add_security_middleware(app: FastAPI) -> None:
    """
    Attach security middleware (CORS and TrustedHost).
    Updated for V2: Supports GET, POST, PUT, DELETE, PATCH, OPTIONS.
    """
    # ── 1. CORS ───────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["*"],
    )
    logger.debug(f"CORS enabled for origins: {settings.origins_list}")

    # ── 2. Trusted Hosts ──────────────────────────────────
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"],  # Tighten this in production
    )


def add_request_size_limit(app: FastAPI) -> None:
    """
    Middleware that rejects requests larger than MAX_IMAGE_SIZE_MB.
    Must be added AFTER CORSMiddleware so pre-flight requests pass.
    """

    max_admin_upload_bytes = 100 * 1024 * 1024  # 100 MB for admin resources (APK, theses)

    @app.middleware("http")
    async def limit_upload_size(request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            size = int(content_length)
            is_admin_upload = request.url.path.startswith("/api/v1/admin/platform-resources/upload-")
            allowed = max_admin_upload_bytes if is_admin_upload else settings.max_image_size_bytes
            if size > allowed:
                logger.warning(
                    f"Request rejected: payload {size} bytes exceeds limit {allowed} bytes"
                )
                return JSONResponse(
                    status_code=413,
                    content={"detail": "Request body too large."},
                )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response
