import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Query, Request, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession

import crud
import database
from config import settings
from database import get_session
from models import User
from schemas import (
    JobApplicationCreate,
    JobApplicationUpdate,
    LoginRequest,
    OtpRequest,
    SignupRequest,
    StatusUpdateRequest,
    TokenResponse,
    VerifyOtpRequest,
)
from security import get_current_user

logger = logging.getLogger("job_tracker")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await database.init_db()
    except Exception as exc:  # keep the API bootable; DB errors surface per request
        logger.error("Could not initialise the database: %s", exc)
    yield


app = FastAPI(
    title="Job Application Tracker",
    description="Track job applications, statuses and resumes. FastAPI + PostgreSQL.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- error mapping ----------
@app.exception_handler(crud.BadRequestError)
async def bad_request_handler(_: Request, exc: crud.BadRequestError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(crud.NotFoundError)
async def not_found_handler(_: Request, exc: crud.NotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(crud.EmailNotVerifiedError)
async def not_verified_handler(_: Request, exc: crud.EmailNotVerifiedError):
    return JSONResponse(status_code=403, content={"detail": str(exc)})


# ---------- meta ----------
@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse("/app/")


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok"}


# ---------- auth ----------
@app.post("/auth/signup", status_code=status.HTTP_201_CREATED, tags=["auth"])
async def signup_api(payload: SignupRequest, session: AsyncSession = Depends(get_session)):
    return await crud.signup_user(session, payload.name, payload.email, payload.password)


@app.post("/auth/send-otp", tags=["auth"])
async def send_otp_api(payload: OtpRequest, session: AsyncSession = Depends(get_session)):
    return await crud.generate_otp(session, payload.email)


@app.post("/auth/verify-otp", tags=["auth"])
async def verify_otp_api(payload: VerifyOtpRequest, session: AsyncSession = Depends(get_session)):
    return await crud.verify_otp(session, payload.email, payload.otp)


@app.post("/auth/login", response_model=TokenResponse, tags=["auth"])
async def login_api(payload: LoginRequest, session: AsyncSession = Depends(get_session)):
    return await crud.login_user(session, payload.email, payload.password)


@app.get("/auth/me", tags=["auth"])
async def me_api(user: User = Depends(get_current_user)):
    return {"id": str(user.id), "name": user.name, "email": user.email}


# ---------- job applications (all routes require a valid JWT) ----------
@app.post("/applications", status_code=status.HTTP_201_CREATED, tags=["applications"])
async def create_application_api(
    payload: JobApplicationCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await crud.create_job_application(session, user.id, payload.model_dump())


@app.get("/applications", tags=["applications"])
async def list_applications_api(
    status_filter: str | None = Query(default=None, alias="status", pattern="^(applied|interviewing|offered|rejected)$"),
    search: str | None = Query(default=None, max_length=100),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await crud.list_job_applications(session, user.id, status_filter, search, skip, limit)


# NOTE: must be declared before /applications/{app_id}
@app.get("/applications/stats", tags=["applications"])
async def stats_api(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    return await crud.get_stats(session, user.id)


@app.get("/applications/{app_id}", tags=["applications"])
async def get_application_api(
    app_id: int, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    return await crud.get_job_application(session, user.id, app_id)


@app.put("/applications/{app_id}", tags=["applications"])
async def update_application_api(
    app_id: int,
    payload: JobApplicationUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await crud.update_job_application(session, user.id, app_id, payload.model_dump(exclude_unset=True))


@app.patch("/applications/{app_id}/status", tags=["applications"])
async def update_status_api(
    app_id: int,
    payload: StatusUpdateRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await crud.update_job_application(session, user.id, app_id, {"status": payload.status})


@app.delete("/applications/{app_id}", tags=["applications"])
async def delete_application_api(
    app_id: int, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    return await crud.delete_job_application(session, user.id, app_id)


@app.post("/applications/{app_id}/resume", tags=["resume"])
async def upload_resume_api(
    app_id: int,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await crud.upload_resume(session, user.id, app_id, file)


@app.get("/applications/{app_id}/resume", tags=["resume"])
async def download_resume_api(
    app_id: int, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    data, filename = await crud.download_resume(session, user.id, app_id)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------- frontend (served by the same server -> no CORS issues) ----------
_frontend = Path(__file__).parent / "frontend"
if _frontend.is_dir():
    app.mount("/app", StaticFiles(directory=_frontend, html=True), name="frontend")
