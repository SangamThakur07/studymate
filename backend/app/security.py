"""
Accounts and access control.

- Passwords: PBKDF2-HMAC-SHA256, random salt per user, 200,000 iterations (standard library).
  The plain password is never stored.
- Sessions: signed JWT (HS256), 7-day expiry, sent as  Authorization: Bearer <token>.
- Ownership: every student record belongs to one user; get_owned_student() refuses (404) to
  show anyone else's data, so knowing a dashboard URL is no longer enough.

Not included (be honest about it): email verification, password reset, rate limiting.
"""
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Student, User

ITERATIONS = 200_000
TOKEN_DAYS = 7
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2${ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _scheme, iters, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iters))
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def create_token(user_id: int) -> str:
    payload = {"sub": str(user_id), "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_DAYS)}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)
) -> User:
    if not creds:
        raise HTTPException(status_code=401, detail="Not signed in")
    try:
        user_id = int(jwt.decode(creds.credentials, settings.SECRET_KEY, algorithms=["HS256"])["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Session expired, please sign in again")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Account not found")
    return user


def ensure_owner(db: Session, student_id: int, user: User) -> Student:
    student = db.query(Student).filter(Student.id == student_id, Student.user_id == user.id).first()
    if not student:
        # 404 (not 403) so the existence of other people's records is not revealed
        raise HTTPException(status_code=404, detail="Student not found")
    return student


def get_owned_student(
    student_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> Student:
    return ensure_owner(db, student_id, user)
