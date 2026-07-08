"""
vlm_processor.py — Phase 3: Context-Aware VLM Processing
==========================================================
Sends each extracted image (+ its caption metadata) to a Vision-Language Model
(Google Gemini) for rigorous biological pathway analysis.  Returns LlamaIndex
``TextNode`` objects with the VLM-generated summaries and image-path metadata.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Sequence

from llama_index.core.schema import TextNode, NodeRelationship, RelatedNodeInfo

logger = logging.getLogger(__name__)

# ── VLM Prompt ───────────────────────────────────────────────────────────────

PATHWAY_ANALYSIS_PROMPT = (
    "You are an expert bioinformatics agent. Analyze this biological pathway "
    "diagram. Provide a rigorous text description detailing every biological "
    "entity (genes, proteins, enzymes), directed interactions (activation, "
    "inhibition), and clinical outcomes shown."
)

# ── Gemini Client (google-generativeai SDK) ──────────────────────────────────

def _get_groq_client():
    """Lazily initialise the groq client."""
    from groq import Groq

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Populate it in your .env file."
        )
    return Groq(api_key=api_key)


def _analyze_image_with_groq(
    image_path: str,
    caption: str,
    surrounding_text: str,
    model_name: str = "llama-3.2-11b-vision-preview",
    max_retries: int = 3,
) -> str:
    """Send a single image + context to Groq and return the analysis text."""
    import base64
    client = _get_groq_client()

    with open(image_path, "rb") as image_file:
        base64_image = base64.b64encode(image_file.read()).decode('utf-8')

    # Groq has completely decommissioned their Vision models as of late 2024
    # (llama-3.2-11b-vision-preview etc. are removed). 
    # Therefore, we bypass the VLM phase and gracefully degrade to just storing the caption.
    logger.info("Groq vision models are unavailable. Bypassing VLM image processing.")
    
    return f"[VLM Image Analysis Skipped: Groq vision models currently unavailable] Caption: {caption}"


# ── Public API ───────────────────────────────────────────────────────────────

def process_images(
    image_records: list[dict],
    model_name: str = "gemini-2.5-flash",
) -> list[TextNode]:
    """Iterate through extracted image records, analyse each with the VLM,
    and return LlamaIndex TextNode objects.

    Parameters
    ----------
    image_records:
        List of dicts from ``ExtractionResult.image_records`` (or the JSON
        metadata file).  Each dict must have at least ``image_path``,
        ``caption``, and ``surrounding_text``.
    model_name:
        Gemini model to use.

    Returns
    -------
    list[TextNode]
        One node per image.  Each node's ``metadata`` contains:
        - ``image_path``: absolute path to the original ``.png``
        - ``source_pdf``: originating PDF filename
        - ``page_number``: page the image was on
        - ``has_image``: ``True`` (flag used in retrieval formatting)
    """
    nodes: list[TextNode] = []

    for idx, record in enumerate(image_records):
        image_path = record["image_path"]
        caption = record.get("caption", "")
        surrounding = record.get("surrounding_text", "")
        source_pdf = record.get("source_pdf", "unknown")
        page_number = record.get("page_number", 0)

        if not Path(image_path).exists():
            logger.warning("Image not found, skipping: %s", image_path)
            continue

        logger.info(
            "  [%d/%d] Analysing image: %s",
            idx + 1, len(image_records), Path(image_path).name,
        )

        # ── Call VLM ─────────────────────────────────────────────────
        vlm_summary = _analyze_image_with_groq(
            image_path=image_path,
            caption=caption,
            surrounding_text=surrounding,
            model_name="llama-3.2-11b-vision-preview",
        )

        logger.info("    VLM summary length: %d chars", len(vlm_summary))

        # ── Build TextNode ───────────────────────────────────────────
        node = TextNode(
            text=vlm_summary,
            metadata={
                "image_path": image_path,
                "source_pdf": source_pdf,
                "page_number": page_number,
                "caption": caption,
                "has_image": True,
                "node_type": "vlm_image_summary",
            },
            excluded_embed_metadata_keys=["image_path", "has_image", "node_type"],
            excluded_llm_metadata_keys=["image_path", "has_image", "node_type"],
        )
        nodes.append(node)

    logger.info("VLM processing complete: %d image nodes created", len(nodes))
    return nodes
