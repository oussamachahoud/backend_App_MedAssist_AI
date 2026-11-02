"""
app/db_models/analysis.py
SQLAlchemy model for AnalysisRecord storing AI predictions and doctor feedback.
"""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.db_models.user import User
    from app.db_models.patient import Patient
    from app.db_models.referral import Referral


class AnalysisRecord(Base):
    """
    Stores an AI lesion analysis result, clinical context,
    storage references in MinIO, and doctor feedback.
    """
    __tablename__ = "analysis_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    patient_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    lesion_tag: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    image_storage_key: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    gradcam_storage_key: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    clinical_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )
    predicted_class: Mapped[str] = mapped_column(
        String(50),
        index=True,
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    all_probabilities: Mapped[Dict[str, float]] = mapped_column(
        JSONB,
        nullable=False,
    )
    risk_level: Mapped[str] = mapped_column(
        String(50),
        index=True,
        nullable=False,
    )
    risk_escalated: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    recommendations: Mapped[Optional[Any]] = mapped_column(
        JSONB,
        nullable=True,
    )
    inference_time_ms: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    model_version: Mapped[str] = mapped_column(
        String(50),
        default="V6.0",
        nullable=False,
    )

    # ── Doctor Review & Feedback ─────────────────────────────────────────────
    doctor_confirmed: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
    )
    doctor_diagnosis: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    biopsy_performed: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
    )
    biopsy_result: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    next_followup_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )

    # ── Audit Timestamps ─────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
        nullable=False,
    )

    # ── Relationships ────────────────────────────────────────────────────────
    doctor: Mapped["User"] = relationship(
        "User",
        back_populates="analyses",
        foreign_keys=[doctor_id],
    )
    patient: Mapped[Optional["Patient"]] = relationship(
        "Patient",
        back_populates="analyses",
        foreign_keys=[patient_id],
    )
    referral: Mapped[Optional["Referral"]] = relationship(
        "Referral",
        back_populates="analysis",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<AnalysisRecord id={self.id} doctor_id={self.doctor_id} "
            f"predicted={self.predicted_class} risk={self.risk_level}>"
        )

