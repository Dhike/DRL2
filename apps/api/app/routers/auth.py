from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import (
    LoginRequest,
    RegisterRequest,
    ResendCodeRequest,
    TokenOut,
    UserOut,
    VerifyEmailRequest,
)
from app.security import create_access_token, hash_password, verify_password
from app.verification import VerifyResult, issue_code, verify_code

router = APIRouter(prefix="/auth", tags=["auth"])

_DUMMY_HASH = hash_password("dummy-password-for-timing")


def _find_user(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.strip().lower()))


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
    issue_code(db, user)
    return user


@router.post("/verify-email", response_model=TokenOut)
def verify_email(
    payload: VerifyEmailRequest, db: Session = Depends(get_db)
) -> TokenOut:
    user = _find_user(db, payload.email)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired code")
    result = verify_code(db, user, payload.code)
    if result is VerifyResult.LOCKED:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many attempts. Request a new code.",
        )
    if result is not VerifyResult.OK:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired code")
    return TokenOut(access_token=create_access_token(str(user.id)))


@router.post("/resend-code", status_code=status.HTTP_202_ACCEPTED)
def resend_code(
    payload: ResendCodeRequest, db: Session = Depends(get_db)
) -> dict[str, str]:
    user = _find_user(db, payload.email)
    if user is not None and user.is_active and user.email_verified_at is None:
        issue_code(db, user)
    return {
        "detail": "If the account exists and is not verified, a new code has been sent."
    }


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
