from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Student, User, MasteryScore, QuizAttempt, Material, MaterialChunk, Concept
from app.schemas import StudentCreate, StudentOut
from app.security import get_current_user, get_owned_student
from app.tools.mastery_tools import get_student_profile
from app.tools.progress_tools import get_progress

router = APIRouter(prefix="/students", tags=["students"])


@router.get("/", response_model=list[StudentOut])
def list_students(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """List all study sessions / topics owned by the current user."""
    return db.query(Student).filter(Student.user_id == user.id).order_by(Student.id.desc()).all()


@router.post("/", response_model=StudentOut)
def create_student(payload: StudentCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    student = Student(**payload.model_dump(), user_id=user.id)
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


@router.delete("/{student_id}")
def delete_student(student: Student = Depends(get_owned_student), db: Session = Depends(get_db)):
    """Delete a study session and all its associated materials and mastery records."""
    db.query(MasteryScore).filter(MasteryScore.student_id == student.id).delete()
    db.query(QuizAttempt).filter(QuizAttempt.student_id == student.id).delete()
    db.query(MaterialChunk).filter(MaterialChunk.student_id == student.id).delete()
    db.query(Material).filter(Material.student_id == student.id).delete()
    db.query(Concept).filter(Concept.student_id == student.id).delete()
    db.delete(student)
    db.commit()
    return {"status": "ok", "deleted_id": student.id}


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
