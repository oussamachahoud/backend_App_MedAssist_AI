"""
app/api/v1/endpoints/profile.py
Doctor profile management and clinical analytics:
- View current doctor profile
- Update profile details (wilaya, phone, institution, etc.)
- Clinical statistics and activity summary
"""

from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_doctor, get_db
from app.core.logging import logger
from app.db_models.analysis import AnalysisRecord
from app.db_models.referral import Referral
from app.db_models.user import DoctorProfile, DoctorType, User
from app.schemas.auth import DoctorProfileResponse
from app.schemas.telemedicine import (
    DoctorProfileUpdateRequest,
    DoctorStatsResponse,
)

router = APIRouter(prefix="/profile", tags=["Doctor Profile"])


@router.get("", response_model=DoctorProfileResponse)
def get_my_profile(
    current_doctor: User = Depends(get_current_active_doctor),
    db: Session = Depends(get_db),
) -> DoctorProfileResponse:
    """
    Retrieve professional profile for current authenticated doctor.
    """
    if not current_doctor.profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor profile not found",
        )
    return DoctorProfileResponse.model_validate(current_doctor.profile)


@router.put("", response_model=DoctorProfileResponse)
def update_my_profile(
    profile_in: DoctorProfileUpdateRequest,
    current_doctor: User = Depends(get_current_active_doctor),
    db: Session = Depends(get_db),
) -> DoctorProfileResponse:
    """
    Update professional profile details (name, specialization, institution, phone, wilaya, avatar).
    """
    profile = current_doctor.profile
    if not profile:
        profile = DoctorProfile(
            user_id=current_doctor.id,
            full_name=profile_in.full_name or "Dr. " + current_doctor.email.split("@")[0],
            doctor_type=DoctorType.GENERAL_PRACTITIONER,
        )
        db.add(profile)

    if profile_in.full_name is not None:
        profile.full_name = profile_in.full_name
    if profile_in.specialization is not None:
        profile.specialization = profile_in.specialization
    if profile_in.institution_name is not None:
        profile.institution_name = profile_in.institution_name
    if profile_in.phone is not None:
        profile.phone = profile_in.phone
    if profile_in.wilaya is not None:
        profile.wilaya = profile_in.wilaya
    if profile_in.avatar_url is not None:
        profile.avatar_url = profile_in.avatar_url

    db.commit()
    db.refresh(profile)
    logger.info(f"Doctor {current_doctor.id} updated their profile")
    return DoctorProfileResponse.model_validate(profile)


@router.get("/stats", response_model=DoctorStatsResponse)
def get_doctor_stats(
    current_doctor: User = Depends(get_current_active_doctor),
    db: Session = Depends(get_db),
) -> DoctorStatsResponse:
    """
    Compute aggregate clinical metrics and telemetry for current doctor.
    """
    doc_id = current_doctor.id

    # Total analyses
    total_analyses = db.query(AnalysisRecord).filter(AnalysisRecord.doctor_id == doc_id).count()

    # Diagnoses distribution
    diag_rows = (
        db.query(AnalysisRecord.predicted_class, func.count(AnalysisRecord.id))
        .filter(AnalysisRecord.doctor_id == doc_id)
        .group_by(AnalysisRecord.predicted_class)
        .all()
    )
    diagnoses_distribution: Dict[str, int] = {row[0]: row[1] for row in diag_rows}

    # Risk level distribution
    risk_rows = (
        db.query(AnalysisRecord.risk_level, func.count(AnalysisRecord.id))
        .filter(AnalysisRecord.doctor_id == doc_id)
        .group_by(AnalysisRecord.risk_level)
        .all()
    )
    risk_distribution: Dict[str, int] = {row[0]: row[1] for row in risk_rows}

    # Feedback count
    feedback_count = (
        db.query(AnalysisRecord)
        .filter(
            AnalysisRecord.doctor_id == doc_id,
            AnalysisRecord.doctor_confirmed.isnot(None),
        )
        .count()
    )
    feedback_rate = (feedback_count / total_analyses * 100.0) if total_analyses > 0 else 0.0

    # Referrals counts
    sent_referrals_count = db.query(Referral).filter(Referral.referring_doctor_id == doc_id).count()
    received_referrals_count = db.query(Referral).filter(Referral.specialist_id == doc_id).count()

    return DoctorStatsResponse(
        total_analyses=total_analyses,
        diagnoses_distribution=diagnoses_distribution,
        risk_distribution=risk_distribution,
        feedback_count=feedback_count,
        feedback_rate_percentage=round(feedback_rate, 2),
        sent_referrals_count=sent_referrals_count,
        received_referrals_count=received_referrals_count,
    )

