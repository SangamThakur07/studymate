"""
The Agent. This is the module to walk an interviewer through line by
line — it's the whole "agentic" story in one file.

Loop: PERCEIVE (read student state) -> DECIDE (pick next action from
weak topics + prerequisite graph) -> ACT (call the relevant tool) ->
LOG (record the decision so it's auditable).

Deliberately NOT using a framework (LangChain/LangGraph) for this core
loop — a hand-rolled loop is trivial to explain in a viva ("here is
every decision point"), whereas "the framework decided" is a much
weaker answer under questioning. You can swap in LangGraph later once
the logic is proven, if you want the framework on your CV too.
"""
from sqlalchemy.orm import Session

from app.models import AgentActionLog, Material, QuizAttempt
from app.tools.mastery_tools import get_student_profile, update_mastery, get_due_reviews, get_review_schedule
from app.tools.knowledge_tools import generate_quiz, search_knowledge, explain_concept
from app.tools.evaluation_tools import evaluate_answer, evaluate_mcq_answer
from app.tools.planner_tools import create_study_plan
from app.services.knowledge_graph import get_prerequisite_map
from app.tools.rag_tools import retrieve
from app.tools.mcq_tools import find_concept_fragments, generate_mcq_set, generate_written_set


def _log_action(db: Session, student_id: int, tool: str, reasoning: str, input_summary: str, output_summary: str):
    entry = AgentActionLog(
        student_id=student_id,
        tool_called=tool,
        reasoning=reasoning,
        input_summary=input_summary[:500],
        output_summary=output_summary[:500],
    )
    db.add(entry)
    db.commit()


def _get_material_context(db: Session, student_id: int) -> str:
    """All of the student's uploaded material, oldest first (capped), so the agent's own
    tools ground questions in what the student actually uploaded."""
    mats = (db.query(Material).filter(Material.student_id == student_id)
            .order_by(Material.uploaded_at.asc()).all())
    return "\n".join(m.raw_text or "" for m in mats)[:60000]


def _retrieve_context(db: Session, student_id: int, concept: str):
    """RAG step: fetch the passages of the student's own material most relevant
    to this concept. Returns (context_text, sources)."""
    sources = retrieve(db, student_id, concept, k=3)
    if sources:
        return "\n\n".join(s["text"] for s in sources), sources
    return search_knowledge(concept, _get_material_context(db, student_id)), []


def decide_next_action(db: Session, student_id: int) -> dict:
    """
    The core decision point. Given the student's current state, decide
    what the agent should do next: intervene on a weak prerequisite,
    quiz a topic that's nearly mastered, or advance to new material.

    This is intentionally rule-based reasoning over real state (not an
    LLM free-associating) — the reasoning is fully inspectable, which
    matters a lot when you're defending "autonomous decision-making" to
    an examiner.
    """
    profile = get_student_profile(db, student_id)
    if not profile:
        return {"error": "student not found"}

    prereq_map = get_prerequisite_map(db, student_id)
    plan = create_study_plan(profile, prereq_map)

    due = get_due_reviews(db, student_id) if not plan else []
    if not plan and due:
        top = due[0]
        ago = max(1, round(top["days_since_practice"]))
        decision = {
            "action": "review",
            "concept": top["concept"],
            "reasoning": (f"'{top['concept']}' is at {top['score']:.0f}% but was last practised {ago} day(s) ago. "
                          f"At this level it is reviewed every {top['interval_days']} day(s), so it is due for review."),
        }
    elif not plan:
        upcoming = [t for t in get_review_schedule(db, student_id) if t["days_until_review"] > 0]
        hint = ""
        if upcoming:
            nxt = min(upcoming, key=lambda t: t["days_until_review"])
            hint = f" Next review: '{nxt['concept']}' in {max(1, round(nxt['days_until_review']))} day(s)."
        decision = {
            "action": "advance",
            "concept": None,
            "reasoning": "No weak topics and nothing due for review." + hint,
        }
    else:
        top = plan[0]
        decision = {
            "action": "intervene",
            "concept": top["concept"],
            "reasoning": top["reason"],
        }

    _log_action(
        db, student_id,
        tool="decide_next_action",
        reasoning=decision["reasoning"],
        input_summary=f"mastery={profile.get('mastery')}",
        output_summary=str(decision),
    )
    return decision


def explain_topic(db: Session, student_id: int) -> dict:
    """Step 1 of a session: decide what to focus on, then explain it simply from the student's material."""
    decision = decide_next_action(db, student_id)
    if decision.get("error"):
        return decision
    concept = decision["concept"] or "general review"
    context, sources = _retrieve_context(db, student_id, concept)
    explanation = explain_concept(concept, context)
    _log_action(db, student_id, tool="explain_topic",
                reasoning=f"Retrieved {len(sources)} passages from student's material, then explaining '{concept}' ({decision['action']})",
                input_summary=concept, output_summary=explanation[:200])
    return {"decision": decision, "context_snippet": context, "sources": sources, "explanation": explanation}


def run_teaching_cycle(db: Session, student_id: int, question_type: str = "open") -> dict:
    """Step 2: generate the quiz in the format the student chose (open or mcq)."""
    decision = decide_next_action(db, student_id)
    if decision.get("error"):
        return decision
    concept = decision["concept"] or "general review"
    context, sources = _retrieve_context(db, student_id, concept)
    pool = list(get_student_profile(db, student_id).get("mastery", {}).keys())
    quiz = generate_quiz(concept, difficulty="medium", question_type=question_type,
                         context=context, distractors=pool)
    _log_action(db, student_id, tool="run_teaching_cycle",
                reasoning=f"Quizzing '{concept}', question_type={question_type}",
                input_summary=concept, output_summary=quiz["question"])
    return {"decision": decision, "context_snippet": context, "sources": sources, "quiz": quiz}


def run_test(db: Session, student_id: int, question_type: str = "mcq", n: int = 5) -> dict:
    """Step 2: build a multi-question test on the topic the agent chose.
    MCQ -> up to n questions; written -> up to 4 (define / compare / explain / why). When the topic's own
    notes cannot fill the test, it is topped up with review questions on related topics."""
    decision = decide_next_action(db, student_id)
    if decision.get("error"):
        return decision
    concept = decision["concept"] or "general review"
    profile = get_student_profile(db, student_id)
    pool = list(profile.get("mastery", {}).keys())
    all_text = _get_material_context(db, student_id)
    context, sources = _retrieve_context(db, student_id, concept)

    # Questions this student has already answered: never repeat them while fresh ones exist.
    asked = {a.question for a in db.query(QuizAttempt).filter(QuizAttempt.student_id == student_id).all()}
    target = n if question_type == "mcq" else min(n, 4)

    def make(topic, k, exclude):
        """Fresh questions about one topic, in the format the student chose."""
        if question_type == "mcq":
            return generate_mcq_set(topic, all_text, pool, n=k, exclude=exclude)
        return generate_written_set(topic, all_text, pool, n=k, exclude=exclude)

    def tag(q, topic, review=False):
        q.update({"concept_name": topic, "question_type": question_type, "difficulty": "medium"})
        if review:
            q["review"] = True
        return q

    questions = [tag(q, concept) for q in make(concept, target, asked)]

    if len(questions) < target:
        # Not enough fresh material on this one topic: top up with review questions on related
        # topics (prerequisites first), so a test is never a single question.
        seen = {q["question"] for q in questions} | asked
        prereqs = get_prerequisite_map(db, student_id).get(concept, [])
        others = [c for c in prereqs if c in pool] + [c for c in pool if c != concept and c not in prereqs]
        for _round in range(3):
            for other in others:
                if len(questions) >= target:
                    break
                for q in make(other, 3, seen):
                    seen.add(q["question"])
                    questions.append(tag(q, other, review=True))
                    break

    if not questions:   # everything has been asked before: allow repeats rather than returning nothing
        questions = [tag(q, concept) for q in make(concept, target, None)]
    if not questions:   # nothing usable in the notes
        questions = [generate_quiz(concept, difficulty="medium", question_type=question_type,
                                   context=context, distractors=pool)]

    _log_action(db, student_id, tool="run_test",
                reasoning=f"Built {len(questions)}-question {question_type} test on '{concept}'",
                input_summary=concept, output_summary=questions[0]["question"])
    return {"decision": decision, "sources": sources, "questions": questions}


def submit_answer(db: Session, student_id: int, concept_name: str, question: str,
                  question_type: str = "open", student_answer: str = "",
                  selected_option: str = "", correct_answer: str = "",
                  reference_answer: str = "") -> dict:
    """Evaluate (exact match for MCQ, semantic similarity for open text), update mastery, log."""
    if question_type == "mcq":
        evaluation = evaluate_mcq_answer(selected_option, correct_answer)
    else:
        # Grade against the student's OWN notes: best defining sentence for the concept.
        reference = reference_answer
        if not reference:
            refs = find_concept_fragments(concept_name, _get_material_context(db, student_id), strict=True)[:3]
            if not refs:
                srcs = retrieve(db, student_id, concept_name, k=1)
                refs = [srcs[0]["text"]] if srcs else [f"A correct, complete explanation of {concept_name}."]
            reference = refs
        evaluation = evaluate_answer(student_answer, reference, concept_name)
    updated = update_mastery(db, student_id, concept_name, evaluation["score"])
    db.add(QuizAttempt(student_id=student_id, concept_name=concept_name, question=question,
                       student_answer=selected_option if question_type == "mcq" else student_answer,
                       score=evaluation["score"], feedback=str(evaluation.get("feedback", ""))[:500]))
    db.commit()
    _log_action(db, student_id, tool="submit_answer",
                reasoning=f"Evaluated {question_type} answer for '{concept_name}', score {evaluation['score']}/10",
                input_summary=selected_option if question_type == "mcq" else student_answer,
                output_summary=f"new_mastery={updated.score}")
    return {"evaluation": evaluation, "updated_mastery": updated.score, "concept_name": concept_name}
