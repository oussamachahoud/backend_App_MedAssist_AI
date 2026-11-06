"""
app/api/v1/endpoints/patients.py
Pseudonymous patient record management endpoints for doctors:
- Register anonymized patient code
- List and search patients
- Get patient file with lesion timeline
- Update patient record
- Soft-delete patient record
"""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_active_doctor, get_db
from app.core.logging import logger
from app.db_models.analysis import AnalysisRecord
from app.db_models.patient import Patient
from app.db_models.user import User, UserRole
from app.schemas.telemedicine import (
    PatientCreateRequest,
    PatientDetailResponse,
    PatientListResponse,
    PatientResponse,
    PatientTimelineItem,
    PatientUpdateRequest,
)
from app.services.storage_service import storage_service

router = APIRouter(prefix="/patients", tags=["Patients"])


@router.post("", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
def create_patient(
    patient_in: PatientCreateRequest,
    current_doctor: User = Depends(get_current_active_doctor),
    db: Session = Depends(get_db),
) -> PatientResponse:
    """
    Register a new pseudonymous patient record.
    """
    existing = db.query(Patient).filter(Patient.patient_code == patient_in.patient_code).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Patient code '{patient_in.patient_code}' already exists",
        )

    patient = Patient(
        created_by_doctor_id=current_doctor.id,
        patient_code=patient_in.patient_code,
        birth_year=patient_in.birth_year,
        sex=patient_in.sex,
        notes=patient_in.notes,
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    logger.info(f"Doctor {current_doctor.id} created patient {patient.patient_code} (id: {patient.id})")
    return PatientResponse.model_validate(patient)


@router.get("", response_model=PatientListResponse)
def list_patients(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by patient code"),
    current_doctor: User = Depends(get_current_active_doctor),
    db: Session = Depends(get_db),
) -> PatientListResponse:
    """
    Retrieve paginated list of active (non-deleted) patients.
    """
    query = db.query(Patient).filter(Patient.deleted_at.is_(None))

    if current_doctor.role != UserRole.ADMIN:
        query = query.filter(Patient.created_by_doctor_id == current_doctor.id)

    if search:
        query = query.filter(Patient.patient_code.ilike(f"%{search.strip()}%"))

    total = query.count()
    offset = (page - 1) * page_size
    records = (
        query.options(selectinload(Patient.analyses))
        .order_by(desc(Patient.created_at))
        .offset(offset)
        .limit(page_size)
        .all()
    )

    items = []
    for p in records:
        resp = PatientResponse.model_validate(p)
        resp.analyses_count = len(p.analyses) if p.analyses else 0
        items.append(resp)

    return PatientListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{patient_id}", response_model=PatientDetailResponse)
def get_patient(
    patient_id: uuid.UUID,
    current_doctor: User = Depends(get_current_active_doctor),
    db: Session = Depends(get_db),
) -> PatientDetailResponse:
    """
    Retrieve single patient details along with lesion tracking timeline.
    """
    patient = db.query(Patient).filter(
        Patient.id == patient_id,
        Patient.deleted_at.is_(None),
    ).first()

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    if patient.created_by_doctor_id != current_doctor.id and current_doctor.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: you can only view your own patient records",
        )

    # Fetch lesion timeline
    analyses = (
        db.query(AnalysisRecord)
        .filter(AnalysisRecord.patient_id == patient.id)
        .order_by(desc(AnalysisRecord.created_at))
        .all()
    )

    timeline: List[PatientTimelineItem] = []
    for a in analyses:
        img_url = None
        if a.image_storage_key:
            try:
                img_url = storage_service.get_presigned_url(a.image_storage_key)
            except Exception:
                img_url = None

        g_url = None
        if a.gradcam_storage_key:
            try:
                g_url = storage_service.get_presigned_url(a.gradcam_storage_key)
            except Exception:
                g_url = None

        timeline.append(
            PatientTimelineItem(
                analysis_id=a.id,
                created_at=a.created_at,
                lesion_tag=a.lesion_tag,
                predicted_class=a.predicted_class,
                confidence=a.confidence,
                risk_level=a.risk_level,
                image_url=img_url,
                gradcam_url=g_url,
                doctor_confirmed=a.doctor_confirmed,
            )
        )

    response_data = PatientResponse.model_validate(patient).model_dump()
    response_data["analyses_count"] = len(timeline)
    return PatientDetailResponse(**response_data, timeline=timeline)


@router.put("/{patient_id}", response_model=PatientResponse)
def update_patient(
    patient_id: uuid.UUID,
    patient_in: PatientUpdateRequest,
    current_doctor: User = Depends(get_current_active_doctor),
    db: Session = Depends(get_db),
) -> PatientResponse:
    """
    Update patient birth year, sex, or clinical notes.
    """
    patient = db.query(Patient).filter(
        Patient.id == patient_id,
        Patient.deleted_at.is_(None),
    ).first()

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    if patient.created_by_doctor_id != current_doctor.id and current_doctor.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: you can only update your own patient records",
        )

    if patient_in.birth_year is not None:
        patient.birth_year = patient_in.birth_year
    if patient_in.sex is not None:
        patient.sex = patient_in.sex
    if patient_in.notes is not None:
        patient.notes = patient_in.notes

    db.commit()
    db.refresh(patient)
    logger.info(f"Doctor {current_doctor.id} updated patient {patient.id}")
    return PatientResponse.model_validate(patient)


@router.delete("/{patient_id}")
def delete_patient(
    patient_id: uuid.UUID,
    current_doctor: User = Depends(get_current_active_doctor),
    db: Session = Depends(get_db),
):
    """
    Soft-delete a patient record (sets deleted_at).
    """
    patient = db.query(Patient).filter(
        Patient.id == patient_id,
        Patient.deleted_at.is_(None),
    ).first()

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    if patient.created_by_doctor_id != current_doctor.id and current_doctor.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: you can only delete your own patient records",
        )

    patient.deleted_at = func.now()
    db.commit()
    logger.info(f"Patient {patient_id} soft-deleted by user {current_doctor.id}")
    return {"message": "Patient deleted successfully", "patient_id": str(patient_id)}

