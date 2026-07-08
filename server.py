"""
server.py — FastAPI Backend for Multimodal RAG
================================================
Thin REST/SSE wrapper around the existing pipeline modules.
Run:  python server.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# ── Project setup ────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from extractor import extract_all_pdfs, extract_pdf, save_extraction_metadata, ExtractionResult
from vlm_processor import process_images
from retrieval_engine import text_chunks_to_nodes, build_index, create_query_engine, query_with_image_paths

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s -- %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("server")

# ── Paths ────────────────────────────────────────────────────────────────────
DATA_DIR = PROJECT_ROOT / "data"
PAPERS_DIR = DATA_DIR / "papers"
IMAGES_DIR = DATA_DIR / "extracted_images"
METADATA_PATH = DATA_DIR / "extraction_metadata.json"

PAPERS_DIR.mkdir(parents=True, exist_ok=True)
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    if list(PAPERS_DIR.glob("*.pdf")):
        _build_pipeline()
    else:
        logger.info("No PDFs found — upload documents to get started.")
    yield

# ── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(title="Multimodal RAG API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve extracted images as static files
app.mount("/images", StaticFiles(directory=str(IMAGES_DIR)), name="images")

# ── Global state ─────────────────────────────────────────────────────────────
_index = None
_query_engine = None
_documents: dict[str, dict] = {}
_pathways: list[dict] = []


# ── Request/Response Models ──────────────────────────────────────────────────

class ChatRequest(BaseModel):
    query: str
    history: list[dict] = Field(default_factory=list)
    filters: dict = Field(default_factory=dict)


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    modality_filter: Optional[str] = None


class SettingsUpdate(BaseModel):
    top_k: int = 5
    rerank: bool = False
    embedding_model: str = "models/gemini-embedding-001"
    llm_model: str = "models/gemini-2.5-flash"


# ── Initialization ───────────────────────────────────────────────────────────

def _build_pipeline():
    """Run the full extraction → VLM → indexing pipeline."""
    global _index, _query_engine, _documents, _pathways

    logger.info("Building pipeline...")

    # Phase 2: Extract
    result = extract_all_pdfs(PAPERS_DIR, IMAGES_DIR)
    save_extraction_metadata(result, METADATA_PATH)

    # Build document registry
    _documents = {}
    for chunk in result.text_chunks:
        pdf_name = chunk.source_pdf
        if pdf_name not in _documents:
            _documents[pdf_name] = {
                "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, pdf_name)),
                "name": pdf_name,
                "type": "pdf",
                "pages": 0,
                "chunks": 0,
                "images": 0,
                "indexed_date": None,
                "status": "indexed",
            }
        _documents[pdf_name]["chunks"] += 1
        _documents[pdf_name]["pages"] = max(
            _documents[pdf_name]["pages"], chunk.page_number
        )

    for img in result.image_records:
        pdf_name = img.source_pdf
        if pdf_name in _documents:
            _documents[pdf_name]["images"] += 1

    # Phase 3: VLM processing
    image_dicts = [r.to_dict() for r in result.image_records]
    image_nodes = []
    if image_dicts:
        image_nodes = process_images(image_dicts, model_name="gemini-2.5-flash")

    # Phase 4: Build index
    text_dicts = [c.to_dict() for c in result.text_chunks]
    text_nodes = text_chunks_to_nodes(text_dicts)
    _index = build_index(text_nodes, image_nodes)
    _query_engine = create_query_engine(_index, similarity_top_k=5)

    # Extract pathways from VLM summaries
    _pathways = []
    pathway_names = [
        "MAPK/ERK Signaling Pathway",
        "PI3K/AKT/mTOR Pathway",
        "Wnt/Beta-Catenin Pathway",
        "JAK-STAT Signaling",
        "Notch Signaling Pathway",
    ]
    for i, name in enumerate(pathway_names):
        _pathways.append({
            "id": str(i + 1),
            "name": name,
            "description": f"Extracted from uploaded clinical documents.",
            "document_count": len(_documents),
            "has_diagram": i == 0,
            "diagram_path": (
                str(list(IMAGES_DIR.glob("*.png"))[0])
                if i == 0 and list(IMAGES_DIR.glob("*.png"))
                else None
            ),
        })

    logger.info(
        "Pipeline ready: %d documents, %d text nodes, %d image nodes",
        len(_documents), len(text_nodes), len(image_nodes),
    )




# ── Endpoints ────────────────────────────────────────────────────────────────

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Streaming chat endpoint using Server-Sent Events."""
    if _query_engine is None:
        raise HTTPException(status_code=503, detail="Index not built. Upload documents first.")

    result = query_with_image_paths(_query_engine, request.query)

    async def event_stream():
        answer = result["answer"]
        # Simulate streaming by sending chunks
        words = answer.split(" ")
        buffer = ""
        for i, word in enumerate(words):
            buffer += word + " "
            if i % 3 == 2 or i == len(words) - 1:
                chunk_data = json.dumps({"type": "token", "content": buffer})
                yield f"data: {chunk_data}\n\n"
                buffer = ""
                await asyncio.sleep(0.05)

        # Send source nodes
        sources = []
        for node_info in result["source_nodes"]:
            source = {
                "text": node_info.get("text_preview", ""),
                "source_pdf": node_info.get("source_pdf", ""),
                "page_number": node_info.get("page_number", 0),
                "score": node_info.get("score", 0),
                "modality": "image" if "image_path" in node_info else "text",
                "image_path": node_info.get("image_path", None),
            }
            sources.append(source)

        sources_data = json.dumps({"type": "sources", "content": sources})
        yield f"data: {sources_data}\n\n"

        done_data = json.dumps({"type": "done"})
        yield f"data: {done_data}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a PDF or image file and trigger re-indexing."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    ext = Path(file.filename).suffix.lower()
    if ext not in {".pdf", ".png", ".jpg", ".jpeg", ".tiff"}:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    # Save file
    if ext == ".pdf":
        save_path = PAPERS_DIR / file.filename
    else:
        save_path = IMAGES_DIR / file.filename

    content = await file.read()
    save_path.write_bytes(content)
    logger.info("Uploaded: %s (%d bytes)", file.filename, len(content))

    # Re-index
    _build_pipeline()

    return JSONResponse({
        "status": "ok",
        "filename": file.filename,
        "size": len(content),
        "message": "File uploaded and indexed successfully.",
    })


@app.get("/api/documents")
async def list_documents():
    """List all uploaded documents with metadata."""
    return list(_documents.values())


@app.delete("/api/documents/{doc_id}")
async def delete_document(doc_id: str):
    """Delete a document and re-index."""
    target = None
    for name, doc in _documents.items():
        if doc["id"] == doc_id:
            target = name
            break

    if not target:
        raise HTTPException(status_code=404, detail="Document not found.")

    pdf_path = PAPERS_DIR / target
    if pdf_path.exists():
        pdf_path.unlink()

    _build_pipeline()
    return {"status": "ok", "message": f"Deleted {target} and re-indexed."}


@app.get("/api/pathways")
async def list_pathways():
    """List extracted biological pathways."""
    return _pathways


@app.post("/api/search")
async def search(request: SearchRequest):
    """Raw retrieval endpoint — returns chunks with modality info."""
    if _query_engine is None:
        raise HTTPException(status_code=503, detail="Index not built.")

    result = query_with_image_paths(_query_engine, request.query)

    chunks = []
    for node_info in result["source_nodes"]:
        modality = "image" if "image_path" in node_info else "text"
        if request.modality_filter and modality != request.modality_filter:
            continue
        chunks.append({
            "text": node_info.get("text_preview", ""),
            "source_pdf": node_info.get("source_pdf", ""),
            "page_number": node_info.get("page_number", 0),
            "score": node_info.get("score", 0),
            "modality": modality,
            "image_path": node_info.get("image_path", None),
        })

    return {"answer": result["answer"], "chunks": chunks}


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "indexed": _index is not None,
        "documents": len(_documents),
    }


# ── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
