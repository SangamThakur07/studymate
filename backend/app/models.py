from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Text, JSON
)
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False, unique=True, index=True)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    name = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    exam_date = Column(DateTime, nullable=True)
    available_minutes_per_day = Column(Integer, default=60)
    goal_score = Column(Float, default=80.0)
    level = Column(String, default="beginner")  # beginner | intermediate | advanced
    created_at = Column(DateTime, default=datetime.utcnow)

    mastery_scores = relationship("MasteryScore", back_populates="student")
    quiz_attempts = relationship("QuizAttempt", back_populates="student")


class Concept(Base):
    __tablename__ = "concepts"

    id = Column(Integer, primary_key=True, index=True)
    # Concepts belong to ONE student's study session. Previously they were
    # shared per subject (and globally unique by name), so on a public link
    # every user studying "NLP" would have seen everyone else's topics.
    student_id = Column(Integer, ForeignKey("students.id"), index=True, nullable=True)
    name = Column(String, nullable=False, index=True)
    subject = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    # Comma-separated concept names this one depends on. Kept simple (no
    # separate edge table) since the knowledge graph is small per subject;
    # NetworkX builds the actual graph in memory from this at runtime.
    prerequisites = Column(String, default="")
    source_material_id = Column(Integer, ForeignKey("materials.id"), nullable=True)


class Material(Base):
    __tablename__ = "materials"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"))
    filename = Column(String, nullable=False)
    raw_text = Column(Text, nullable=True)
    extracted_keywords = Column(JSON, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)


class MaterialChunk(Base):
    """A retrievable passage of an uploaded material (the 'R' in RAG)."""
    __tablename__ = "material_chunks"

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), index=True)
    student_id = Column(Integer, ForeignKey("students.id"), index=True)
    chunk_index = Column(Integer, default=0)
    text = Column(Text, nullable=False)
    embedding = Column(JSON, nullable=True)  # list of floats, or null if model unavailable


class MasteryScore(Base):
    __tablename__ = "mastery_scores"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"))
    concept_name = Column(String, nullable=False, index=True)
    score = Column(Float, default=0.0)  # 0-100
    attempts = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)

    student = relationship("Student", back_populates="mastery_scores")


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"))
    concept_name = Column(String, nullable=False)
    question = Column(Text, nullable=False)
    student_answer = Column(Text, nullable=True)
    score = Column(Float, nullable=True)  # 0-10
    feedback = Column(Text, nullable=True)
    misconception = Column(Text, nullable=True)
    difficulty = Column(String, default="medium")  # easy | medium | hard
    created_at = Column(DateTime, default=datetime.utcnow)

    student = relationship("Student", back_populates="quiz_attempts")


class AgentActionLog(Base):
    """
    Records every decision the agent makes: which tool it called, why
    (reasoning), and what happened. This is what you show in the viva to
    prove the agent is actually making autonomous decisions, not following
    a fixed script.
    """
    __tablename__ = "agent_action_log"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"))
    tool_called = Column(String, nullable=False)
    reasoning = Column(Text, nullable=True)
    input_summary = Column(Text, nullable=True)
    output_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
