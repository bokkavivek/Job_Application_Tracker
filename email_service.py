import asyncio
import logging
import smtplib
from email.message import EmailMessage

from config import settings

logger = logging.getLogger("job_tracker")


def _send_sync(to: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)


def smtp_configured() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD)


async def send_otp_email(to: str, otp: str) -> bool:
    """Returns True if a real email was sent."""
    if not smtp_configured():
        logger.warning("SMTP not configured - OTP for %s is %s (dev only)", to, otp)
        return False
    body = (
        f"Your Job Application Tracker verification code is {otp}.\n"
        f"It expires in {settings.OTP_EXPIRE_MINUTES} minutes."
    )
    await asyncio.to_thread(_send_sync, to, "Your verification code", body)
    return True
