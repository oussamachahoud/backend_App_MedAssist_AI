"""
app/db_models/patient.py
SQLAlchemy model for pseudonymous Patient records.
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.db_models.user import User
    from app.db_models.analysis import AnalysisRecord


class PatientSex(str, enum.Enum):
    """Patient biological sex."""
    MALE = "male"
    FEMALE = "female"


class Patient(Base):
    """
    Pseudonymized patient record created by a doctor.
    Supports soft deletion via `deleted_at`.
    """
    __tablename__ = "patients"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    created_by_doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    patient_code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )
    birth_year: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    sex: Mapped[PatientSex] = mapped_column(
        Enum(
            PatientSex,
            name="patient_sex",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    # ── Relationships ────────────────────────────────────────────────────────
    doctor: Mapped["User"] = relationship(
        "User",
        back_populates="created_patients",
        foreign_keys=[created_by_doctor_id],
    )
    analyses: Mapped[List["AnalysisRecord"]] = relationship(
        "AnalysisRecord",
        back_populates="patient",
    )

    def __repr__(self) -> str:
        return f"<Patient id={self.id} code={self.patient_code} birth_year={self.birth_year} sex={self.sex}>"
