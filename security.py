import hashlib
import hmac
from datetime import timedelta

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

import database
from config import settings
from models import User, utc_now  # noqa: F401  (utc_now re-exported for other modules)

bearer_scheme = HTTPBearer(auto_error=False)


# ---------- passwords ----------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


# ---------- OTP ----------
def hash_otp(email: str, otp: str) -> str:
    # OTPs are never stored in plain text.
    return hashlib.sha256(f"{email.lower()}:{otp}:{settings.JWT_SECRET}".encode()).hexdigest()


def otp_matches(email: str, otp: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_otp(email, otp), stored_hash)


# ---------- JWT ----------
def create_access_token(user_id: int) -> str:
    expire = utc_now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(database.get_session),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if creds is None:
        raise unauthorized
    try:
        payload = jwt.decode(creds.credentials, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        raise unauthorized
    user = await session.get(User, user_id)
    if not user:
        raise unauthorized
    return user
