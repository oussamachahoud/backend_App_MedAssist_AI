"""
app/api/v1/endpoints/auth.py
Authentication endpoints: register, login, refresh, logout, change-password, and me.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from loguru import logger
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.db_models.audit import AuditLog
from app.db_models.user import DoctorProfile, RefreshToken, User, UserRole, UserStatus
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    MessageResponse,
    RefreshTokenRequest,
    RegisterDoctorRequest,
    TokenRefreshResponse,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()


# ── 1. Register Doctor ───────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new Doctor",
    description="Register doctor profile. Accounts are set to 'pending_verification' by default.",
)
def register(
    payload: RegisterDoctorRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> UserResponse:
    """Register doctor account and doctor profile."""
    clean_email = str(payload.email).lower().strip()

    # Check duplicate email
    existing_user = db.query(User).filter(User.email == clean_email).first()
    if existing_user:
        logger.warning(f"Registration attempt with existing email: {clean_email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered",
        )

    # Check duplicate license number if provided
    if payload.license_number:
        clean_license = payload.license_number.strip()
        existing_profile = (
            db.query(DoctorProfile)
            .filter(DoctorProfile.license_number == clean_license)
            .first()
        )
        if existing_profile:
            logger.warning(f"Registration attempt with existing license number: {clean_license}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="License number is already registered",
            )
    else:
        clean_license = None

    # Create User record
    new_user = User(
        email=clean_email,
        password_hash=hash_password(payload.password),
        role=UserRole.DOCTOR,
        status=UserStatus.PENDING_VERIFICATION,
        must_change_password=False,
    )
    db.add(new_user)
    db.flush()

    # Create DoctorProfile record
    profile = DoctorProfile(
        user_id=new_user.id,
        full_name=payload.full_name.strip(),
        doctor_type=payload.doctor_type,
        specialization=payload.specialization.strip() if payload.specialization else None,
        license_number=clean_license,
        institution_name=payload.institution_name.strip() if payload.institution_name else None,
        phone=payload.phone.strip() if payload.phone else None,
        wilaya=payload.wilaya.strip() if payload.wilaya else None,
        avatar_url=payload.avatar_url.strip() if payload.avatar_url else None,
    )
    db.add(profile)

    # Audit log
    client_ip = request.client.host if request.client else None
    audit = AuditLog(
        user_id=new_user.id,
        action="DOCTOR_REGISTERED",
        resource_type="user",
        resource_id=new_user.id,
        details={
            "email": new_user.email,
            "doctor_type": payload.doctor_type.value,
            "full_name": payload.full_name,
            "wilaya": payload.wilaya,
        },
        ip_address=client_ip,
    )
    db.add(audit)
    db.commit()
    db.refresh(new_user)

    logger.info(f"✅ Doctor registered: {new_user.email} (status=pending_verification)")
    return UserResponse.model_validate(new_user)


# ── 2. Login ─────────────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login",
    description="Authenticate with email and password to obtain access and refresh tokens.",
)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Authenticate user and return JWT tokens."""
    clean_email = str(payload.email).lower().strip()
    client_ip = request.client.host if request.client else None
    user = db.query(User).filter(User.email == clean_email).first()

    if not user or not verify_password(payload.password, user.password_hash):
        audit = AuditLog(
            user_id=user.id if user else None,
            action="LOGIN_FAILED",
            resource_type="auth",
            details={"email": clean_email, "reason": "invalid_credentials"},
            ip_address=client_ip,
        )
        db.add(audit)
        db.commit()
        logger.warning(f"Failed login attempt for: {clean_email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if account is suspended
    if user.status == UserStatus.SUSPENDED:
        audit = AuditLog(
            user_id=user.id,
            action="LOGIN_SUSPENDED",
            resource_type="auth",
            details={"email": clean_email, "reason": "account_suspended"},
            ip_address=client_ip,
        )
        db.add(audit)
        db.commit()
        logger.warning(f"Login denied for suspended account: {user.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is suspended. Please contact administrator.",
        )

    # Update last login timestamp
    user.last_login = datetime.now(timezone.utc)

    # Issue tokens
    access_token = create_access_token(
        user_id=user.id,
        role=user.role.value,
    )
    raw_refresh, token_hash = create_refresh_token(user_id=user.id)

    refresh_record = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
        is_revoked=False,
    )
    db.add(refresh_record)

    # Audit log
    audit = AuditLog(
        user_id=user.id,
        action="LOGIN_SUCCESS",
        resource_type="auth",
        details={"email": user.email, "role": user.role.value},
        ip_address=client_ip,
    )
    db.add(audit)
    db.commit()
    db.refresh(user)

    logger.info(f"✅ User logged in: {user.email} (role={user.role.value})")

    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
        must_change_password=user.must_change_password,
        user=UserResponse.model_validate(user),
    )


# ── 3. Refresh Access Token ──────────────────────────────────────────────────

@router.post(
    "/refresh",
    response_model=TokenRefreshResponse,
    summary="Refresh Access Token",
    description="Exchange a valid refresh token for a new access token.",
)
def refresh(
    payload: RefreshTokenRequest,
    db: Session = Depends(get_db),
) -> TokenRefreshResponse:
    """Issue a new access token from a valid refresh token."""
    token_data = decode_token(payload.refresh_token)
    if token_data.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type for refresh",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_hash = hash_refresh_token(payload.refresh_token)
    stored_token = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == token_hash)
        .first()
    )

    if not stored_token or stored_token.is_revoked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is revoked or invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )

    now = datetime.now(timezone.utc)
    exp = stored_token.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == stored_token.user_id).first()
    if not user or user.status == UserStatus.SUSPENDED:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is not active or account is suspended",
            headers={"WWW-Authenticate": "Bearer"},
        )

    new_access_token = create_access_token(
        user_id=user.id,
        role=user.role.value,
    )

    return TokenRefreshResponse(
        access_token=new_access_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
    )


# ── 4. Logout ────────────────────────────────────────────────────────────────

@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Logout",
    description="Revoke the provided refresh token session.",
)
def logout(
    payload: RefreshTokenRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Revoke refresh token and terminate session."""
    token_hash = hash_refresh_token(payload.refresh_token)
    stored_token = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == token_hash)
        .first()
    )

    if stored_token:
        stored_token.is_revoked = True
        client_ip = request.client.host if request.client else None
        audit = AuditLog(
            user_id=stored_token.user_id,
            action="LOGOUT",
            resource_type="auth",
            details={"refresh_token_id": str(stored_token.id)},
            ip_address=client_ip,
        )
        db.add(audit)
        db.commit()

    return MessageResponse(message="Successfully logged out")


# ── 5. Change Password ───────────────────────────────────────────────────────

@router.put(
    "/change-password",
    response_model=MessageResponse,
    summary="Change Password",
    description="Change password for the currently authenticated user.",
)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Change current user's password and revoke active refresh tokens."""
    if current_user.status == UserStatus.SUSPENDED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is suspended. Please contact administrator.",
        )

    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    if verify_password(payload.new_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password cannot be the same as current password",
        )

    current_user.password_hash = hash_password(payload.new_password)
    current_user.must_change_password = False

    # Revoke all existing refresh tokens for security
    db.query(RefreshToken).filter(
        RefreshToken.user_id == current_user.id
    ).update({RefreshToken.is_revoked: True})

    client_ip = request.client.host if request.client else None
    audit = AuditLog(
        user_id=current_user.id,
        action="PASSWORD_CHANGED",
        resource_type="user",
        resource_id=current_user.id,
        details={"email": current_user.email},
        ip_address=client_ip,
    )
    db.add(audit)
    db.commit()

    logger.info(f"✅ Password changed for user {current_user.email}")
    return MessageResponse(message="Password changed successfully")


# ── 6. Get Current User ──────────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get Current User Profile",
    description="Return profile details and status of the authenticated user.",
)
def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Return current authenticated user profile."""
    return UserResponse.model_validate(current_user)
