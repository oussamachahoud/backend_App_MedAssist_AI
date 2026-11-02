"""
app/api/deps.py
Authentication, authorization, and database dependencies for MedAssist AI V2.
"""

import uuid
from typing import Generator, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from loguru import logger
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.db_models.user import DoctorType, User, UserRole, UserStatus
from app.services.model_service import ModelService
from app.services.model_service import model_service as _model_service

# OAuth2 scheme pointing to login endpoint
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=True,
)

oauth2_scheme_optional = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=False,
)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Validate access token and return the authenticated User from the database.
    Raises 401 if token is invalid, expired, not an access token, or user is not found.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_token(token)

    token_type = payload.get("type")
    if token_type != "access":
        logger.warning(f"Invalid token type provided for authentication: {token_type}")
        raise credentials_exception

    user_id_str: str = payload.get("sub")
    if not user_id_str:
        logger.warning("Token missing 'sub' subject claim")
        raise credentials_exception

    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        logger.warning(f"Invalid UUID in token subject: {user_id_str}")
        raise credentials_exception

    user = db.query(User).filter(User.id == user_uuid).first()
    if user is None:
        logger.warning(f"User not found for token subject: {user_id_str}")
        raise credentials_exception

    if user.status == UserStatus.SUSPENDED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is suspended. Please contact administrator.",
        )

    return user


def get_current_active_doctor(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Ensure the current authenticated user has the DOCTOR role (or active Admin)
    and has completed any mandatory password change.
    """
    if current_user.role != UserRole.DOCTOR:
        logger.warning(f"Forbidden access: User {current_user.id} has role {current_user.role}, required {UserRole.DOCTOR}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Doctor access required",
        )

    if current_user.status == UserStatus.SUSPENDED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is suspended. Please contact administrator.",
        )

    if current_user.status == UserStatus.PENDING_VERIFICATION:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is pending verification by administrator.",
        )

    if current_user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not active.",
        )

    if current_user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password change required before accessing clinical endpoints.",
        )

    return current_user


def get_optional_active_doctor(
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    If a Bearer token is provided:
      Validates it and ensures the user is an active doctor (raises 401/403 if invalid).
    If no Bearer token is provided:
      Returns None (allowing guest access / backward compatibility with legacy tests).
    """
    if not token:
        return None

    user = get_current_user(token=token, db=db)
    return get_current_active_doctor(current_user=user)


def get_current_specialist(
    doctor: User = Depends(get_current_active_doctor),
) -> User:
    """
    Ensure the active doctor is a certified Specialist Dermatologist.
    Raises 403 if the profile is missing or doctor_type is not specialist_dermatologist.
    """
    if not doctor.profile or doctor.profile.doctor_type != DoctorType.SPECIALIST_DERMATOLOGIST:
        logger.warning(
            f"Specialist access denied for doctor {doctor.id} "
            f"(type={doctor.profile.doctor_type if doctor.profile else 'No Profile'})"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Specialist dermatologist access required",
        )

    return doctor


def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Ensure the authenticated user is an active system administrator.
    Raises 403 if not admin or suspended.
    """
    if current_user.role != UserRole.ADMIN:
        logger.warning(f"Admin access denied for user {current_user.id} with role {current_user.role}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required",
        )

    if current_user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator account is not active",
        )

    return current_user


def get_model_service() -> ModelService:
    """Dependency that returns the global ModelService singleton."""
    if not _model_service.is_loaded:
        logger.warning("Prediction requested but model is not loaded. Proceeding with MOCK mode.")
    return _model_service
