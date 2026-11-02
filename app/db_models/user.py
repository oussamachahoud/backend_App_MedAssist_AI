"""
app/db_models/user.py
SQLAlchemy models for User, DoctorProfile, and RefreshToken.
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import FetchedValue

from app.core.database import Base

if TYPE_CHECKING:
    from app.db_models.patient import Patient
    from app.db_models.analysis import AnalysisRecord
    from app.db_models.referral import Referral
    from app.db_models.audit import AuditLog


class UserRole(str, enum.Enum):
    """User authorization roles."""
    DOCTOR = "doctor"
    ADMIN = "admin"


class UserStatus(str, enum.Enum):
    """User account approval statuses."""
    PENDING_VERIFICATION = "pending_verification"
    ACTIVE = "active"
    SUSPENDED = "suspended"


class DoctorType(str, enum.Enum):
    """Doctor category: Frontline GP or Specialist."""
    GENERAL_PRACTITIONER = "general_practitioner"
    SPECIALIST_DERMATOLOGIST = "specialist_dermatologist"


class User(Base):
    """
    Central user authentication table.
    Supports both doctors and system administrators.
    """
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="user_role",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=UserRole.DOCTOR,
    )
    status: Mapped[UserStatus] = mapped_column(
        Enum(
            UserStatus,
            name="user_status",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=UserStatus.PENDING_VERIFICATION,
    )
    must_change_password: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    last_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # ── Relationships ────────────────────────────────────────────────────────
    profile: Mapped[Optional["DoctorProfile"]] = relationship(
        "DoctorProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    refresh_tokens: Mapped[List["RefreshToken"]] = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    created_patients: Mapped[List["Patient"]] = relationship(
        "Patient",
        back_populates="doctor",
        foreign_keys="[Patient.created_by_doctor_id]",
    )
    analyses: Mapped[List["AnalysisRecord"]] = relationship(
        "AnalysisRecord",
        back_populates="doctor",
        foreign_keys="[AnalysisRecord.doctor_id]",
    )
    sent_referrals: Mapped[List["Referral"]] = relationship(
        "Referral",
        back_populates="referring_doctor",
        foreign_keys="[Referral.referring_doctor_id]",
    )
    received_referrals: Mapped[List["Referral"]] = relationship(
        "Referral",
        back_populates="specialist",
        foreign_keys="[Referral.specialist_id]",
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="user",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role} status={self.status}>"


class DoctorProfile(Base):
    """
    Professional profile details for verified doctors.
    Linked 1:1 with the User table.
    """
    __tablename__ = "doctor_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    doctor_type: Mapped[DoctorType] = mapped_column(
        Enum(
            DoctorType,
            name="doctor_type",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=DoctorType.GENERAL_PRACTITIONER,
    )
    specialization: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    license_number: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    institution_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    phone: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    wilaya: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
    )
    avatar_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        server_onupdate=FetchedValue(),
        onupdate=func.now(),
        nullable=False,
    )

    # ── Relationships ────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship(
        "User",
        back_populates="profile",
    )

    def __repr__(self) -> str:
        return f"<DoctorProfile id={self.id} user_id={self.user_id} name={self.full_name} type={self.doctor_type}>"


class RefreshToken(Base):
    """
    Hashed refresh tokens stored for revocable sessions.
    """
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    is_revoked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # ── Relationships ────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship(
        "User",
        back_populates="refresh_tokens",
    )

    def __repr__(self) -> str:
        return f"<RefreshToken id={self.id} user_id={self.user_id} revoked={self.is_revoked}>"
