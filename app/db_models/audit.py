"""
app/db_models/audit.py
SQLAlchemy model for administrative and security Audit Logs.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.db_models.user import User


class AuditLog(Base):
    """
    Security and administrative audit trail.
    Tracks all critical actions (auth, analyses, referrals, user verification).
    """
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    action: Mapped[str] = mapped_column(
        String(100),
        index=True,
        nullable=False,
    )
    resource_type: Mapped[str] = mapped_column(
        String(50),
        index=True,
        nullable=False,
    )
    resource_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
        nullable=False,
    )

    # ── Relationships ────────────────────────────────────────────────────────
    user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="audit_logs",
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog id={self.id} action={self.action} "
            f"user_id={self.user_id} resource={self.resource_type}:{self.resource_id}>"
        )

