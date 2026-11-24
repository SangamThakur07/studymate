"""
search_knowledge() and generate_quiz() tools, plus material NLP
preprocessing (concept/keyword extraction from uploaded notes).
"""
import json
import re
from functools import lru_cache

from app.services.llm_service import llm_service

_keybert_load_failed = False


@lru_cache(maxsize=1)
def _get_keyword_model():
    from keybert import KeyBERT
    # Reuse the SAME sentence-embedding model the retrieval step uses, instead of letting KeyBERT
    # load a second copy of it (a second load = more waiting and more memory).
    from app.tools.evaluation_tools import _get_embedding_model
    return KeyBERT(model=_get_embedding_model())


def _tfidf_keywords_fallback(text: str, top_n: int) -> list[str]:
    """
    TF-IDF top terms, single-document version (term frequency only, since
    there's no corpus to compare against). Used if KeyBERT's underlying
    embedding model can't be downloaded — no internet dependency, works
    fully offline. Less semantically aware than KeyBERT (picks frequent
    distinctive words/bigrams rather than true keyphrases), but keeps the
    pipeline functional instead of failing the upload entirely.
    """
    from sklearn.feature_extraction.text import TfidfVectorizer

    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2), stop_words="english", max_features=top_n
    )
    try:
        matrix = vectorizer.fit_transform([text])
    except ValueError:
        return []  # text had no extractable vocabulary (e.g. too short)
    scores = matrix.toarray()[0]
    terms = vectorizer.get_feature_names_out()
    ranked = sorted(zip(terms, scores), key=lambda x: x[1], reverse=True)
    return [term for term, _score in ranked[:top_n]]


def extract_keywords(text: str, top_n: int = 10) -> list[str]:
    """Extracts top concept/keyword candidates from uploaded study material.
    Falls back to TF-IDF if KeyBERT's embedding model is unavailable."""
    global _keybert_load_failed

    # Limit text length to prevent CPU bottlenecks on long 10+ page documents
    text = text[:10000]

    if _keybert_load_failed:
        return _tfidf_keywords_fallback(text, top_n)

    try:
        kw_model = _get_keyword_model()
        # Embedding every word pair in a long document is the slow part, so cheaply pre-select
        # ~150 candidates with TF-IDF and let KeyBERT rank only those.
        candidates = _tfidf_keywords_fallback(text, 150)
        pairs = kw_model.extract_keywords(
            text, candidates=candidates or None, keyphrase_ngram_range=(1, 2), stop_words="english",
            top_n=top_n, use_mmr=True, diversity=0.5,   # MMR: avoid near-duplicate phrases
        )
        return [phrase for phrase, _score in pairs]
    except Exception:
        _keybert_load_failed = True
        return _tfidf_keywords_fallback(text, top_n)


def search_knowledge(query: str, material_text: str) -> str:
    """
    Simple relevance stub for now: returns the material text (or a
    truncated slice). In the RAG module this becomes a real vector
    search over chunked, embedded material.
    """
    if not material_text:
        return "No material uploaded yet for this student."
    return material_text[:1500]


def generate_quiz(concept_name: str, difficulty: str = "medium", question_type: str = "open",
                  context: str = "", distractors: list = None) -> dict:
    """Agent tool: one quiz question in "open" (written) or "mcq" format."""
    if question_type == "mcq":
        return _generate_mcq(concept_name, difficulty, context, distractors or [])
    return _generate_open_question(concept_name, difficulty, context)


def _using_mock() -> bool:
    from app.config import settings
    return settings.LLM_PROVIDER == "mock"


def _generate_open_question(concept_name, difficulty, context):
    if _using_mock():
        question = f"In your own words, explain {concept_name}: what is it, and why does it matter?"
    else:
        prompt = (
            f"Generate a quiz question about the concept '{concept_name}' at {difficulty} difficulty. "
            + (f"Base it on this material: {context[:800]}. " if context else "")
            + "Return only the question text."
        )
        question = llm_service.complete(prompt, system="You generate concise exam-style questions.")
    return {"concept_name": concept_name, "question_type": "open", "question": question, "difficulty": difficulty}


def _mcq_result(concept_name, difficulty, question, options, correct):
    return {"concept_name": concept_name, "question_type": "mcq", "question": question,
            "options": options, "correct_answer": correct, "difficulty": difficulty}


def _generate_mcq(concept_name, difficulty, context, distractors):
    from app.tools.mcq_tools import generate_cloze_mcq

    # Without an LLM key, build the question directly from the student's notes.
    if _using_mock():
        c = generate_cloze_mcq(concept_name, context, distractors)
        if c:
            return _mcq_result(concept_name, difficulty, c["question"], c["options"], c["correct_answer"])
    else:
        prompt = (
            f"Concept: {concept_name}\n"
            + (f"Context: {context[:800]}\n" if context else "")
            + f"Generate one multiple-choice question testing this concept at {difficulty} difficulty, "
            "with exactly 4 options where only one is correct. Respond ONLY with JSON in this exact shape, "
            'no other text: {"question": "...", "options": ["...", "...", "...", "..."], '
            '"correct_answer": "exact text of the correct option"}.'
        )
        raw = llm_service.complete(prompt, system="You output only valid JSON, nothing else, no markdown fences.")
        try:
            parsed = json.loads(re.sub(r"```json|```", "", raw).strip())
            options, correct = parsed["options"], parsed["correct_answer"]
            if correct not in options or len(options) < 2:
                raise ValueError("malformed MCQ")
            return _mcq_result(concept_name, difficulty, parsed["question"], options, correct)
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            c = generate_cloze_mcq(concept_name, context, distractors)
            if c:
                return _mcq_result(concept_name, difficulty, c["question"], c["options"], c["correct_answer"])

    # Last resort: the notes had no usable sentence/distractors for this topic.
    correct = f"{concept_name.capitalize()} is a topic covered in these notes"
    return _mcq_result(concept_name, difficulty,
                       f"[Not enough material] Which statement is true about {concept_name}?",
                       [correct, f"{concept_name.capitalize()} is never mentioned in these notes",
                        f"{concept_name.capitalize()} is unrelated to this subject",
                        f"{concept_name.capitalize()} is only a tool name"], correct)


def explain_concept(concept_name: str, context: str = "") -> str:
    """Agent tool: simple beginner-friendly explanation - the 'teach' half before testing."""
    prompt = (
        f"Explain the concept '{concept_name}' in simple, beginner-friendly terms, in 3-4 sentences. "
        "Use a concrete example or analogy. "
        + (f"Base your explanation on this source material: {context[:1000]}" if context else "")
    )
    return llm_service.complete(prompt, system="You are a patient tutor explaining a concept simply and clearly.")
