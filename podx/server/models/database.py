"""SQLAlchemy database models for PodX server."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


class Job(Base):
    """Job model for tracking processing tasks.

    A job represents a single processing task (transcribe, diarize, deepcast, or pipeline).
    Jobs track their status, progress, and results throughout their lifecycle.
    """

    __tablename__ = "jobs"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # Job metadata
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # queued, running, completed, failed, cancelled
    job_type: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # transcribe, diarize, deepcast, pipeline

    # Job data (stored as JSON)
    input_params: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    progress: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        """String representation of Job."""
        return f"<Job(id={self.id}, type={self.job_type}, status={self.status})>"
