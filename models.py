from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password: Mapped[str] = mapped_column(String(255))
    is_email_verified: Mapped[bool] = mapped_column(default=False)

    otp_hash: Mapped[str | None] = mapped_column(String(64))
    otp_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    otp_attempts: Mapped[int] = mapped_column(default=0)
    otp_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class JobApplication(Base):
    __tablename__ = "job_applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    company: Mapped[str] = mapped_column(String(120))
    position: Mapped[str] = mapped_column(String(120))
    location: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(20), default="applied", index=True)
    salary_min: Mapped[float | None] = mapped_column(Float)
    salary_max: Mapped[float | None] = mapped_column(Float)
    applied_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    job_url: Mapped[str | None] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(Text)

    resume_filename: Mapped[str | None] = mapped_column(String(255))
    # deferred: the PDF bytes are only loaded when explicitly selected (download)
    resume_data: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
