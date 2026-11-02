"""
app/api/v1/endpoints/analyses.py
Analyses management endpoints for verified doctors:
- List analyses with pagination and filters
- Retrieve single analysis with presigned image and Grad-CAM URLs
- Submit clinical doctor feedback and biopsy outcome
- Delete analysis record
- Export official medical PDF report with QR code
"""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_doctor, get_db
from app.core.logging import logger
from app.core.security import create_qr_token
from app.db_models.analysis import AnalysisRecord
from app.db_models.patient import Patient
from app.db_models.referral import Referral
from app.db_models.user import User, UserRole
from app.schemas.telemedicine import (
    AnalysisFeedbackRequest,
    AnalysisListResponse,
    AnalysisResponse,
)
from app.services.pdf_service import generate_analysis_pdf
from app.services.storage_service import storage_service

router = APIRouter(prefix="/analyses", tags=["Analyses"])


def _build_analysis_response(record: AnalysisRecord) -> AnalysisResponse:
    """Helper to convert AnalysisRecord to AnalysisResponse with presigned URLs."""
    image_url = None
    if record.image_storage_key:
        try:
            image_url = storage_service.get_presigned_url(record.image_storage_key)
        except Exception as e:
            logger.warning(f"Failed to generate presigned URL for image: {e}")

    gradcam_url = None
    if record.gradcam_storage_key:
        try:
            gradcam_url = storage_service.get_presigned_url(record.gradcam_storage_key)
        except Exception as e:
            logger.warning(f"Failed to generate presigned URL for Grad-CAM: {e}")

    return AnalysisResponse(
        id=record.id,
        doctor_id=record.doctor_id,
        patient_id=record.patient_id,
        lesion_tag=record.lesion_tag,
        image_storage_key=record.image_storage_key,
        image_url=image_url,
        gradcam_storage_key=record.gradcam_storage_key,
        gradcam_url=gradcam_url,
        clinical_data=record.clinical_data,
        predicted_class=record.predicted_class,
        confidence=record.confidence,
        all_probabilities=record.all_probabilities,
        risk_level=record.risk_level,
        risk_escalated=record.risk_escalated,
        recommendations=record.recommendations,
        inference_time_ms=record.inference_time_ms,
        model_version=record.model_version,
        doctor_confirmed=record.doctor_confirmed,
        doctor_diagnosis=record.doctor_diagnosis,
        biopsy_performed=record.biopsy_performed,
        biopsy_result=record.biopsy_result,
        next_followup_date=record.next_followup_date,
        created_at=record.created_at,
    )


@router.get("", response_model=AnalysisListResponse)
def list_analyses(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    patient_id: Optional[uuid.UUID] = Query(None, description="Filter by patient ID"),
    risk_level: Optional[str] = Query(None, description="Filter by risk level"),
    predicted_class: Optional[str] = Query(None, description="Filter by diagnostic class"),
    doctor_confirmed: Optional[bool] = Query(None, description="Filter by confirmation status"),
    start_date: Optional[datetime] = Query(None, description="Created on or after"),
    end_date: Optional[datetime] = Query(None, description="Created on or before"),
    current_doctor: User = Depends(get_current_active_doctor),
    db: Session = Depends(get_db),
) -> AnalysisListResponse:
    """
    Retrieve paginated list of analyses.
    Doctors view analyses they conducted (Admins view all analyses).
    """
    query = db.query(AnalysisRecord)

    if current_doctor.role != UserRole.ADMIN:
        query = query.filter(AnalysisRecord.doctor_id == current_doctor.id)

    if patient_id:
        query = query.filter(AnalysisRecord.patient_id == patient_id)
    if risk_level:
        query = query.filter(AnalysisRecord.risk_level == risk_level.upper())
    if predicted_class:
        query = query.filter(AnalysisRecord.predicted_class == predicted_class.upper())
    if doctor_confirmed is not None:
        query = query.filter(AnalysisRecord.doctor_confirmed == doctor_confirmed)
    if start_date:
        query = query.filter(AnalysisRecord.created_at >= start_date)
    if end_date:
        query = query.filter(AnalysisRecord.created_at <= end_date)

    total = query.count()
    offset = (page - 1) * page_size
    records = query.order_by(desc(AnalysisRecord.created_at)).offset(offset).limit(page_size).all()

    items = [_build_analysis_response(r) for r in records]
    return AnalysisListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{analysis_id}", response_model=AnalysisResponse)
def get_analysis(
    analysis_id: uuid.UUID,
    current_doctor: User = Depends(get_current_active_doctor),
    db: Session = Depends(get_db),
) -> AnalysisResponse:
    """
    Retrieve single analysis record with presigned URLs.
    Authorized if requester is the examining doctor, assigned specialist via referral, or admin.
    """
    record = db.query(AnalysisRecord).filter(AnalysisRecord.id == analysis_id).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis record not found",
        )

    # Authorization check
    is_owner = record.doctor_id == current_doctor.id
    is_admin = current_doctor.role == UserRole.ADMIN
    is_assigned_specialist = False

    if not (is_owner or is_admin):
        referral = db.query(Referral).filter(
            Referral.analysis_id == analysis_id,
            Referral.specialist_id == current_doctor.id,
        ).first()
        is_assigned_specialist = referral is not None

    if not (is_owner or is_admin or is_assigned_specialist):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: you are not authorized to view this analysis",
        )

    return _build_analysis_response(record)


@router.put("/{analysis_id}/feedback", response_model=AnalysisResponse)
def update_analysis_feedback(
    analysis_id: uuid.UUID,
    feedback: AnalysisFeedbackRequest,
    current_doctor: User = Depends(get_current_active_doctor),
    db: Session = Depends(get_db),
) -> AnalysisResponse:
    """
    Submit clinical confirmation, secondary diagnosis, biopsy tracking, and next follow-up.
    Authorized for the owning doctor, assigned specialist, or admin.
    """
    record = db.query(AnalysisRecord).filter(AnalysisRecord.id == analysis_id).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis record not found",
        )

    is_owner = record.doctor_id == current_doctor.id
    is_admin = current_doctor.role == UserRole.ADMIN
    is_assigned_specialist = False

    if not (is_owner or is_admin):
        referral = db.query(Referral).filter(
            Referral.analysis_id == analysis_id,
            Referral.specialist_id == current_doctor.id,
        ).first()
        is_assigned_specialist = referral is not None

    if not (is_owner or is_admin or is_assigned_specialist):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: you cannot update feedback for this analysis",
        )

    record.doctor_confirmed = feedback.doctor_confirmed
    if feedback.doctor_diagnosis is not None:
        record.doctor_diagnosis = feedback.doctor_diagnosis
    if feedback.biopsy_performed is not None:
        record.biopsy_performed = feedback.biopsy_performed
    if feedback.biopsy_result is not None:
        record.biopsy_result = feedback.biopsy_result
    if feedback.next_followup_date is not None:
        record.next_followup_date = feedback.next_followup_date

    db.commit()
    db.refresh(record)
    logger.info(f"Doctor {current_doctor.id} updated feedback for analysis {record.id}")

    return _build_analysis_response(record)


@router.delete("/{analysis_id}")
def delete_analysis(
    analysis_id: uuid.UUID,
    current_doctor: User = Depends(get_current_active_doctor),
    db: Session = Depends(get_db),
):
    """
    Delete an analysis record.
    Allowed only for the doctor who created it or a system admin.
    """
    record = db.query(AnalysisRecord).filter(AnalysisRecord.id == analysis_id).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis record not found",
        )

    if record.doctor_id != current_doctor.id and current_doctor.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: you can only delete your own analyses",
        )

    # Attempt to clean up storage objects in MinIO
    if record.image_storage_key:
        try:
            storage_service.delete_image(record.image_storage_key)
        except Exception as e:
            logger.warning(f"Failed to delete image storage object {record.image_storage_key}: {e}")

    if record.gradcam_storage_key:
        try:
            storage_service.delete_image(record.gradcam_storage_key)
        except Exception as e:
            logger.warning(f"Failed to delete gradcam storage object {record.gradcam_storage_key}: {e}")

    db.delete(record)
    db.commit()
    logger.info(f"Analysis {analysis_id} deleted by user {current_doctor.id}")
    return {"message": "Analysis deleted successfully", "analysis_id": str(analysis_id)}


@router.post("/{analysis_id}/export-pdf")
def export_analysis_pdf(
    analysis_id: uuid.UUID,
    current_doctor: User = Depends(get_current_active_doctor),
    db: Session = Depends(get_db),
):
    """
    Generate and stream an official clinical PDF report with follow-up QR code.
    """
    record = db.query(AnalysisRecord).filter(AnalysisRecord.id == analysis_id).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis record not found",
        )

    is_owner = record.doctor_id == current_doctor.id
    is_admin = current_doctor.role == UserRole.ADMIN
    is_assigned_specialist = False

    if not (is_owner or is_admin):
        referral = db.query(Referral).filter(
            Referral.analysis_id == analysis_id,
            Referral.specialist_id == current_doctor.id,
        ).first()
        is_assigned_specialist = referral is not None

    if not (is_owner or is_admin or is_assigned_specialist):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: you are not authorized to export this report",
        )

    patient = None
    if record.patient_id:
        patient = db.query(Patient).filter(Patient.id == record.patient_id).first()

    qr_token = create_qr_token(analysis_id=record.id)
    pdf_bytes = generate_analysis_pdf(
        analysis=record,
        doctor_profile=current_doctor.profile,
        patient=patient,
        qr_token=qr_token,
    )

    filename = f"MedAssist_Report_{str(record.id)[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "application/pdf",
        },
    )

