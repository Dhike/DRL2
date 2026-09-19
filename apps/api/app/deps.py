import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.security import decode_access_token_claims

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    claims = decode_access_token_claims(credentials.credentials)
    if claims is None:
        raise unauthorized
    subject, issued_at = claims
    try:
        user_id = uuid.UUID(subject)
    except ValueError:
        raise unauthorized
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized
    changed_at = user.password_changed_at
    if changed_at is not None and issued_at < changed_at.replace(microsecond=0):
        raise unauthorized
    return user
