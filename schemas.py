from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field

Status = Literal["applied", "interviewing", "offered", "rejected"]


# ---------- auth ----------
class SignupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class OtpRequest(BaseModel):
    email: EmailStr


class VerifyOtpRequest(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


# ---------- job applications ----------
class SalaryRange(BaseModel):
    min: Optional[float] = Field(default=None, ge=0)
    max: Optional[float] = Field(default=None, ge=0)


class JobApplicationCreate(BaseModel):
    company: str = Field(min_length=1, max_length=120)
    position: str = Field(min_length=1, max_length=120)
    location: str = Field(default="", max_length=120)
    status: Status = "applied"
    salary_range: Optional[SalaryRange] = None
    applied_date: Optional[datetime] = None
    job_url: Optional[str] = Field(default=None, max_length=500)
    notes: Optional[str] = Field(default=None, max_length=2000)


class JobApplicationUpdate(BaseModel):
    company: Optional[str] = Field(default=None, min_length=1, max_length=120)
    position: Optional[str] = Field(default=None, min_length=1, max_length=120)
    location: Optional[str] = Field(default=None, max_length=120)
    status: Optional[Status] = None
    salary_range: Optional[SalaryRange] = None
    applied_date: Optional[datetime] = None
    job_url: Optional[str] = Field(default=None, max_length=500)
    notes: Optional[str] = Field(default=None, max_length=2000)


class StatusUpdateRequest(BaseModel):
    status: Status
