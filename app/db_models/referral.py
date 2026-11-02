"""
app/db_models/referral.py
SQLAlchemy model for Telemedicine Referrals between Frontline GP and Specialist.
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.db_models.user import User
    from app.db_models.analysis import AnalysisRecord


class ReferralStatus(str, enum.Enum):
    """Lifecycle statuses for a telemedicine referral."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Referral(Base):
    """
    Telemedicine referral record linking an analysis case
    from a frontline GP to a dermatologist specialist.
    """
    __tablename__ = "referrals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_records.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    referring_doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    specialist_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    status: Mapped[ReferralStatus] = mapped_column(
        Enum(
            ReferralStatus,
            name="referral_status",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=ReferralStatus.PENDING,
        index=True,
    )
    referral_note: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    specialist_response: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    responded_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # ── Relationships ────────────────────────────────────────────────────────
    analysis: Mapped["AnalysisRecord"] = relationship(
        "AnalysisRecord",
        back_populates="referral",
    )
    referring_doctor: Mapped["User"] = relationship(
        "User",
        back_populates="sent_referrals",
        foreign_keys=[referring_doctor_id],
    )
    specialist: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="received_referrals",
        foreign_keys=[specialist_id],
    )

    def __repr__(self) -> str:
        return (
            f"<Referral id={self.id} analysis_id={self.analysis_id} "
            f"from={self.referring_doctor_id} to={self.specialist_id} status={self.status}>"
        )
