"""
app/core/database.py
SQLAlchemy database setup and session management for MedAssist AI V2.
"""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from app.core.config import get_settings

settings = get_settings()

# Engine creation with pool pre-ping to ensure stale connections are handled
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a transactional DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

