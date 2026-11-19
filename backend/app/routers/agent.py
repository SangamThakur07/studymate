from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Student, User
from app.schemas import AnswerSubmit
from app.security import ensure_owner, get_current_user, get_owned_student
from app.services.agent_service import (decide_next_action, explain_topic, run_teaching_cycle,
                                        run_test, submit_answer)

router = APIRouter(prefix="/agent", tags=["agent"])


@router.get("/{student_id}/next-action")
def next_action(student: Student = Depends(get_owned_student), db: Session = Depends(get_db)):
    """The agent's decision for this student, with its reasoning."""
    return decide_next_action(db, student.id)


@router.post("/{student_id}/explain")
def explain(student: Student = Depends(get_owned_student), db: Session = Depends(get_db)):
    """Step 1 of a session: agent picks a topic and explains it simply."""
    return explain_topic(db, student.id)


@router.post("/{student_id}/teach")
def teach(question_type: str = "open", student: Student = Depends(get_owned_student), db: Session = Depends(get_db)):
    """Single quiz question ("mcq" or "open")."""
    return run_teaching_cycle(db, student.id, question_type=question_type)


@router.post("/{student_id}/test")
def test(question_type: str = "mcq", n: int = 5, student: Student = Depends(get_owned_student),
         db: Session = Depends(get_db)):
    """Step 2: a multi-question test ("mcq" -> up to n questions, "open" -> one)."""
    return run_test(db, student.id, question_type=question_type, n=min(max(n, 1), 10))


@router.post("/answer")
def answer(payload: AnswerSubmit, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Student submits an answer; agent evaluates and updates mastery."""
    ensure_owner(db, payload.student_id, user)
    return submit_answer(
        db,
        student_id=payload.student_id,
        concept_name=payload.concept_name,
        question=payload.question,
        question_type=payload.question_type,
        student_answer=payload.student_answer,
        selected_option=payload.selected_option,
        correct_answer=payload.correct_answer,
        reference_answer=payload.references or "",
    )
