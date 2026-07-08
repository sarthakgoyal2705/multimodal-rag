"""
main.py — Multimodal RAG Pipeline Entry-Point
===============================================
Wires Phase 2 (PDF extraction), Phase 3 (VLM processing), and
Phase 4 (multi-vector indexing & retrieval) into a cohesive pipeline.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

# ── Resolve project paths ───────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
PAPERS_DIR = DATA_DIR / "papers"
IMAGES_DIR = DATA_DIR / "extracted_images"
METADATA_PATH = DATA_DIR / "extraction_metadata.json"

# ── Bootstrap ────────────────────────────────────────────────────────────────
load_dotenv(PROJECT_ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s -- %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("multimodal-rag")

# Add src to path so imports resolve cleanly
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from extractor import extract_all_pdfs, save_extraction_metadata  # noqa: E402
from vlm_processor import process_images                          # noqa: E402
from retrieval_engine import (                                     # noqa: E402
    text_chunks_to_nodes,
    build_index,
    create_query_engine,
    query_with_image_paths,
)


# ── Phase 2: PDF Extraction ─────────────────────────────────────────────────

def run_extraction():
    """Parse all PDFs and dump text + images."""
    logger.info("=" * 60)
    logger.info("Phase 2: PDF Extraction")
    logger.info("=" * 60)

    result = extract_all_pdfs(PAPERS_DIR, IMAGES_DIR)

    logger.info("  Text chunks extracted : %d", len(result.text_chunks))
    logger.info("  Images extracted      : %d", len(result.image_records))

    # Persist metadata for downstream phases
    save_extraction_metadata(result, METADATA_PATH)

    return result


# ── Phase 3: VLM Processing ─────────────────────────────────────────────────

def run_vlm_processing(extraction_result):
    """Send each extracted image to the VLM for pathway analysis."""
    logger.info("=" * 60)
    logger.info("Phase 3: VLM Image Analysis (Gemini 2.5 Flash)")
    logger.info("=" * 60)

    image_records = [r.to_dict() for r in extraction_result.image_records]
    image_nodes = process_images(image_records, model_name="gemini-2.5-flash")

    if image_nodes:
        logger.info("  -- Sample VLM summary (first 200 chars) --")
        logger.info("  %s...", image_nodes[0].text[:200])

    return image_nodes


# ── Phase 4: Indexing & Retrieval ────────────────────────────────────────────

def run_indexing_and_query(extraction_result, image_nodes):
    """Build the vector index and execute test queries."""
    logger.info("=" * 60)
    logger.info("Phase 4: Multi-Vector Indexing & Retrieval")
    logger.info("=" * 60)

    # Convert text chunks to LlamaIndex nodes
    text_dicts = [c.to_dict() for c in extraction_result.text_chunks]
    text_nodes = text_chunks_to_nodes(text_dicts)
    logger.info("  Text nodes created  : %d", len(text_nodes))
    logger.info("  Image nodes (VLM)   : %d", len(image_nodes))

    # Build the index
    index = build_index(text_nodes, image_nodes)

    # Create the query engine
    engine = create_query_engine(index, similarity_top_k=5)

    # ── Test Query ───────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("Phase 5: Test Query")
    logger.info("=" * 60)

    test_query = (
        "How do mutations in this pathway affect downstream enzyme production?"
    )

    result = query_with_image_paths(engine, test_query)
    return result


# ──────────────────────── CLI Entry-Point ────────────────────────────────────

if __name__ == "__main__":
    # Phase 2
    extraction_result = run_extraction()

    # Phase 3
    image_nodes = run_vlm_processing(extraction_result)

    # Phase 4 + 5
    query_result = run_indexing_and_query(extraction_result, image_nodes)
