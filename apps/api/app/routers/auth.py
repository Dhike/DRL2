import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.mailer import send_password_changed_email
from app.models import User
from app.schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResendCodeRequest,
    ResetPasswordRequest,
    TokenOut,
    UserOut,
    VerifyEmailRequest,
)
from app.security import create_access_token, hash_password, verify_password
from app.verification import (
    PURPOSE_RESET_PASSWORD,
    PURPOSE_VERIFY_EMAIL,
    VerifyResult,
    issue_code,
    verify_code,
)

logger = logging.getLogger("drl2.auth")

router = APIRouter(prefix="/auth", tags=["auth"])

_DUMMY_HASH = hash_password("dummy-password-for-timing")


def _find_user(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.strip().lower()))


def _check_code_result(result: VerifyResult) -> None:
    if result is VerifyResult.LOCKED:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many attempts. Request a new code.",
        )
    if result is not VerifyResult.OK:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired code")


def _notify_password_changed(email: str) -> None:
    try:
        send_password_changed_email(email)
    except Exception:
        logger.exception("Failed to send password-changed email to %s", email)


@router.post(
    "/register", response_model=UserOut, status_code=status.HTTP_201_CREATED
)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> User:
    email = payload.email.strip().lower()
    if _find_user(db, email) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = User(email=email, password_hash=hash_password(payload.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    db.refresh(user)
    issue_code(db, user, PURPOSE_VERIFY_EMAIL)
    return user


@router.post("/verify-email", response_model=TokenOut)
def verify_email(
    payload: VerifyEmailRequest, db: Session = Depends(get_db)
) -> TokenOut:
    user = _find_user(db, payload.email)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired code")
    _check_code_result(verify_code(db, user, payload.code, PURPOSE_VERIFY_EMAIL))
    db.commit()
    return TokenOut(access_token=create_access_token(str(user.id)))


@router.post("/resend-code", status_code=status.HTTP_202_ACCEPTED)
def resend_code(
    payload: ResendCodeRequest, db: Session = Depends(get_db)
) -> dict[str, str]:
    user = _find_user(db, payload.email)
    if user is not None and user.is_active and user.email_verified_at is None:
        issue_code(db, user, PURPOSE_VERIFY_EMAIL)
    return {
        "detail": "If the account exists and is not verified, a new code has been sent."
    }


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(
    payload: ForgotPasswordRequest, db: Session = Depends(get_db)
) -> dict[str, str]:
    user = _find_user(db, payload.email)
    if user is not None and user.is_active and user.email_verified_at is not None:
        issue_code(db, user, PURPOSE_RESET_PASSWORD)
    return {
        "detail": "If an account exists for that email, a reset code has been sent."
    }


@router.post("/reset-password")
def reset_password(
    payload: ResetPasswordRequest, db: Session = Depends(get_db)
) -> dict[str, str]:
    user = _find_user(db, payload.email)
    if user is None or not user.is_active or user.email_verified_at is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired code")
    _check_code_result(verify_code(db, user, payload.code, PURPOSE_RESET_PASSWORD))
    user.password_hash = hash_password(payload.new_password)
    user.password_changed_at = datetime.now(timezone.utc)
    db.commit()
    _notify_password_changed(user.email)
    return {"detail": "Password updated. You can now sign in."}


@router.post("/change-password", response_model=TokenOut)
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TokenOut:
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Current password is incorrect"
        )
    if payload.current_password == payload.new_password:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "New password must be different from the current one",
        )
    current_user.password_hash = hash_password(payload.new_password)
    current_user.password_changed_at = datetime.now(timezone.utc)
    db.commit()
    _notify_password_changed(current_user.email)
    return TokenOut(access_token=create_access_token(str(current_user.id)))


@router.post("/login", response_model=TokenOut)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenOut:
    user = _find_user(db, payload.email)
    password_ok = verify_password(
        payload.password, user.password_hash if user else _DUMMY_HASH
    )
    if user is None or not password_ok or not user.is_active:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Invalid email or password"
        )
    if user.email_verified_at is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Email not verified")
    return TokenOut(access_token=create_access_token(str(user.id)))


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
