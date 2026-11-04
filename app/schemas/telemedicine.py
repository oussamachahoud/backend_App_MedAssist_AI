"""
app/schemas/telemedicine.py
Pydantic V2 schemas for Phase 4 telemedicine endpoints:
- Analyses CRUD, doctor feedback, and export
- Pseudonymous Patients and Lesion Timelines
- Telemedicine Referrals (GP <-> Specialist)
- Doctor Profiles and Clinical Statistics
- Public doctor directory and Patient QR follow-up
- Administration user management and metrics
"""

import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.db_models.patient import PatientSex
from app.db_models.referral import ReferralStatus
from app.db_models.user import DoctorType, UserRole, UserStatus
from app.schemas.auth import DoctorProfileResponse, UserResponse


# ── 1. Analyses Schemas ───────────────────────────────────────────────────────

class AnalysisFeedbackRequest(BaseModel):
    doctor_confirmed: bool
    doctor_diagnosis: Optional[str] = Field(None, max_length=100)
    biopsy_performed: Optional[bool] = None
    biopsy_result: Optional[str] = Field(None, max_length=255)
    next_followup_date: Optional[date] = None


class AnalysisResponse(BaseModel):
    id: uuid.UUID
    doctor_id: uuid.UUID
    patient_id: Optional[uuid.UUID] = None
    lesion_tag: Optional[str] = None
    image_storage_key: str
    image_url: Optional[str] = None
    gradcam_storage_key: Optional[str] = None
    gradcam_url: Optional[str] = None
    clinical_data: Optional[Dict[str, Any]] = None
    predicted_class: str
    confidence: float
    all_probabilities: Dict[str, float]
    risk_level: str
    risk_escalated: bool
    recommendations: Optional[Any] = None
    inference_time_ms: float
    model_version: str
    doctor_confirmed: Optional[bool] = None
    doctor_diagnosis: Optional[str] = None
    biopsy_performed: Optional[bool] = None
    biopsy_result: Optional[str] = None
    next_followup_date: Optional[date] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AnalysisListResponse(BaseModel):
    items: List[AnalysisResponse]
    total: int
    page: int
    page_size: int


# ── 2. Patient Schemas ────────────────────────────────────────────────────────

class PatientCreateRequest(BaseModel):
    patient_code: str = Field(..., min_length=2, max_length=50)
    birth_year: int = Field(..., ge=1900, le=2026)
    sex: PatientSex = PatientSex.MALE
    notes: Optional[str] = None


class PatientUpdateRequest(BaseModel):
    birth_year: Optional[int] = Field(None, ge=1900, le=2026)
    sex: Optional[PatientSex] = None
    notes: Optional[str] = None


class PatientResponse(BaseModel):
    id: uuid.UUID
    created_by_doctor_id: uuid.UUID
    patient_code: str
    birth_year: int
    sex: PatientSex
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PatientListResponse(BaseModel):
    items: List[PatientResponse]
    total: int
    page: int
    page_size: int


class PatientTimelineItem(BaseModel):
    analysis_id: uuid.UUID
    created_at: datetime
    lesion_tag: Optional[str] = None
    predicted_class: str
    confidence: float
    risk_level: str
    image_url: Optional[str] = None
    gradcam_url: Optional[str] = None
    doctor_confirmed: Optional[bool] = None


class PatientDetailResponse(PatientResponse):
    timeline: List[PatientTimelineItem] = []


# ── 3. Referral Schemas ───────────────────────────────────────────────────────

class ReferralCreateRequest(BaseModel):
    analysis_id: uuid.UUID
    specialist_id: Optional[uuid.UUID] = None
    referral_note: str = Field(..., min_length=5, max_length=1000)


class ReferralRespondRequest(BaseModel):
    status: ReferralStatus = ReferralStatus.COMPLETED
    specialist_response: str = Field(..., min_length=5, max_length=2000)


class ReferralUpdateRequest(BaseModel):
    referral_note: Optional[str] = Field(None, min_length=2, max_length=1000)
    specialist_id: Optional[uuid.UUID] = None
    specialist_response: Optional[str] = Field(None, min_length=2, max_length=2000)
    status: Optional[ReferralStatus] = None


class ReferralResponse(BaseModel):
    id: uuid.UUID
    analysis_id: uuid.UUID
    referring_doctor_id: uuid.UUID
    specialist_id: Optional[uuid.UUID] = None
    status: ReferralStatus
    referral_note: str
    specialist_response: Optional[str] = None
    created_at: datetime
    responded_at: Optional[datetime] = None
    analysis: Optional[AnalysisResponse] = None
    referring_doctor_name: Optional[str] = None
    specialist_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ReferralListResponse(BaseModel):
    items: List[ReferralResponse]
    total: int


# ── 4. Doctor Profile & Statistics Schemas ───────────────────────────────────

class DoctorProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    specialization: Optional[str] = Field(None, max_length=255)
    institution_name: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    wilaya: Optional[str] = Field(None, max_length=10)
    avatar_url: Optional[str] = Field(None, max_length=500)


class DoctorStatsResponse(BaseModel):
    total_analyses: int
    diagnoses_distribution: Dict[str, int]
    risk_distribution: Dict[str, int]
    feedback_count: int
    feedback_rate_percentage: float
    sent_referrals_count: int
    received_referrals_count: int


# ── 5. Public & Patient QR Schemas ───────────────────────────────────────────

class PublicDoctorResponse(BaseModel):
    id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    profile_id: Optional[uuid.UUID] = None
    full_name: str
    doctor_type: DoctorType
    specialization: Optional[str] = None
    institution_name: Optional[str] = None
    wilaya: Optional[str] = None
    avatar_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PatientQRFollowUpResponse(BaseModel):
    analysis_id: uuid.UUID
    predicted_class: str
    confidence: float
    risk_level: str
    recommendations: Optional[Any] = None
    created_at: datetime
    next_followup_date: Optional[date] = None
    doctor_confirmed: Optional[bool] = None
    doctor_diagnosis: Optional[str] = None
    doctor_institution: Optional[str] = None


# ── 6. Admin Schemas ─────────────────────────────────────────────────────────

class AdminUserListResponse(BaseModel):
    items: List[UserResponse]
    total: int
    page: int
    page_size: int


class AdminUserStatusUpdateRequest(BaseModel):
    status: UserStatus


class AdminResetPasswordResponse(BaseModel):
    temporary_password: str
    message: str


class AdminStatsResponse(BaseModel):
    total_users: int
    active_doctors: int
    pending_verifications: int
    suspended_users: int
    total_analyses: int
    total_patients: int
    total_referrals: int


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    action: str
    resource_type: str
    resource_id: Optional[uuid.UUID] = None
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditLogListResponse(BaseModel):
    items: List[AuditLogResponse]
    total: int
    page: int
    page_size: int


class AdminAnalyticsResponse(BaseModel):
    geographical_distribution: Dict[str, int]
    diagnostic_class_distribution: Dict[str, int]
    risk_distribution: Dict[str, int]
    model_concordance_rate_percentage: float
    average_inference_time_ms: float


class PlatformResourcesResponse(BaseModel):
    video_walkthrough_url: str
    mobile_apk_url: str
    landing_page_url: str
    thesis_en_url: str
    thesis_fr_url: Optional[str] = None
    thesis_ar_url: Optional[str] = None
    announcement: str
    updated_at: str
    updated_by: str
    apk_file_size: Optional[str] = None
    apk_original_name: Optional[str] = None
    apk_uploaded_at: Optional[str] = None
    thesis_en_size: Optional[str] = None
    thesis_fr_size: Optional[str] = None
    qr_code_url: Optional[str] = "/dashboard/assets/images/qr-code.svg"


class PlatformResourcesUpdateRequest(BaseModel):
    video_walkthrough_url: Optional[str] = None
    mobile_apk_url: Optional[str] = None
    landing_page_url: Optional[str] = None
    thesis_en_url: Optional[str] = None
    thesis_fr_url: Optional[str] = None
    thesis_ar_url: Optional[str] = None
    announcement: Optional[str] = None
    apk_file_size: Optional[str] = None
    apk_original_name: Optional[str] = None
    apk_uploaded_at: Optional[str] = None
    thesis_en_size: Optional[str] = None
    thesis_fr_size: Optional[str] = None
    qr_code_url: Optional[str] = None

