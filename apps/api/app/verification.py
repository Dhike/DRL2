import hashlib
import hmac
import logging
import secrets
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from enum import Enum

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.mailer import send_password_reset_email, send_verification_email
from app.models import EmailVerificationCode, User

logger = logging.getLogger("drl2.verification")

PURPOSE_VERIFY_EMAIL = "verify_email"
PURPOSE_RESET_PASSWORD = "reset_password"

_SENDERS: dict[str, Callable[[str, str], None]] = {
    PURPOSE_VERIFY_EMAIL: send_verification_email,
    PURPOSE_RESET_PASSWORD: send_password_reset_email,
}

CODE_TTL = timedelta(minutes=10)
MAX_ATTEMPTS = 5
RESEND_COOLDOWN = timedelta(seconds=60)
MAX_CODES_PER_HOUR = 5


class VerifyResult(str, Enum):
    OK = "ok"
    INVALID = "invalid"
    EXPIRED = "expired"
    LOCKED = "locked"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_code(user_id: uuid.UUID, purpose: str, code: str) -> str:
    return hmac.new(
        settings.jwt_secret.encode("utf-8"),
        f"{purpose}:{user_id}:{code}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def issue_code(db: Session, user: User, purpose: str) -> bool:
    """Create a new code and email it. Returns False when rate limited."""
    now = _now()
    latest = db.scalar(
        select(EmailVerificationCode)
        .where(
            EmailVerificationCode.user_id == user.id,
            EmailVerificationCode.purpose == purpose,
        )
        .order_by(EmailVerificationCode.created_at.desc())
        .limit(1)
    )
    if latest is not None and now - latest.created_at < RESEND_COOLDOWN:
        return False
    recent = db.scalar(
        select(func.count())
        .select_from(EmailVerificationCode)
        .where(
            EmailVerificationCode.user_id == user.id,
            EmailVerificationCode.purpose == purpose,
            EmailVerificationCode.created_at > now - timedelta(hours=1),
        )
    )
    if recent is not None and recent >= MAX_CODES_PER_HOUR:
        return False

    to = user.email
    code = generate_code()
    db.execute(
        update(EmailVerificationCode)
        .where(
            EmailVerificationCode.user_id == user.id,
            EmailVerificationCode.purpose == purpose,
            EmailVerificationCode.consumed_at.is_(None),
        )
        .values(consumed_at=now)
    )
    db.add(
        EmailVerificationCode(
            user_id=user.id,
            purpose=purpose,
            code_hash=hash_code(user.id, purpose, code),
            expires_at=now + CODE_TTL,
        )
    )
    db.commit()
    try:
        _SENDERS[purpose](to, code)
    except Exception:
        logger.exception("Failed to send %s email to %s", purpose, to)
    return True


def verify_code(
    db: Session, user: User, code: str, purpose: str
) -> VerifyResult:
    """Check a code. On OK the changes are pending: the caller must commit."""
    now = _now()
    record = db.scalar(
        select(EmailVerificationCode)
        .where(
            EmailVerificationCode.user_id == user.id,
            EmailVerificationCode.purpose == purpose,
            EmailVerificationCode.consumed_at.is_(None),
        )
        .order_by(EmailVerificationCode.created_at.desc())
        .limit(1)
    )
    if record is None:
        return VerifyResult.INVALID
    if record.expires_at < now:
        return VerifyResult.EXPIRED
    if record.attempts >= MAX_ATTEMPTS:
        return VerifyResult.LOCKED
    if not hmac.compare_digest(record.code_hash, hash_code(user.id, purpose, code)):
        record.attempts += 1
        db.commit()
        return VerifyResult.INVALID
    record.consumed_at = now
    if purpose == PURPOSE_VERIFY_EMAIL:
        user.email_verified_at = now
    return VerifyResult.OK
