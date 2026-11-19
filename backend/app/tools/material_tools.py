"""
Tools for turning an uploaded document into structured knowledge:
text extraction -> keyword/concept extraction (already in knowledge_tools)
-> prerequisite relationship inference.

This is the module that closes the gap between "upload a PDF" and
"the knowledge graph has real concepts in it" — the actual core of the
NLP story for this project.
"""
import json
import re
from io import BytesIO

from app.services.llm_service import llm_service


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extracts raw text from a PDF's pages, concatenated."""
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(file_bytes))
    pages_text = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages_text)


def infer_prerequisites(concepts: list[str], subject: str) -> dict:
    """
    Asks the LLM to reason about which concepts depend on which others,
    given only their names. Returns {concept_name: [prerequisite_names]}.

    Falls back to a simple linear chain (each concept depends on the one
    before it, in extraction order) if the LLM output can't be parsed —
    extraction order roughly tracks how material is usually written
    (foundational ideas introduced before ideas that build on them), so
    it's a reasonable degraded default rather than leaving prerequisites
    empty.
    """
    if len(concepts) < 2:
        return {c: [] for c in concepts}

    prompt = (
        f"Subject: {subject}\n"
        f"Concepts: {', '.join(concepts)}\n\n"
        "For each concept, list which OTHER concepts from this list are "
        "prerequisites a student should understand first. Respond ONLY "
        "with JSON in this exact shape, no other text: "
        '{"concept_name": ["prerequisite1", "prerequisite2"], ...}. '
        "Concepts with no prerequisites should map to an empty list."
    )

    raw = llm_service.complete(
        prompt,
        system="You output only valid JSON, nothing else, no markdown fences.",
    )

    try:
        cleaned = re.sub(r"```json|```", "", raw).strip()
        parsed = json.loads(cleaned)
        # Keep only prerequisites that are actually in our concept list,
        # and only for concepts we actually extracted.
        result = {}
        for concept in concepts:
            prereqs = parsed.get(concept, [])
            result[concept] = [p for p in prereqs if p in concepts and p != concept]
        return result
    except (json.JSONDecodeError, AttributeError, TypeError):
        # Degraded fallback: linear chain in extraction order.
        result = {concepts[0]: []}
        for i in range(1, len(concepts)):
            result[concepts[i]] = [concepts[i - 1]]
        return result
