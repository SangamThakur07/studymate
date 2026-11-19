import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Student, User
from app.security import create_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class Credentials(BaseModel):
    email: str
    password: str


def _students(db: Session, user: User):
    rows = db.query(Student).filter(Student.user_id == user.id).order_by(Student.id).all()
    return [{"id": s.id, "name": s.name, "subject": s.subject} for s in rows]


@router.post("/register")
def register(c: Credentials, db: Session = Depends(get_db)):
    email = c.email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(status_code=400, detail="Please enter a valid email address")
    if len(c.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(email=email, password_hash=hash_password(c.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"access_token": create_token(user.id), "email": user.email, "students": []}


@router.post("/login")
def login(c: Credentials, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == c.email.strip().lower()).first()
    if not user or not verify_password(c.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return {"access_token": create_token(user.id), "email": user.email, "students": _students(db, user)}


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"email": user.email, "students": _students(db, user)}
