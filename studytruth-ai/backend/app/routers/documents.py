from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from app.config import settings
from app.core.document_processor import ingest_document
from app.core.vector_store import rebuild_vector_store
from app.db import get_all_documents, get_document
from app.utils.logger import get_logger

router = APIRouter(prefix="/api/documents", tags=["documents"])
log = get_logger("documents_router")


@router.get("")
def list_documents(subject: Optional[str] = None, doc_type: Optional[str] = None):
    docs = get_all_documents()
    if subject:
        docs = [d for d in docs if d["subject"].lower() == subject.lower()]
    if doc_type:
        docs = [d for d in docs if d["doc_type"] == doc_type]
    for d in docs:
        d["preview"] = (d.pop("full_text", "") or "")[:220]
    return docs


@router.get("/{doc_id}")
def get_document_detail(doc_id: str):
    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    return doc


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    subject: str = Form(...),
    doc_type: str = Form(...),
    academic_year: str = Form("2025-26"),
    version: str = Form("v1"),
    upload_date: Optional[str] = Form(None),
):
    dest = settings.UPLOAD_DIR / file.filename
    content = await file.read()
    dest.write_bytes(content)

    try:
        meta = ingest_document(
            file_path=dest, filename=file.filename, subject=subject,
            doc_type=doc_type, academic_year=academic_year, version=version,
            upload_date=upload_date,
        )
    except Exception as e:
        log.exception("Ingestion failed")
        raise HTTPException(400, f"Could not process file: {e}")

    rebuild_vector_store()
    return {"status": "ok", "document": meta}
