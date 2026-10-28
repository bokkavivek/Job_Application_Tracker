import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from email_service import send_otp_email
from models import JobApplication, User
from security import (
    create_access_token,
    hash_otp,
    hash_password,
    otp_matches,
    utc_now,
    verify_password,
)

STATUSES = ("applied", "interviewing", "offered", "rejected")
OTP_COOLDOWN_SECONDS = 30


class BadRequestError(Exception):
    """Maps to HTTP 400."""


class NotFoundError(Exception):
    """Maps to HTTP 404."""


class EmailNotVerifiedError(Exception):
    """Maps to HTTP 403."""


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _public_user(user: User) -> dict:
    return {"id": str(user.id), "name": user.name, "email": user.email}


async def _user_by_email(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(select(User).where(User.email == email.lower()))


# ======================= AUTH =======================
async def signup_user(session: AsyncSession, name: str, email: str, password: str) -> dict:
    if await _user_by_email(session, email):
        raise BadRequestError("User with this email already exists.")
    session.add(User(name=name.strip(), email=email.lower(), password=hash_password(password)))
    try:
        await session.commit()
    except IntegrityError:  # two signups racing for the same email
        await session.rollback()
        raise BadRequestError("User with this email already exists.")
    return {"message": "User created successfully. Please verify your email with the OTP."}


async def generate_otp(session: AsyncSession, email: str) -> dict:
    user = await _user_by_email(session, email)
    if not user:
        raise NotFoundError("User not found.")
    if user.is_email_verified:
        raise BadRequestError("Email is already verified.")
    if user.otp_sent_at and (utc_now() - _aware(user.otp_sent_at)).total_seconds() < OTP_COOLDOWN_SECONDS:
        raise BadRequestError(f"Please wait {OTP_COOLDOWN_SECONDS} seconds before requesting a new OTP.")

    otp = f"{secrets.randbelow(900000) + 100000}"  # cryptographically secure 6 digits
    now = utc_now()
    user.otp_hash = hash_otp(user.email, otp)
    user.otp_expires_at = now + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)
    user.otp_attempts = 0
    user.otp_sent_at = now
    await session.commit()

    emailed = await send_otp_email(user.email, otp)
    response = {"message": "OTP sent to your email." if emailed else "OTP generated."}
    if not emailed and settings.DEV_MODE:
        response["dev_otp"] = otp  # local demos only - never enable DEV_MODE in production
    return response


async def verify_otp(session: AsyncSession, email: str, otp: str) -> dict:
    user = await _user_by_email(session, email)
    if not user or not user.otp_hash or not user.otp_expires_at:
        raise BadRequestError("Invalid OTP.")
    if user.otp_attempts >= settings.OTP_MAX_ATTEMPTS:
        raise BadRequestError("Too many attempts. Please request a new OTP.")
    if _aware(user.otp_expires_at) < utc_now():
        raise BadRequestError("OTP has expired. Please request a new one.")
    if not otp_matches(user.email, otp, user.otp_hash):
        user.otp_attempts += 1
        await session.commit()
        raise BadRequestError("Invalid OTP.")

    user.is_email_verified = True
    user.otp_hash = None
    user.otp_expires_at = None
    user.otp_sent_at = None
    user.otp_attempts = 0
    user.updated_at = utc_now()
    await session.commit()
    return {"message": "Email verified successfully."}


async def login_user(session: AsyncSession, email: str, password: str) -> dict:
    user = await _user_by_email(session, email)
    if not user or not verify_password(password, user.password):
        raise BadRequestError("Invalid email or password.")
    if not user.is_email_verified:
        raise EmailNotVerifiedError("Email not verified.")
    return {
        "access_token": create_access_token(user.id),
        "token_type": "bearer",
        "user": _public_user(user),
    }


# ======================= JOB APPLICATIONS =======================
def serialize_application(a: JobApplication) -> dict:
    has_salary = a.salary_min is not None or a.salary_max is not None
    return {
        "id": str(a.id),
        "company": a.company,
        "position": a.position,
        "location": a.location or "",
        "status": a.status,
        "salary_range": {"min": a.salary_min, "max": a.salary_max} if has_salary else None,
        "applied_date": a.applied_date,
        "job_url": a.job_url,
        "notes": a.notes,
        "has_resume": a.resume_filename is not None,
        "resume_filename": a.resume_filename,
        "created_at": a.created_at,
        "updated_at": a.updated_at,
    }


async def _get_owned(session: AsyncSession, user_id: int, app_id: int) -> JobApplication:
    app = await session.scalar(
        select(JobApplication).where(JobApplication.id == app_id, JobApplication.user_id == user_id)
    )
    if not app:
        raise NotFoundError("Job application not found.")
    return app


async def create_job_application(session: AsyncSession, user_id: int, data: dict) -> dict:
    salary = data.get("salary_range") or {}
    now = utc_now()
    app = JobApplication(
        user_id=user_id,
        company=data["company"].strip(),
        position=data["position"].strip(),
        location=data.get("location") or "",
        status=data.get("status", "applied"),
        salary_min=salary.get("min"),
        salary_max=salary.get("max"),
        applied_date=data.get("applied_date") or now,
        job_url=data.get("job_url"),
        notes=data.get("notes"),
        created_at=now,
        updated_at=now,
    )
    session.add(app)
    await session.commit()
    return serialize_application(app)


async def list_job_applications(
    session: AsyncSession,
    user_id: int,
    status: str | None = None,
    search: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> dict:
    stmt = select(JobApplication).where(JobApplication.user_id == user_id)
    if status:
        stmt = stmt.where(JobApplication.status == status)
    if search and search.strip():
        escaped = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{escaped}%"
        stmt = stmt.where(
            or_(
                JobApplication.company.ilike(like, escape="\\"),
                JobApplication.position.ilike(like, escape="\\"),
            )
        )
    total = await session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = await session.scalars(
        stmt.order_by(JobApplication.created_at.desc(), JobApplication.id.desc()).offset(skip).limit(limit)
    )
    return {"items": [serialize_application(a) for a in rows.all()], "total": total or 0}


async def get_job_application(session: AsyncSession, user_id: int, app_id: int) -> dict:
    return serialize_application(await _get_owned(session, user_id, app_id))


async def update_job_application(session: AsyncSession, user_id: int, app_id: int, changes: dict) -> dict:
    app = await _get_owned(session, user_id, app_id)
    if "salary_range" in changes:
        salary = changes.pop("salary_range") or {}
        changes["salary_min"] = salary.get("min")
        changes["salary_max"] = salary.get("max")
    allowed = {"company", "position", "location", "status", "salary_min", "salary_max",
               "applied_date", "job_url", "notes"}
    not_nullable = {"company", "position", "status"}
    changes = {k: v for k, v in changes.items() if k in allowed and not (k in not_nullable and v is None)}
    if not changes:
        raise BadRequestError("No fields to update.")
    for key, value in changes.items():
        setattr(app, key, value)
    app.updated_at = utc_now()
    await session.commit()
    return serialize_application(app)


async def delete_job_application(session: AsyncSession, user_id: int, app_id: int) -> dict:
    app = await _get_owned(session, user_id, app_id)
    await session.delete(app)
    await session.commit()
    return {"message": "Job application deleted."}


async def get_stats(session: AsyncSession, user_id: int) -> dict:
    rows = await session.execute(
        select(JobApplication.status, func.count())
        .where(JobApplication.user_id == user_id)
        .group_by(JobApplication.status)
    )
    by_status = {s: 0 for s in STATUSES}
    for status, count in rows.all():
        by_status[status] = count
    total = sum(by_status.values())
    return {
        "total": total,
        "by_status": by_status,
        "active": by_status["applied"] + by_status["interviewing"],
        "offer_rate": round(by_status["offered"] * 100 / total, 1) if total else 0.0,
    }


# ======================= RESUME (stored in PostgreSQL as bytea) =======================
async def upload_resume(session: AsyncSession, user_id: int, app_id: int, file: UploadFile) -> dict:
    app = await _get_owned(session, user_id, app_id)
    if file.content_type != "application/pdf":
        raise BadRequestError("Only PDF files are allowed.")
    content = await file.read()
    if len(content) > settings.MAX_RESUME_MB * 1024 * 1024:
        raise BadRequestError(f"File size must be less than {settings.MAX_RESUME_MB} MB.")
    if not content.startswith(b"%PDF"):
        raise BadRequestError("File is not a valid PDF.")

    app.resume_filename = os.path.basename(file.filename or "") or "resume.pdf"
    app.resume_data = content  # replaces any previous upload
    app.updated_at = utc_now()
    await session.commit()
    return serialize_application(app)


async def download_resume(session: AsyncSession, user_id: int, app_id: int) -> tuple[bytes, str]:
    app = await _get_owned(session, user_id, app_id)
    if not app.resume_filename:
        raise NotFoundError("No resume uploaded for this application.")
    data = await session.scalar(select(JobApplication.resume_data).where(JobApplication.id == app_id))
    if not data:
        raise NotFoundError("No resume uploaded for this application.")
    return data, app.resume_filename
