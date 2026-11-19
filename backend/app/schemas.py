from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel


class StudentCreate(BaseModel):
    name: str
    subject: str
    exam_date: Optional[datetime] = None
    available_minutes_per_day: int = 60
    goal_score: float = 80.0
    level: str = "beginner"


class StudentOut(StudentCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class MasteryOut(BaseModel):
    concept_name: str
    score: float
    attempts: int

    class Config:
        from_attributes = True


class AnswerSubmit(BaseModel):
    student_id: int
    concept_name: str
    question: str
    question_type: str = "open"  # "open" | "mcq"
    student_answer: str = ""
    selected_option: str = ""
    correct_answer: str = ""  # echoed back from the quiz for MCQ grading
    references: list[str] = []  # note sentences a written question is graded against


class EvaluationResult(BaseModel):
    score: float  # 0-10
    covered_points: List[str]
    missing_points: List[str]
    misconception: Optional[str] = None
    feedback: str


class AgentDecision(BaseModel):
    tool_called: str
    reasoning: str
    result: dict
