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


def store_chunks_fast(db: Session, material: Material, text: str, max_chunks: int = 60) -> int:
    """Split text into chunks and store in DB immediately with embedding=None.
    Runs in < 0.01 seconds so upload and retrieval are never blocked."""
    existing = db.query(MaterialChunk).filter(MaterialChunk.material_id == material.id).count()
    if existing:
        return existing
    chunks = chunk_text(text)[:max_chunks]
    if not chunks:
        return 0
    for i, chunk in enumerate(chunks):
        db.add(MaterialChunk(
            material_id=material.id,
            student_id=material.student_id,
            chunk_index=i,
            text=chunk,
            embedding=None,
        ))
    db.commit()
    return len(chunks)


def embed_pending_chunks(db: Session, material_id: int, batch_size: int = 8) -> int:
    """Compute embeddings in small batches for chunks that don't have them yet."""
    pending = (db.query(MaterialChunk)
               .filter(MaterialChunk.material_id == material_id, MaterialChunk.embedding.is_(None))
               .order_by(MaterialChunk.chunk_index)
               .all())
    if not pending:
        return 0

    count = 0
    for i in range(0, len(pending), batch_size):
        batch = pending[i:i + batch_size]
        texts = [c.text for c in batch]
        vectors = _embed(texts)
        if not vectors:
            break
        for c, vec in zip(batch, vectors):
            c.embedding = vec
        db.commit()
        count += len(batch)
    return count


def index_material(db: Session, material: Material, text: str) -> int:
    """Chunk and embed a material. Fast stores chunks, then computes embeddings."""
    n = store_chunks_fast(db, material, text)
    try:
        embed_pending_chunks(db, material.id)
    except Exception:
        pass
    return n


def _ensure_indexed(db: Session, student_id: int):
    """Lazily index any older uploads that predate the chunk table (without blocking on embeddings)."""
    for m in db.query(Material).filter(Material.student_id == student_id).all():
        has = db.query(MaterialChunk).filter(MaterialChunk.material_id == m.id).first()
        if not has and m.raw_text:
            store_chunks_fast(db, m, m.raw_text)


def rank_texts(texts: list[str], query: str, vectors=None, method: str = "auto"):
    """Score every passage against the query. Pure function (no database), so the
    evaluation harness can compare methods on identical inputs.

    method: "embeddings" (cosine similarity of sentence embeddings), "tfidf" (lexical),
            or "auto" (embeddings when available, else tfidf).
    Returns (scores, method_used); scores is None if "embeddings" was forced but unavailable.
    """
    import numpy as np

    if method == "hybrid":
        if not vectors:
            return rank_texts(texts, query, method="tfidf")
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
        if not vectors:
            if method == "embeddings":
                return None, "embeddings"
            return rank_texts(texts, query, method="tfidf")
        try:
            q_vec = _embed([query])
            if q_vec and vectors:
                m, q = np.array(vectors), np.array(q_vec[0])
                denom = (np.linalg.norm(m, axis=1) * np.linalg.norm(q)) + 1e-9
                return (m @ q) / denom, "embeddings"
        except Exception:
            pass
        if method == "embeddings":
            return None, "embeddings"

    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import linear_kernel
    try:
        matrix = TfidfVectorizer(stop_words="english").fit_transform(texts + [query])
        return linear_kernel(matrix[-1], matrix[:-1]).ravel(), "tfidf"
    except Exception:
        import numpy as np
        return np.zeros(len(texts)), "tfidf"


def retrieve(db: Session, student_id: int, query: str, k: int = 3) -> list[dict]:
    """Top-k passages from the student's own material for this query."""
    chunks = db.query(MaterialChunk).filter(MaterialChunk.student_id == student_id).all()
    if not chunks:
        _ensure_indexed(db, student_id)
        chunks = db.query(MaterialChunk).filter(MaterialChunk.student_id == student_id).all()
    if not chunks:
        return []

    has_embeddings = all(c.embedding is not None for c in chunks)
    vectors = [c.embedding for c in chunks] if has_embeddings else None

    from app.config import settings
    desired = settings.RETRIEVAL_METHOD
    # If vectors are not ready yet, seamlessly fall back to tfidf without stalling
    method_to_use = desired if (has_embeddings or desired == "tfidf") else "tfidf"

    scores, method = rank_texts([c.text for c in chunks], query, vectors=vectors,
                                method=method_to_use)

    ranked = sorted(zip(chunks, scores), key=lambda x: float(x[1]), reverse=True)[:k]
    return [
        {"text": c.text, "score": round(float(sc), 3), "chunk_index": c.chunk_index, "method": method}
        for c, sc in ranked
    ]
