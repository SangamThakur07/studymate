"""
evaluate_answer() tool.

This is the module you'll want to walk an examiner through line by line:
preprocessing -> embeddings -> cosine similarity -> LLM-refined feedback.
Semantic similarity is computed with sentence-transformers so scoring is
based on meaning, not exact keyword overlap.
"""
import re
from functools import lru_cache

from app.services.llm_service import llm_service

_embedding_model_load_failed = False


@lru_cache(maxsize=1)
def _get_embedding_model():
    # Loaded lazily + cached: importing sentence-transformers at module
    # import time would slow down every API startup, even for routes
    # that never need it.
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("all-MiniLM-L6-v2")


def _lexical_similarity_fallback(text_a: str, text_b: str) -> float:
    """
    Jaccard token overlap. Only used if the embedding model can't be
    loaded (e.g. no internet to download it on first run, or the
    dependency isn't installed yet) so the pipeline degrades instead of
    crashing. NOT a substitute for real semantic similarity — swap back
    to the embedding path once the model is available.
    """
    def tokenize(t):
        return set(re.findall(r"[a-z0-9]+", t.lower()))

    tokens_a, tokens_b = tokenize(text_a), tokenize(text_b)
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def semantic_similarity(text_a: str, text_b: str) -> float:
    """Cosine similarity between two texts' sentence embeddings, 0-1.
    Falls back to lexical overlap if the embedding model is unavailable."""
    global _embedding_model_load_failed

    if _embedding_model_load_failed:
        return _lexical_similarity_fallback(text_a, text_b)

    try:
        from sklearn.metrics.pairwise import cosine_similarity

        model = _get_embedding_model()
        emb = model.encode([text_a, text_b])
        sim = cosine_similarity([emb[0]], [emb[1]])[0][0]
        return float(sim)
    except Exception:
        # Covers: no internet to download the model, missing dependency,
        # or any runtime error in the embedding path.
        _embedding_model_load_failed = True
        return _lexical_similarity_fallback(text_a, text_b)


# Raw cosine similarity between a short answer and a reference sentence is crowded into a narrow
# band (unrelated ~0.0, same-topic but vague ~0.6, good ~0.8+), so "similarity x 10" overrates
# vague answers. Rescale so below SIM_LOW scores 0 and SIM_HIGH or above scores 10.
# The constants were set from a 7-topic evaluation (eval/run_eval.py): treat as a starting
# point and re-check against more examples.
SIM_LOW, SIM_HIGH = 0.45, 0.85


def similarity_to_score(sim: float) -> float:
    return round(max(0.0, min(1.0, (sim - SIM_LOW) / (SIM_HIGH - SIM_LOW))) * 10, 1)


MIN_CONTENT_WORDS = 4   # an answer needs at least this many meaningful words besides the topic name


def answer_substance(answer: str, concept_name: str) -> int:
    """Number of meaningful words in the answer, ignoring stop words and the topic's own name
    (repeating the topic name is not evidence of understanding)."""
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS as STOP
    topic = set(re.findall(r"[a-z]+", concept_name.lower()))
    words = re.findall(r"[a-z]+", answer.lower())
    return len({w for w in words if len(w) > 2 and w not in STOP and w not in topic})


COPY_JACCARD = 0.85    # word overlap at or above this = the answer is the notes' sentence, not the student's own


def is_copy(answer: str, reference: str) -> bool:
    a, r = set(re.findall(r"[a-z]+", answer.lower())), set(re.findall(r"[a-z]+", reference.lower()))
    return bool(a and r) and len(a & r) / len(a | r) >= COPY_JACCARD


MIN_COVERAGE = 0.15  # share of the notes' key terms an answer must mention to count as correct


def _content_words(text: str, concept_name: str) -> list[str]:
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS as STOP
    topic = set(re.findall(r"[a-z]+", concept_name.lower()))
    out, seen = [], set()
    for w in re.findall(r"[a-z]+", text.lower()):
        if len(w) > 3 and w not in STOP and w not in topic and w[:5] not in seen:
            seen.add(w[:5])
            out.append(w)
    return out


def key_term_coverage(answer: str, reference: str, concept_name: str):
    """Which key terms from the student's own notes does the answer mention?
    Similarity measures topical closeness, not whether specific ideas are present, so this
    is a second, independent check. Words are matched on a crude 5-letter stem
    ('splits' / 'splitting')."""
    ref_terms = _content_words(reference, concept_name)
    ans_stems = {w[:5] for w in _content_words(answer, concept_name)}
    covered = [w for w in ref_terms if w[:5] in ans_stems]
    missing = [w for w in ref_terms if w[:5] not in ans_stems]
    frac = len(covered) / len(ref_terms) if ref_terms else 1.0
    return frac, covered, missing


def _as_list(reference) -> list[str]:
    return [r for r in (reference if isinstance(reference, list) else [reference]) if r]


def finalize_score(similarity: float, answer: str, concept_name: str, reference=""):
    """similarity -> (0-10 score, note). Capped below the pass mark when the answer is too
    brief, or when it mentions too few of the key terms of the reference sentence it most
    resembles. Pass that sentence as `reference` (a list is accepted: best coverage is used)."""
    score = round(similarity * 10, 1) if _embedding_model_load_failed else similarity_to_score(similarity)
    refs, note = _as_list(reference), None
    if answer_substance(answer, concept_name) < MIN_CONTENT_WORDS:
        note = "too_brief"
    elif any(is_copy(answer, r) for r in refs):
        note = "copied"
    elif refs and max(key_term_coverage(answer, r, concept_name)[0] for r in refs) < MIN_COVERAGE:
        note = "missing_key_ideas"
    if note:
        score = min(score, 5.0)
    return score, note


def evaluate_mcq_answer(selected_option: str, correct_answer: str) -> dict:
    """MCQ scoring is exact-match, kept separate from semantic free-text scoring."""
    ok = selected_option.strip() == correct_answer.strip()
    return {
        "score": 10.0 if ok else 0.0,
        "is_correct": ok,
        "feedback": "Correct!" if ok else f"Not quite. The correct answer was: {correct_answer}",
        "covered_points": [], "missing_points": [], "misconception": None,
    }


def evaluate_answer(student_answer: str, reference_answer, concept_name: str) -> dict:
    """
    Scores a free-text answer against the student's own notes.

    reference_answer: one sentence or a list of candidate sentences from the notes. The answer is
    compared with each and the best match is used, so it doesn't matter which sentence about the
    topic happens to come first in the document.
    """
    refs = _as_list(reference_answer) or [f"A correct, complete explanation of {concept_name}."]
    sims = [semantic_similarity(student_answer, r) for r in refs]
    best = max(range(len(refs)), key=lambda i: sims[i])
    similarity, best_ref = sims[best], refs[best]

    score, note = finalize_score(similarity, student_answer, concept_name, best_ref)
    _frac, covered, missing = key_term_coverage(student_answer, best_ref, concept_name)

    if note == "too_brief":
        verdict = "Your answer is too short to show understanding. Add more detail."
    elif note == "copied":
        verdict = "This is copied from your notes. Put it in your own words."
    elif note == "missing_key_ideas":
        verdict = "Your answer doesn't mention the key ideas from your notes."
    elif score >= 8:
        verdict = "Strong answer."
    elif score >= 6:
        verdict = "Good, but you can be more complete."
    else:
        verdict = "Not quite."
    feedback = verdict
    if missing and score < 9:
        feedback += "\nKey ideas from your notes to include: " + ", ".join(missing[:4]) + "."
    feedback += f"\n(Notes say: \u201c{best_ref}\u201d)"

    from app.config import settings
    if settings.LLM_PROVIDER != "mock":     # a real LLM adds a written explanation on top
        prompt = (f"Concept: {concept_name}\nReference: {best_ref}\nStudent answer: {student_answer}\n"
                  f"Similarity: {similarity:.2f}\nGive brief feedback: what is right, what is missing, any misconception.")
        feedback += "\n\n" + llm_service.complete(prompt, system="You are evaluating a student's answer.")

    return {
        "score": score,
        "covered_points": covered,
        "missing_points": missing,
        "misconception": None,
        "feedback": feedback,
        "raw_similarity": similarity,
    }
