"""
app/schemas package initialization.
"""

from app.schemas.auth import (
    ChangePasswordRequest,
    DoctorProfileResponse,
    LoginRequest,
    MessageResponse,
    RefreshTokenRequest,
    RegisterDoctorRequest,
    TokenRefreshResponse,
    TokenResponse,
    UserResponse,
)
from app.schemas.prediction import ClassProbability, PredictResponse

__all__ = [
    "RegisterDoctorRequest",
    "LoginRequest",
    "TokenResponse",
    "TokenRefreshResponse",
    "RefreshTokenRequest",
    "ChangePasswordRequest",
    "DoctorProfileResponse",
    "UserResponse",
    "MessageResponse",
    "PredictResponse",
    "ClassProbability",
]
