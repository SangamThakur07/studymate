"""Everything the dashboard needs to show a student's progress and revision schedule."""
import math
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Concept, QuizAttempt
from app.tools.mastery_tools import get_review_schedule


def get_progress(db: Session, student_id: int, now: datetime = None) -> dict:
    now = now or datetime.utcnow()
    schedule = {t["concept"]: t for t in get_review_schedule(db, student_id, now)}
    concepts = db.query(Concept).filter(Concept.student_id == student_id).order_by(Concept.id).all()

    topics = []
    for c in concepts:
        t = schedule.get(c.name)
        if t is None:
            topics.append({"name": c.name, "score": 0, "attempts": 0, "status": "new",
                           "days_since_practice": None, "review_in_days": None})
            continue
        if t["score"] < 60:
            status = "weak"
        elif t["days_until_review"] <= 0:
            status = "due"
        else:
            status = "scheduled"
        topics.append({
            "name": c.name,
            "score": round(t["score"], 1),
            "attempts": t["attempts"],
            "status": status,
            "days_since_practice": math.floor(t["days_since_practice"]),
            "review_in_days": max(0, math.ceil(t["days_until_review"])) if status == "scheduled" else 0,
        })

    scored = [t for t in topics if t["status"] != "new"]
    summary = {
        "total": len(topics),
        "new": sum(t["status"] == "new" for t in topics),
        "weak": sum(t["status"] == "weak" for t in topics),
        "due": sum(t["status"] == "due" for t in topics),
        "strong": sum(t["score"] >= 80 for t in topics),
        "average_mastery": round(sum(t["score"] for t in scored) / len(scored), 1) if scored else 0,
    }

    attempts = (db.query(QuizAttempt).filter(QuizAttempt.student_id == student_id)
                .order_by(QuizAttempt.created_at.desc()).limit(8).all())
    recent = [{
        "concept": a.concept_name,
        "question": (a.question[:90] + "...") if len(a.question) > 90 else a.question,
        "correct": (a.score or 0) >= 6,
        "when": a.created_at.isoformat() if a.created_at else None,
    } for a in attempts]
    return {"summary": summary, "topics": topics, "recent": recent}
