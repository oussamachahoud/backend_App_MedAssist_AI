"""
app/api/v1/endpoints/referrals.py
Telemedicine referral workflow between Frontline GPs and Dermatologist Specialists:
- Create referral for suspicious analysis
- List sent referrals (GP dashboard)
- List received / unassigned referrals (Specialist dashboard)
- Get referral details
- Specialist clinical evaluation and response
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_active_doctor,
    get_current_specialist,
    get_db,
)
from app.api.v1.endpoints.analyses import _build_analysis_response
from app.core.logging import logger
from app.db_models.analysis import AnalysisRecord
from app.db_models.referral import Referral, ReferralStatus
from app.db_models.user import DoctorProfile, DoctorType, User, UserRole, UserStatus
from app.schemas.telemedicine import (
    ReferralCreateRequest,
    ReferralListResponse,
    ReferralRespondRequest,
    ReferralResponse,
)

router = APIRouter(prefix="/referrals", tags=["Referrals"])


def _build_referral_response(ref: Referral) -> ReferralResponse:
    """Helper to convert a Referral model instance into ReferralResponse schema."""
    ref_dr_name = None
    if ref.referring_doctor and ref.referring_doctor.profile:
        ref_dr_name = ref.referring_doctor.profile.full_name
    elif ref.referring_doctor:
        ref_dr_name = ref.referring_doctor.email

    spec_name = None
    if ref.specialist and ref.specialist.profile:
        spec_name = ref.specialist.profile.full_name
    elif ref.specialist:
        spec_name = ref.specialist.email

    analysis_resp = None
    if ref.analysis:
        analysis_resp = _build_analysis_response(ref.analysis)

    return ReferralResponse(
        id=ref.id,
        analysis_id=ref.analysis_id,
        referring_doctor_id=ref.referring_doctor_id,
        specialist_id=ref.specialist_id,
        status=ref.status,
        referral_note=ref.referral_note,
        specialist_response=ref.specialist_response,
        created_at=ref.created_at,
        responded_at=ref.responded_at,
        analysis=analysis_resp,
        referring_doctor_name=ref_dr_name,
        specialist_name=spec_name,
    )


@router.post("", response_model=ReferralResponse, status_code=status.HTTP_201_CREATED)
def create_referral(
    referral_in: ReferralCreateRequest,
    current_doctor: User = Depends(get_current_active_doctor),
    db: Session = Depends(get_db),
) -> ReferralResponse:
    """
    GP creates a referral for an analysis to a dermatologist specialist.
    """
    analysis = db.query(AnalysisRecord).filter(AnalysisRecord.id == referral_in.analysis_id).first()
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis record not found",
        )

    if analysis.doctor_id != current_doctor.id and current_doctor.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only refer analyses that you conducted",
        )

    # Check if referral already exists
    existing = db.query(Referral).filter(Referral.analysis_id == referral_in.analysis_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A referral has already been created for this analysis",
        )

    # Validate specialist if specified (supports User.id or DoctorProfile.id)
    designated_specialist_id = None
    if referral_in.specialist_id:
        specialist = (
            db.query(User)
            .join(DoctorProfile, User.id == DoctorProfile.user_id, isouter=True)
            .filter(
                or_(
                    User.id == referral_in.specialist_id,
                    DoctorProfile.id == referral_in.specialist_id,
                ),
                User.status == UserStatus.ACTIVE,
            )
            .first()
        )
        if not specialist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Designated specialist not found or account is not active",
            )
        if not specialist.profile or specialist.profile.doctor_type != DoctorType.SPECIALIST_DERMATOLOGIST:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Designated doctor is not a registered specialist dermatologist",
            )
        designated_specialist_id = specialist.id

    referral = Referral(
        analysis_id=referral_in.analysis_id,
        referring_doctor_id=current_doctor.id,
        specialist_id=designated_specialist_id,
        status=ReferralStatus.PENDING,
        referral_note=referral_in.referral_note,
    )
    db.add(referral)
    db.commit()
    db.refresh(referral)
    logger.info(f"Referral {referral.id} created by doctor {current_doctor.id} for analysis {analysis.id}")
    return _build_referral_response(referral)


@router.get("/sent", response_model=ReferralListResponse)
def list_sent_referrals(
    status_filter: Optional[ReferralStatus] = Query(None, alias="status", description="Filter by status"),
    current_doctor: User = Depends(get_current_active_doctor),
    db: Session = Depends(get_db),
) -> ReferralListResponse:
    """
    List all referrals sent by the current doctor.
    """
    query = db.query(Referral).filter(Referral.referring_doctor_id == current_doctor.id)
    if status_filter:
        query = query.filter(Referral.status == status_filter)

    records = query.order_by(desc(Referral.created_at)).all()
    items = [_build_referral_response(r) for r in records]
    return ReferralListResponse(items=items, total=len(items))


@router.get("/received", response_model=ReferralListResponse)
def list_received_referrals(
    status_filter: Optional[ReferralStatus] = Query(None, alias="status", description="Filter by status"),
    current_specialist: User = Depends(get_current_specialist),
    db: Session = Depends(get_db),
) -> ReferralListResponse:
    """
    List referrals assigned to the current specialist or unassigned pending in queue.
    """
    query = db.query(Referral).filter(
        or_(
            Referral.specialist_id == current_specialist.id,
            Referral.specialist_id.is_(None),
        )
    )
    if status_filter:
        query = query.filter(Referral.status == status_filter)

    records = query.order_by(desc(Referral.created_at)).all()
    items = [_build_referral_response(r) for r in records]
    return ReferralListResponse(items=items, total=len(items))


@router.get("/{referral_id}", response_model=ReferralResponse)
def get_referral(
    referral_id: uuid.UUID,
    current_doctor: User = Depends(get_current_active_doctor),
    db: Session = Depends(get_db),
) -> ReferralResponse:
    """
    Retrieve single referral details.
    Accessible by referring doctor, assigned specialist, unassigned specialist, or admin.
    """
    ref = db.query(Referral).filter(Referral.id == referral_id).first()
    if not ref:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Referral not found",
        )

    is_sender = ref.referring_doctor_id == current_doctor.id
    is_assigned = ref.specialist_id == current_doctor.id
    is_unassigned_specialist = (
        ref.specialist_id is None
        and current_doctor.profile
        and current_doctor.profile.doctor_type == DoctorType.SPECIALIST_DERMATOLOGIST
    )
    is_admin = current_doctor.role == UserRole.ADMIN

    if not (is_sender or is_assigned or is_unassigned_specialist or is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: you are not authorized to view this referral",
        )

    return _build_referral_response(ref)


@router.put("/{referral_id}/respond", response_model=ReferralResponse)
def respond_to_referral(
    referral_id: uuid.UUID,
    resp_in: ReferralRespondRequest,
    current_specialist: User = Depends(get_current_specialist),
    db: Session = Depends(get_db),
) -> ReferralResponse:
    """
    Specialist reviews and responds to a referral case.
    """
    ref = db.query(Referral).filter(Referral.id == referral_id).first()
    if not ref:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Referral not found",
        )

    if ref.specialist_id is not None and ref.specialist_id != current_specialist.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This referral is assigned to another specialist",
        )

    # Assign specialist if unassigned
    if ref.specialist_id is None:
        ref.specialist_id = current_specialist.id

    ref.status = resp_in.status
    ref.specialist_response = resp_in.specialist_response
    ref.responded_at = func.now()

    db.commit()
    db.refresh(ref)
    logger.info(f"Specialist {current_specialist.id} responded to referral {ref.id} with status {ref.status}")
    return _build_referral_response(ref)

