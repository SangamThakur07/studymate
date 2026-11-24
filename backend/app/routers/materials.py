"""
Material upload endpoint. This is the entry point for your core product
vision: someone uploads their own notes/PDF, and the system builds a
knowledge graph from it automatically — no manual concept entry needed.
"""
import time

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models import Student, Material, Concept
from app.security import get_owned_student
from app.tools.material_tools import extract_text_from_pdf, infer_prerequisites
from app.tools.knowledge_tools import extract_keywords
from app.tools.rag_tools import store_chunks_fast, embed_pending_chunks
from app.tools.topic_tools import extract_topics

router = APIRouter(prefix="/students", tags=["materials"])


def _index_in_background(material_id: int):
    """Embed the passages in background in small batches so requests are never frozen."""
    t0 = time.time()
    db = SessionLocal()
    try:
        n = embed_pending_chunks(db, material_id)
        print(f"[index] material {material_id}: {n} passages embedded in {time.time() - t0:.1f}s")
    except Exception as exc:
        print(f"[index] background embedding failed ({exc})")
    finally:
        db.close()


@router.post("/{student_id}/materials/upload")
def upload_material(background: BackgroundTasks, file: UploadFile = File(...),
                    student: Student = Depends(get_owned_student), db: Session = Depends(get_db)):
    # A plain (non-async) handler runs in a worker thread, so the heavy NLP below no longer
    # freezes every other request while it works.
    student_id = student.id
    t_start = time.time()
    seconds = {}

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported right now.")

    file_bytes = file.file.read()
    from app.config import settings
    if len(file_bytes) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File too large (limit {settings.MAX_UPLOAD_MB} MB).")
    try:
        raw_text = extract_text_from_pdf(file_bytes)
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read this PDF. It may be scanned/image-based or corrupted.")

    if not raw_text.strip():
        raise HTTPException(status_code=400, detail="No extractable text found in this PDF.")
    seconds["read_pdf"] = round(time.time() - t_start, 2)

    # 1. NLP: pull candidate concepts/keywords out of the raw text.
    t = time.time()
    keywords = extract_topics(raw_text, limit=12)
    seconds["find_topics"] = round(time.time() - t, 2)

    # 2. Store the material record.
    material = Material(
        student_id=student_id,
        filename=file.filename,
        raw_text=raw_text[:20000],  # cap stored text; full retrieval chunking comes with RAG phase
        extracted_keywords=keywords,
    )
    db.add(material)
    db.commit()
    db.refresh(material)

    # 2b. Immediately create chunks in DB so RAG retrieval works instantly via TF-IDF with zero delay.
    store_chunks_fast(db, material, raw_text)

    # 2c. Background task computes embeddings without blocking response
    background.add_task(_index_in_background, material.id)

    # 3. Infer prerequisite relationships between the extracted concepts.
    prereq_map = infer_prerequisites(keywords, student.subject)

    # 4. Upsert Concept rows so the knowledge graph and dashboard reflect
    #    this material immediately — no manual entry required.
    created, updated = [], []
    for name in keywords:
        existing = (
            db.query(Concept)
            .filter(Concept.name == name, Concept.student_id == student_id)
            .first()
        )
        prereq_str = ", ".join(prereq_map.get(name, []))
        if existing:
            existing.prerequisites = prereq_str
            existing.source_material_id = material.id
            updated.append(name)
        else:
            db.add(Concept(
                student_id=student_id,
                name=name,
                subject=student.subject,
                prerequisites=prereq_str,
                source_material_id=material.id,
            ))
            created.append(name)
    db.commit()

    return {
        "material_id": material.id,
        "filename": file.filename,
        "indexing": "running in background",
        "seconds": {**seconds, "total": round(time.time() - t_start, 2)},
        "concepts_extracted": keywords,
        "concepts_created": created,
        "concepts_updated": updated,
        "prerequisite_map": prereq_map,
    }


@router.get("/{student_id}/materials")
def list_materials(student: Student = Depends(get_owned_student), db: Session = Depends(get_db)):
    materials = db.query(Material).filter(Material.student_id == student.id).all()
    return [
        {
            "id": m.id,
            "filename": m.filename,
            "extracted_keywords": m.extracted_keywords,
            "uploaded_at": m.uploaded_at,
        }
        for m in materials
    ]


@router.get("/{student_id}/concepts")
def list_concepts(student: Student = Depends(get_owned_student), db: Session = Depends(get_db)):
    concepts = db.query(Concept).filter(Concept.student_id == student.id).all()
    return [
        {
            "name": c.name,
            "prerequisites": [p.strip() for p in (c.prerequisites or "").split(",") if p.strip()],
        }
        for c in concepts
    ]
