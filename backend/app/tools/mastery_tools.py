"""
get_student_profile() and update_mastery() tools. These are the agent's
"read state" and "write state" primitives — every decision loop starts
with get_student_profile and ends with update_mastery.
"""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Student, MasteryScore, Concept


def get_student_profile(db: Session, student_id: int) -> dict:
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        return {}

    scores = db.query(MasteryScore).filter(MasteryScore.student_id == student_id).all()
    mastery = {s.concept_name: s.score for s in scores}

    # Concepts that exist for this subject (e.g. from an uploaded
    # material) but have no mastery record yet are "unknown", not
    # "mastered" — they must show up as weak so the agent actually
    # offers to teach newly uploaded material instead of silently
    # ignoring anything the student hasn't been quizzed on yet.
    all_concepts = db.query(Concept).filter(Concept.student_id == student_id).all()
    for concept in all_concepts:
        if concept.name not in mastery:
            mastery[concept.name] = 0.0

    return {
        "student_id": student.id,
        "name": student.name,
        "subject": student.subject,
        "goal_score": student.goal_score,
        "mastery": mastery,
        "weak_topics": [name for name, score in mastery.items() if score < 60],
    }


def update_mastery(db: Session, student_id: int, concept_name: str, new_score_delta: float) -> MasteryScore:
    """
    new_score_delta: the raw evaluation score (0-10) from evaluate_answer,
    which we fold into a running 0-100 mastery estimate. Simple exponential
    moving average — good enough for the assessment, swappable for a
    proper Bayesian/IRT model later if you want to go further.
    """
    record = (
        db.query(MasteryScore)
        .filter(MasteryScore.student_id == student_id, MasteryScore.concept_name == concept_name)
        .first()
    )
    observed = new_score_delta * 10  # 0-10 -> 0-100 scale

    if record is None:
        record = MasteryScore(
            student_id=student_id,
            concept_name=concept_name,
            score=observed,
            attempts=1,
            last_updated=datetime.utcnow(),
        )
        db.add(record)
    else:
        alpha = 0.4  # weight given to the newest attempt
        record.score = round((1 - alpha) * record.score + alpha * observed, 1)
        record.attempts += 1
        record.last_updated = datetime.utcnow()

    db.commit()
    db.refresh(record)
    return record


# ---------------------------------------------------------------------------
# Spaced revision
# ---------------------------------------------------------------------------
# A topic comes back for review after an interval that grows with how well it is known:
#   below 60% -> 1 day, 60-79% -> 2 days, 80-89% -> 4 days, 90%+ -> 7 days.
# Stateless on purpose: the due date is computed from the stored mastery score and the time it was
# last practised, so it needs no extra database columns and can be explained in one sentence.
REVIEW_BANDS = [(90, 7), (80, 4), (60, 2)]


def review_interval_days(score: float) -> int:
    for minimum, days in REVIEW_BANDS:
        if score >= minimum:
            return days
    return 1


def get_review_schedule(db: Session, student_id: int, now: datetime = None) -> list[dict]:
    """Every practised topic with when it was last practised and when it is next due."""
    now = now or datetime.utcnow()
    names = {c.name for c in db.query(Concept).filter(Concept.student_id == student_id).all()}
    out = []
    for m in db.query(MasteryScore).filter(MasteryScore.student_id == student_id).all():
        if m.concept_name not in names:
            continue
        interval = review_interval_days(m.score)
        due_at = m.last_updated + timedelta(days=interval)
        out.append({
            "concept": m.concept_name,
            "score": m.score,
            "attempts": m.attempts,
            "last_practiced": m.last_updated,
            "interval_days": interval,
            "next_review": due_at,
            "days_until_review": (due_at - now).total_seconds() / 86400,
            "days_since_practice": (now - m.last_updated).total_seconds() / 86400,
        })
    return out


def get_due_reviews(db: Session, student_id: int, now: datetime = None) -> list[dict]:
    """Topics that are known well enough (60%+) and whose review date has passed, most overdue
    first. Weak topics are not listed: the agent already prioritises those."""
    due = [t for t in get_review_schedule(db, student_id, now)
           if t["score"] >= 60 and t["days_until_review"] <= 0]
    return sorted(due, key=lambda t: t["days_until_review"])
