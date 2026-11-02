"""
app/api/v1/endpoints/admin.py
System administration and governance endpoints:
- List and filter users
- Get user details
- Doctor verification / approval workflow
- Account suspension and activation
- Admin password reset with temporary credentials
- System-wide clinical and operational statistics
"""

import os
import secrets
import string
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, status, UploadFile
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.core.logging import logger
from app.core.security import hash_password
from app.db_models.analysis import AnalysisRecord
from app.db_models.audit import AuditLog
from app.db_models.patient import Patient
from app.db_models.referral import Referral
from app.db_models.user import DoctorProfile, RefreshToken, User, UserRole, UserStatus
from app.schemas.auth import UserResponse
from app.schemas.telemedicine import (
    AdminAnalyticsResponse,
    AdminResetPasswordResponse,
    AdminStatsResponse,
    AdminUserListResponse,
    AdminUserStatusUpdateRequest,
    AuditLogListResponse,
    AuditLogResponse,
    PlatformResourcesResponse,
    PlatformResourcesUpdateRequest,
)
from app.services.platform_resources import (
    get_platform_resources,
    update_platform_resources,
)

router = APIRouter(prefix="/admin", tags=["Administration"])

PROJECT_ROOT = Path(__file__).resolve().parents[4]


def _generate_temp_password(length: int = 12) -> str:
    """Generate a high-entropy temporary password complying with security policy."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    # Ensure at least one uppercase, lowercase, digit, and special char
    pwd = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%^&*"),
    ]
    pwd += [secrets.choice(alphabet) for _ in range(length - 4)]
    secrets.SystemRandom().shuffle(pwd)
    return "".join(pwd)


@router.get("/users", response_model=AdminUserListResponse)
def list_users(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    role: Optional[UserRole] = Query(None, description="Filter by user role"),
    user_status: Optional[UserStatus] = Query(None, alias="status", description="Filter by status"),
    search: Optional[str] = Query(None, description="Search by email"),
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminUserListResponse:
    """
    List all platform users with pagination and role/status filters.
    """
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    if user_status:
        query = query.filter(User.status == user_status)
    if search:
        query = query.filter(User.email.ilike(f"%{search.strip()}%"))

    total = query.count()
    offset = (page - 1) * page_size
    records = query.order_by(desc(User.created_at)).offset(offset).limit(page_size).all()

    items = [UserResponse.model_validate(u) for u in records]
    return AdminUserListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(
    user_id: uuid.UUID,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserResponse:
    """
    Retrieve full details for any user account.
    """
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return UserResponse.model_validate(target_user)


@router.put("/users/{user_id}/verify", response_model=UserResponse)
def verify_doctor_account(
    user_id: uuid.UUID,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserResponse:
    """
    Approve and activate a doctor account pending verification.
    """
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    target_user.status = UserStatus.ACTIVE
    doctor_name = target_user.profile.full_name if target_user.profile else target_user.email
    db.add(
        AuditLog(
            user_id=admin_user.id,
            action="DOCTOR_VERIFY",
            resource_type="USER",
            resource_id=target_user.id,
            details={
                "doctor_email": target_user.email,
                "doctor_name": doctor_name,
            },
        )
    )
    db.commit()
    db.refresh(target_user)
    logger.info(f"Admin {admin_user.email} verified and activated doctor {target_user.email} (id: {target_user.id})")
    return UserResponse.model_validate(target_user)


@router.put("/users/{user_id}/status", response_model=UserResponse)
def update_user_status(
    user_id: uuid.UUID,
    status_in: AdminUserStatusUpdateRequest,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserResponse:
    """
    Update user account status (e.g. suspend or re-activate).
    """
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if target_user.id == admin_user.id and status_in.status == UserStatus.SUSPENDED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin cannot suspend their own account",
        )

    target_user.status = status_in.status
    # If suspending, invalidate active sessions
    if status_in.status == UserStatus.SUSPENDED:
        db.query(RefreshToken).filter(RefreshToken.user_id == target_user.id).delete()

    db.add(
        AuditLog(
            user_id=admin_user.id,
            action=f"USER_STATUS_{status_in.status.value.upper()}",
            resource_type="USER",
            resource_id=target_user.id,
            details={"target_email": target_user.email, "new_status": status_in.status.value},
        )
    )

    db.commit()
    db.refresh(target_user)
    logger.info(f"Admin {admin_user.email} changed user {target_user.email} status to {status_in.status.value}")
    return UserResponse.model_validate(target_user)


@router.post("/users/{user_id}/reset-pwd", response_model=AdminResetPasswordResponse)
def reset_user_password(
    user_id: uuid.UUID,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminResetPasswordResponse:
    """
    Reset user password and issue a temporary credentials token.
    Forces must_change_password on next login and invalidates existing refresh tokens.
    """
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    temp_password = _generate_temp_password()
    target_user.password_hash = hash_password(temp_password)
    target_user.must_change_password = True

    # Revoke all existing sessions
    db.query(RefreshToken).filter(RefreshToken.user_id == target_user.id).delete()

    db.add(
        AuditLog(
            user_id=admin_user.id,
            action="PASSWORD_RESET",
            resource_type="USER",
            resource_id=target_user.id,
            details={"target_email": target_user.email},
        )
    )

    db.commit()
    logger.info(f"Admin {admin_user.email} reset password for user {target_user.email}")
    return AdminResetPasswordResponse(
        temporary_password=temp_password,
        message=f"Password for user {target_user.email} successfully reset. Account flagged to require password change upon next login.",
    )


@router.get("/stats", response_model=AdminStatsResponse)
def get_system_stats(
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminStatsResponse:
    """
    System-wide platform analytics and operational metrics.
    """
    total_users = db.query(User).count()
    active_doctors = (
        db.query(User)
        .filter(User.role == UserRole.DOCTOR, User.status == UserStatus.ACTIVE)
        .count()
    )
    pending_verifications = (
        db.query(User)
        .filter(User.status == UserStatus.PENDING_VERIFICATION)
        .count()
    )
    suspended_users = (
        db.query(User)
        .filter(User.status == UserStatus.SUSPENDED)
        .count()
    )
    total_analyses = db.query(AnalysisRecord).count()
    total_patients = db.query(Patient).filter(Patient.deleted_at.is_(None)).count()
    total_referrals = db.query(Referral).count()

    return AdminStatsResponse(
        total_users=total_users,
        active_doctors=active_doctors,
        pending_verifications=pending_verifications,
        suspended_users=suspended_users,
        total_analyses=total_analyses,
        total_patients=total_patients,
        total_referrals=total_referrals,
    )


@router.get("/analytics", response_model=AdminAnalyticsResponse)
def get_system_analytics(
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminAnalyticsResponse:
    """
    Advanced system analytics: Wilaya distribution, AI diagnostic distribution,
    risk levels, clinician concordance rate, and average latency.
    """
    from sqlalchemy import func

    # Geographical distribution (by Wilaya)
    wilaya_rows = (
        db.query(DoctorProfile.wilaya, func.count(DoctorProfile.id))
        .filter(DoctorProfile.wilaya.isnot(None))
        .group_by(DoctorProfile.wilaya)
        .all()
    )
    geographical_distribution = {row[0]: row[1] for row in wilaya_rows}

    # Diagnostic class distribution
    class_rows = (
        db.query(AnalysisRecord.predicted_class, func.count(AnalysisRecord.id))
        .group_by(AnalysisRecord.predicted_class)
        .all()
    )
    diagnostic_class_distribution = {row[0]: row[1] for row in class_rows}

    # Risk level distribution
    risk_rows = (
        db.query(AnalysisRecord.risk_level, func.count(AnalysisRecord.id))
        .group_by(AnalysisRecord.risk_level)
        .all()
    )
    risk_distribution = {row[0]: row[1] for row in risk_rows}

    # Model concordance rate (where doctor confirmed AI prediction)
    reviewed_count = (
        db.query(AnalysisRecord)
        .filter(AnalysisRecord.doctor_confirmed.isnot(None))
        .count()
    )
    confirmed_count = (
        db.query(AnalysisRecord)
        .filter(AnalysisRecord.doctor_confirmed == True)
        .count()
    )
    concordance_rate = (confirmed_count / reviewed_count * 100.0) if reviewed_count > 0 else 0.0

    # Average inference time ms
    avg_latency = db.query(func.avg(AnalysisRecord.inference_time_ms)).scalar() or 0.0

    return AdminAnalyticsResponse(
        geographical_distribution=geographical_distribution,
        diagnostic_class_distribution=diagnostic_class_distribution,
        risk_distribution=risk_distribution,
        model_concordance_rate_percentage=round(concordance_rate, 2),
        average_inference_time_ms=round(float(avg_latency), 2),
    )


@router.get("/audit-logs", response_model=AuditLogListResponse)
def get_audit_logs(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    action: Optional[str] = Query(None, description="Filter by action name"),
    user_id: Optional[uuid.UUID] = Query(None, description="Filter by acting user ID"),
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AuditLogListResponse:
    """
    Retrieve paginated audit logs for compliance, security, and administrative oversight.
    """
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action.ilike(f"%{action.strip()}%"))
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)

    total = query.count()
    offset = (page - 1) * page_size
    records = query.order_by(desc(AuditLog.created_at)).offset(offset).limit(page_size).all()

    items = [AuditLogResponse.model_validate(log) for log in records]
    return AuditLogListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/platform-resources", response_model=PlatformResourcesResponse)
def get_admin_platform_resources(
    current_admin: User = Depends(require_admin),
) -> PlatformResourcesResponse:
    """
    Retrieve platform resources configuration for administrative editing.
    """
    data = get_platform_resources()
    return PlatformResourcesResponse(**data)


@router.put("/platform-resources", response_model=PlatformResourcesResponse)
def update_admin_platform_resources(
    payload: PlatformResourcesUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> PlatformResourcesResponse:
    """
    Update platform resources (video walkthrough link, mobile APK link, thesis documents).
    Audited in system audit logs.
    """
    updated = update_platform_resources(
        payload.model_dump(exclude_unset=True),
        updated_by=current_admin.email,
    )

    client_ip = request.client.host if request.client else None
    audit = AuditLog(
        user_id=current_admin.id,
        action="PLATFORM_RESOURCES_UPDATED",
        resource_type="system_settings",
        resource_id=None,
        details={
            "updated_by": current_admin.email,
            "video_url": updated.get("video_walkthrough_url"),
            "apk_url": updated.get("mobile_apk_url"),
        },
        ip_address=client_ip,
    )
    db.add(audit)
    db.commit()

    logger.info(f"Platform resources updated by admin: {current_admin.email}")
    return PlatformResourcesResponse(**updated)


@router.post("/platform-resources/upload-apk", response_model=PlatformResourcesResponse)
async def upload_admin_apk(
    file: UploadFile = File(...),
    request: Request = None,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> PlatformResourcesResponse:
    """
    Upload and deploy a new mobile APK version (Admin only).
    Replaces the canonical APK file in dashboard/assets/downloads/MedAssist-AI.apk,
    updates metadata, and records an audit trail entry.
    """
    if not file.filename or not file.filename.lower().endswith(".apk"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Please upload an Android application package (.apk).",
        )

    downloads_dir = str(PROJECT_ROOT / "dashboard" / "assets" / "downloads")
    os.makedirs(downloads_dir, exist_ok=True)
    target_path = os.path.join(downloads_dir, "MedAssist-AI.apk")

    contents = await file.read()
    size_bytes = len(contents)
    if size_bytes == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded APK file is empty.",
        )

    with open(target_path, "wb") as f:
        f.write(contents)

    size_mb = f"{size_bytes / (1024 * 1024):.2f} MB"
    now_iso = datetime.now(timezone.utc).isoformat()

    updated = update_platform_resources(
        {
            "mobile_apk_url": "/dashboard/assets/downloads/MedAssist-AI.apk",
            "apk_file_size": size_mb,
            "apk_original_name": file.filename,
            "apk_uploaded_at": now_iso,
        },
        updated_by=current_admin.email,
    )

    client_ip = request.client.host if request and request.client else None
    audit = AuditLog(
        user_id=current_admin.id,
        action="APK_VERSION_UPLOADED",
        resource_type="platform_resources",
        resource_id=None,
        details={
            "filename": file.filename,
            "file_size": size_mb,
            "updated_by": current_admin.email,
        },
        ip_address=client_ip,
    )
    db.add(audit)
    db.commit()

    logger.info(f"Admin {current_admin.email} deployed new APK: {file.filename} ({size_mb})")
    return PlatformResourcesResponse(**updated)


@router.post("/platform-resources/upload-thesis", response_model=PlatformResourcesResponse)
async def upload_admin_thesis(
    file: UploadFile = File(...),
    lang: str = Query("en", description="Language of thesis: en, fr, or ar"),
    request: Request = None,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> PlatformResourcesResponse:
    """
    Upload and deploy Master Thesis documentation PDF (English or French) (Admin only).
    Saves to dashboard/assets/docs/Thesis_Master_GLAA_{LANG}.pdf.
    """
    lang_clean = lang.lower().strip()
    if lang_clean not in ["en", "fr", "ar"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid language code. Supported languages: 'en' (English), 'fr' (French), 'ar' (Arabic).",
        )

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Please upload a PDF document (.pdf).",
        )

    docs_dir = str(PROJECT_ROOT / "dashboard" / "assets" / "docs")
    os.makedirs(docs_dir, exist_ok=True)
    filename = f"Thesis_Master_GLAA_{lang_clean.upper()}.pdf"
    target_path = os.path.join(docs_dir, filename)

    contents = await file.read()
    size_bytes = len(contents)
    if size_bytes == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded PDF file is empty.",
        )

    with open(target_path, "wb") as f:
        f.write(contents)

    size_mb = f"{size_bytes / (1024 * 1024):.2f} MB"
    field_key = f"thesis_{lang_clean}_url"
    size_key = f"thesis_{lang_clean}_size"

    updated = update_platform_resources(
        {
            field_key: f"/dashboard/assets/docs/{filename}",
            size_key: size_mb,
        },
        updated_by=current_admin.email,
    )

    client_ip = request.client.host if request and request.client else None
    audit = AuditLog(
        user_id=current_admin.id,
        action="THESIS_DOCUMENT_UPLOADED",
        resource_type="platform_resources",
        resource_id=None,
        details={
            "language": lang_clean,
            "filename": file.filename,
            "saved_as": filename,
            "file_size": size_mb,
            "updated_by": current_admin.email,
        },
        ip_address=client_ip,
    )
    db.add(audit)
    db.commit()

    logger.info(f"Admin {current_admin.email} uploaded {lang_clean.upper()} thesis ({size_mb})")
    return PlatformResourcesResponse(**updated)


@router.post("/platform-resources/upload-qr-code", response_model=PlatformResourcesResponse)
async def upload_admin_qr_code(
    file: UploadFile = File(...),
    request: Request = None,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> PlatformResourcesResponse:
    """
    Upload and deploy mobile download QR Code SVG image (Admin only).
    Saves directly to dashboard/assets/images/qr-code.svg.
    """
    if not file.filename or not file.filename.lower().endswith(".svg"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Please upload a vector SVG image (.svg).",
        )

    images_dir = str(PROJECT_ROOT / "dashboard" / "assets" / "images")
    os.makedirs(images_dir, exist_ok=True)
    target_path = os.path.join(images_dir, "qr-code.svg")

    contents = await file.read()
    size_bytes = len(contents)
    if size_bytes == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded SVG file is empty.",
        )
    if size_bytes > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SVG file size exceeds maximum limit of 5 MB.",
        )

    # Basic check for SVG markup
    try:
        sample = contents[:1024].decode("utf-8", errors="ignore").lower()
        if "<svg" not in sample and "<!doctype svg" not in sample:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid SVG format. The file does not contain valid SVG markup.",
            )
    except HTTPException:
        raise
    except Exception:
        pass

    with open(target_path, "wb") as f:
        f.write(contents)

    size_kb = f"{size_bytes / 1024:.2f} KB"
    updated = update_platform_resources(
        {
            "qr_code_url": "/dashboard/assets/images/qr-code.svg",
        },
        updated_by=current_admin.email,
    )

    client_ip = request.client.host if request and request.client else None
    audit = AuditLog(
        user_id=current_admin.id,
        action="QR_CODE_UPLOADED",
        resource_type="platform_resources",
        resource_id=None,
        details={
            "filename": file.filename,
            "saved_as": "qr-code.svg",
            "file_size": size_kb,
            "updated_by": current_admin.email,
        },
        ip_address=client_ip,
    )
    db.add(audit)
    db.commit()

    logger.info(f"Admin {current_admin.email} uploaded new QR Code SVG ({size_kb})")
    return PlatformResourcesResponse(**updated)





