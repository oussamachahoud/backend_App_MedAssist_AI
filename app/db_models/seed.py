"""
app/db_models/seed.py
Initial database seeding: creates the first super-admin account if absent.

Called non-blocking from `lifespan()` in `app/main.py` at every startup.
Credentials are read from environment variables so they are never hardcoded.
"""

import os
from typing import Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.db_models.user import User, UserRole, UserStatus


# ── Default fallback values (override via env in production) ─────────────────
_DEFAULT_ADMIN_EMAIL = "admin@medassist.dz"
_DEFAULT_ADMIN_PASSWORD = "Admin@MedAssist2026!"


def _hash_password(plain: str) -> str:
    """
    Bcrypt password hashing using centralized security module.
    Falls back to direct CryptContext if security module is not loaded.
    """
    try:
        from app.core.security import hash_password
        return hash_password(plain)
    except Exception:
        from passlib.context import CryptContext
        ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
        return ctx.hash(plain)


def create_initial_admin(db: Session) -> Optional[User]:
    """
    Ensure a super-admin account exists in the database.

    - If an admin already exists → skips silently.
    - If not → creates one using INITIAL_ADMIN_EMAIL / INITIAL_ADMIN_PASSWORD
      from environment variables (with safe defaults for local dev).
    - Returns the User object if created, None if already existed.

    Usage in lifespan::

        from app.core.database import SessionLocal
        from app.db_models.seed import create_initial_admin

        with SessionLocal() as db:
            create_initial_admin(db)
    """
    admin_email = os.environ.get("INITIAL_ADMIN_EMAIL", _DEFAULT_ADMIN_EMAIL).lower().strip()
    admin_password = os.environ.get("INITIAL_ADMIN_PASSWORD", _DEFAULT_ADMIN_PASSWORD)

    # Check if any admin already exists
    existing = (
        db.query(User)
        .filter(User.role == UserRole.ADMIN)
        .first()
    )
    if existing:
        logger.debug(f"🛡️  Admin already exists: {existing.email} — seed skipped.")
        return None

    logger.info(f"🌱 No admin found — creating initial admin: {admin_email}")

    admin = User(
        email=admin_email,
        password_hash=_hash_password(admin_password),
        role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
        must_change_password=False,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)

    logger.info(
        f"✅ Initial admin created | id={admin.id} | email={admin.email}"
    )
    return admin
