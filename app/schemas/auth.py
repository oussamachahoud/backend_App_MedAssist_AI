"""
app/schemas/auth.py
Pydantic schemas for authentication, registration, user profiles, and tokens.
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.db_models.user import DoctorType, UserRole, UserStatus


# ── Doctor Profile Schemas ───────────────────────────────────────────────────

class DoctorProfileBase(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255)
    doctor_type: DoctorType = DoctorType.GENERAL_PRACTITIONER
    specialization: Optional[str] = Field(None, max_length=255)
    license_number: Optional[str] = Field(None, max_length=100)
    institution_name: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    wilaya: Optional[str] = Field(None, max_length=10)
    avatar_url: Optional[str] = Field(None, max_length=500)


class DoctorProfileResponse(DoctorProfileBase):
    id: uuid.UUID
    user_id: uuid.UUID
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ── User Schemas ─────────────────────────────────────────────────────────────

class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    role: UserRole
    status: UserStatus
    must_change_password: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    profile: Optional[DoctorProfileResponse] = None

    model_config = ConfigDict(from_attributes=True)


# ── Registration & Login Requests ────────────────────────────────────────────

class RegisterDoctorRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    full_name: str = Field(..., min_length=2, max_length=255)
    doctor_type: DoctorType = DoctorType.GENERAL_PRACTITIONER
    specialization: Optional[str] = Field(None, max_length=255)
    license_number: Optional[str] = Field(None, max_length=100)
    institution_name: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    wilaya: Optional[str] = Field(None, max_length=10)
    avatar_url: Optional[str] = Field(None, max_length=500)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


# ── Token Schemas ────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    must_change_password: bool = False
    user: Optional[UserResponse] = None


class TokenRefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, description="New password must be at least 8 characters")


class MessageResponse(BaseModel):
    message: str

