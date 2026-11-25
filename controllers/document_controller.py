import hashlib
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from config.database import get_db
from models.document import Document
from models.user import User
from rag.chunker import split_chunks
from rag.loader import extract_text
from rag.retriever import index_chunks
from security.basic_auth import require_admin

router = APIRouter(prefix="/api/documents", tags=["documents"])
_MAX_UPLOAD = 10 * 1024 * 1024
_ALLOWED = {".pdf", ".docx", ".txt"}


@router.post("", status_code=201)
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    safe_name = Path(file.filename or "").name
    suffix = Path(safe_name).suffix.lower()
    if suffix not in _ALLOWED:
        raise HTTPException(status_code=415, detail="Upload a PDF, DOCX, or TXT file")
    content = await file.read(_MAX_UPLOAD + 1)
    if not content or len(content) > _MAX_UPLOAD:
        raise HTTPException(status_code=413, detail="Document must be smaller than 10 MB")
    try:
        pages = extract_text(safe_name, content)
        chunks = split_chunks(pages)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="The document could not be read") from exc
    if not chunks:
        raise HTTPException(status_code=422, detail="The document contains no readable text")
    digest = hashlib.sha256(content).hexdigest()
    document = Document(filename=safe_name, sha256=digest, uploaded_by=admin.id, status="ACTIVE")
    db.add(document)
    db.flush()
    uploads = Path("uploads")
    uploads.mkdir(exist_ok=True)
    (uploads / f"{uuid4().hex}.txt").write_text("\n\n".join(chunk["text"] for chunk in chunks), encoding="utf-8")
    indexed = False
    try:
        indexed = index_chunks(safe_name, chunks, document.id)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=503, detail="Document was not indexed; check OpenAI and Chroma configuration")
    db.commit()
    return {"id": document.id, "filename": safe_name, "chunks": len(chunks), "vector_indexed": indexed, "message": "Document saved for local retrieval" if not indexed else "Document uploaded and indexed"}
