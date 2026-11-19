from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Student, User
from app.schemas import StudentCreate, StudentOut
from app.security import get_current_user, get_owned_student
from app.tools.mastery_tools import get_student_profile
from app.tools.progress_tools import get_progress

router = APIRouter(prefix="/students", tags=["students"])


@router.post("/", response_model=StudentOut)
def create_student(payload: StudentCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    student = Student(**payload.model_dump(), user_id=user.id)
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


@router.get("/{student_id}", response_model=StudentOut)
def get_student(student: Student = Depends(get_owned_student)):
    return student


@router.get("/{student_id}/profile")
def get_profile(student: Student = Depends(get_owned_student), db: Session = Depends(get_db)):
    return get_student_profile(db, student.id)


@router.get("/{student_id}/progress")
def progress(student: Student = Depends(get_owned_student), db: Session = Depends(get_db)):
    """Per-topic status, the revision schedule and recent activity."""
    return get_progress(db, student.id)
