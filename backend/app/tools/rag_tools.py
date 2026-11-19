"""
Real retrieval for the agent: chunk -> embed -> index -> retrieve.

Pipeline:
  index_material():  split the PDF text into overlapping passages, embed each
                     with sentence-transformers, store in MaterialChunk.
  retrieve():        embed the query (the concept being taught), rank passages
                     by cosine similarity, return top-k with scores.

Graceful degradation (same pattern as the rest of the project): if the
embedding model is unavailable (no internet on first run), chunks are stored
without embeddings and retrieval falls back to TF-IDF cosine similarity over
the chunks - lexical instead of semantic, but still real ranked retrieval.
"""
import re
import threading

from sqlalchemy.orm import Session

from app.models import Material, MaterialChunk


def chunk_text(text: str, max_chars: int = 600, overlap_sentences: int = 1) -> list[str]:
    """Sentence-aware chunking: pack sentences up to max_chars, carry the last
    sentence into the next chunk so ideas that straddle a boundary aren't lost."""
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks, current = [], []
    for sent in sentences:
        if current and len(" ".join(current)) + len(sent) > max_chars:
            chunks.append(" ".join(current))
            current = current[-overlap_sentences:] if overlap_sentences else []
        current.append(sent)
    if current:
        chunks.append(" ".join(current))
    return chunks


def _embed(texts: list[str]):
    """Returns list of vectors, or None if the embedding model is unavailable."""
    try:
        from app.tools.evaluation_tools import _get_embedding_model
        model = _get_embedding_model()
        return [v.tolist() for v in model.encode(texts, batch_size=64, show_progress_bar=False)]
    except Exception:
        return None


_locks: dict = {}
_locks_guard = threading.Lock()


def index_material(db: Session, material: Material, text: str) -> int:
    """Chunk + embed a material and store its passages. Returns chunk count.

    Safe to call twice at once (the background job after an upload, and a student pressing
    Explain straight away): a per-material lock makes the second caller wait, then find the
    passages already stored instead of indexing again."""
    with _locks_guard:
        lock = _locks.setdefault(material.id, threading.Lock())
    with lock:
        existing = db.query(MaterialChunk).filter(MaterialChunk.material_id == material.id).count()
        if existing:
            return existing
        chunks = chunk_text(text)
        if not chunks:
            return 0
        vectors = _embed(chunks)
        for i, chunk in enumerate(chunks):
            db.add(MaterialChunk(
                material_id=material.id,
                student_id=material.student_id,
                chunk_index=i,
                text=chunk,
                embedding=vectors[i] if vectors else None,
            ))
        db.commit()
        return len(chunks)


def _ensure_indexed(db: Session, student_id: int):
    """Lazily index any older uploads that predate the chunk table."""
    for m in db.query(Material).filter(Material.student_id == student_id).all():
        has = db.query(MaterialChunk).filter(MaterialChunk.material_id == m.id).first()
        if not has and m.raw_text:
            index_material(db, m, m.raw_text)


def rank_texts(texts: list[str], query: str, vectors=None, method: str = "auto"):
    """Score every passage against the query. Pure function (no database), so the
    evaluation harness can compare methods on identical inputs.

    method: "embeddings" (cosine similarity of sentence embeddings), "tfidf" (lexical),
            or "auto" (embeddings when available, else tfidf).
    Returns (scores, method_used); scores is None if "embeddings" was forced but unavailable.
    """
    import numpy as np

    if method == "hybrid":
        # Score fusion: min-max normalise the semantic and the lexical scores, then average.
        # Semantic scores catch paraphrases; lexical scores catch exact terms. Each covers
        # the other's blind spot.
        sem, used = rank_texts(texts, query, vectors=vectors, method="embeddings")
        lex, _ = rank_texts(texts, query, method="tfidf")
        if sem is None:
            return lex, "tfidf"

        def norm01(a):
            a = np.asarray(a, dtype=float)
            span = a.max() - a.min()
            return (a - a.min()) / span if span > 1e-9 else np.zeros_like(a)

        return 0.5 * norm01(sem) + 0.5 * norm01(lex), "hybrid"

    if method in ("auto", "embeddings"):
        q_vec = _embed([query])
        if q_vec:
            vecs = vectors if vectors else _embed(texts)
            if vecs:
                m, q = np.array(vecs), np.array(q_vec[0])
                denom = (np.linalg.norm(m, axis=1) * np.linalg.norm(q)) + 1e-9
                return (m @ q) / denom, "embeddings"
        if method == "embeddings":
            return None, "embeddings"

    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import linear_kernel
    try:
        matrix = TfidfVectorizer(stop_words="english").fit_transform(texts + [query])
        return linear_kernel(matrix[-1], matrix[:-1]).ravel(), "tfidf"
    except ValueError:
        return np.zeros(len(texts)), "tfidf"


def retrieve(db: Session, student_id: int, query: str, k: int = 3) -> list[dict]:
    """Top-k passages from the student's own material for this query."""
    _ensure_indexed(db, student_id)
    chunks = db.query(MaterialChunk).filter(MaterialChunk.student_id == student_id).all()
    if not chunks:
        return []

    vectors = [c.embedding for c in chunks] if all(c.embedding for c in chunks) else None
    from app.config import settings
    scores, method = rank_texts([c.text for c in chunks], query, vectors=vectors,
                                method=settings.RETRIEVAL_METHOD)

    ranked = sorted(zip(chunks, scores), key=lambda x: float(x[1]), reverse=True)[:k]
    return [
        {"text": c.text, "score": round(float(sc), 3), "chunk_index": c.chunk_index, "method": method}
        for c, sc in ranked
    ]
