"""
app/api/v1/endpoints/public.py
Public unauthenticated endpoints:
- Public directory of verified active doctors (filter by wilaya, type)
- Patient follow-up verification via scanned QR code token
"""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.logging import logger
from app.core.security import decode_token
from app.db_models.analysis import AnalysisRecord
from app.db_models.user import DoctorProfile, DoctorType, User, UserStatus
from app.schemas.telemedicine import (
    PatientQRFollowUpResponse,
    PlatformResourcesResponse,
    PublicDoctorResponse,
)
from app.services.platform_resources import get_platform_resources

router = APIRouter(prefix="/public", tags=["Public"])


@router.get("/doctors", response_model=List[PublicDoctorResponse])
def get_public_doctors(
    wilaya: Optional[str] = Query(None, description="Filter by Algerian Wilaya code"),
    doctor_type: Optional[DoctorType] = Query(None, description="Filter by GP or Specialist"),
    db: Session = Depends(get_db),
) -> List[PublicDoctorResponse]:
    """
    Public directory of verified active healthcare practitioners on MedAssist AI.
    """
    query = (
        db.query(DoctorProfile)
        .join(User, DoctorProfile.user_id == User.id)
        .filter(User.status == UserStatus.ACTIVE)
    )

    if wilaya:
        query = query.filter(DoctorProfile.wilaya == wilaya)
    if doctor_type:
        query = query.filter(DoctorProfile.doctor_type == doctor_type)

    profiles = query.order_by(DoctorProfile.full_name).all()
    return [
        PublicDoctorResponse(
            id=p.user_id,
            user_id=p.user_id,
            profile_id=p.id,
            full_name=p.full_name,
            doctor_type=p.doctor_type,
            specialization=p.specialization,
            institution_name=p.institution_name,
            wilaya=p.wilaya,
            avatar_url=p.avatar_url,
        )
        for p in profiles
    ]


@router.get("/follow-up/{token}", response_model=PatientQRFollowUpResponse)
def get_patient_qr_followup(
    token: str,
    db: Session = Depends(get_db),
) -> PatientQRFollowUpResponse:
    """
    Resolve patient medical follow-up summary by decoding their QR code token.
    Publicly accessible without clinician authentication.
    """
    try:
        payload = decode_token(token)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning(f"Failed to decode QR token: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or corrupted QR token",
        )

    if payload.get("type") != "qr_access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type for patient follow-up",
        )

    analysis_id_str = payload.get("sub")
    if not analysis_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload is missing analysis reference",
        )

    try:
        analysis_id = uuid.UUID(analysis_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed analysis reference in token",
        )

    record = db.query(AnalysisRecord).filter(AnalysisRecord.id == analysis_id).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis record not found",
        )

    doctor_inst = None
    if record.doctor and record.doctor.profile:
        doctor_inst = record.doctor.profile.institution_name

    return PatientQRFollowUpResponse(
        analysis_id=record.id,
        predicted_class=record.predicted_class,
        confidence=record.confidence,
        risk_level=record.risk_level,
        recommendations=record.recommendations,
        created_at=record.created_at,
        next_followup_date=record.next_followup_date,
        doctor_confirmed=record.doctor_confirmed,
        doctor_diagnosis=record.doctor_diagnosis,
        doctor_institution=doctor_inst,
    )


@router.get("/platform-resources", response_model=PlatformResourcesResponse)
def get_public_platform_resources() -> PlatformResourcesResponse:
    """
    Publicly accessible platform resources (walkthrough video URL, mobile APK download, thesis docs).
    Configured dynamically by the System Administrator.
    """
    data = get_platform_resources()
    return PlatformResourcesResponse(**data)


