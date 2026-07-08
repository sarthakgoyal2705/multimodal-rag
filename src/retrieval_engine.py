"""
retrieval_engine.py — Phase 4: Multi-Vector Indexing & Retrieval
=================================================================
Combines text chunks (Phase 2) and VLM image-summary nodes (Phase 3) into
a single VectorStoreIndex.  Provides a query interface that returns the
generated answer **and** file paths to any clinical diagrams that informed it.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Sequence

from llama_index.core import Settings, VectorStoreIndex
from llama_index.core.schema import TextNode
from llama_index.embeddings.gemini import GeminiEmbedding

logger = logging.getLogger(__name__)


# ──────────────────── Node Construction ──────────────────────────────────────

def text_chunks_to_nodes(text_chunks: list[dict]) -> list[TextNode]:
    """Convert raw text-chunk dicts (from Phase 2) into LlamaIndex TextNodes."""
    nodes: list[TextNode] = []
    for chunk in text_chunks:
        node = TextNode(
            text=chunk["text"],
            metadata={
                "source_pdf": chunk.get("source_pdf", "unknown"),
                "page_number": chunk.get("page_number", 0),
                "chunk_index": chunk.get("chunk_index", 0),
                "has_image": False,
                "node_type": "text_chunk",
            },
            excluded_embed_metadata_keys=["has_image", "node_type", "chunk_index"],
            excluded_llm_metadata_keys=["has_image", "node_type", "chunk_index"],
        )
        nodes.append(node)
    return nodes


# ──────────────────── Index Building ─────────────────────────────────────────

def build_index(
    text_nodes: list[TextNode],
    image_nodes: list[TextNode],
    embedding_model: str = "models/gemini-embedding-001",
) -> VectorStoreIndex:
    """Merge text + image nodes and build a local VectorStoreIndex.

    Parameters
    ----------
    text_nodes:
        TextNodes from Phase 2 text extraction.
    image_nodes:
        TextNodes from Phase 3 VLM processing (contain image metadata).
    embedding_model:
        Gemini embedding model name (free tier).

    Returns
    -------
    VectorStoreIndex
        Ready for querying.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set in environment.")

    # Configure the embedding model globally
    embed_model = GeminiEmbedding(
        model_name=embedding_model,
        api_key=api_key,
    )
    Settings.embed_model = embed_model

    # Merge all nodes
    all_nodes = text_nodes + image_nodes
    logger.info(
        "Building index with %d nodes (%d text + %d image)",
        len(all_nodes), len(text_nodes), len(image_nodes),
    )

    index = VectorStoreIndex(nodes=all_nodes)
    logger.info("VectorStoreIndex built successfully")
    return index


# ──────────────────── Query Engine ───────────────────────────────────────────

def create_query_engine(index: VectorStoreIndex, similarity_top_k: int = 5):
    """Create a query engine with custom response formatting.

    The engine inspects source nodes after retrieval: if any node carries
    the ``has_image`` metadata flag, the file path to the original ``.png``
    diagram is included in the output.
    """
    from llama_index.core.query_engine import RetrieverQueryEngine
    from llama_index.core.retrievers import VectorIndexRetriever
    from llama_index.core.response_synthesizers import get_response_synthesizer
    from llama_index.llms.openai_like import OpenAILike

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not set in environment.")

    # Use Groq via generic OpenAI compatible endpoint to avoid strict model name validation
    llm = OpenAILike(
        model="llama-3.1-8b-instant", # Note: Updated to a fast and stable Groq model
        api_key=api_key, 
        api_base="https://api.groq.com/openai/v1",
        is_chat_model=True
    )
    Settings.llm = llm

    retriever = VectorIndexRetriever(index=index, similarity_top_k=similarity_top_k)
    synthesizer = get_response_synthesizer(llm=llm)

    engine = RetrieverQueryEngine(retriever=retriever, response_synthesizer=synthesizer)
    return engine


def query_with_image_paths(engine, query: str) -> dict:
    """Execute a query and return the answer plus any referenced diagram paths.

    Returns
    -------
    dict with keys:
        ``answer``       — the synthesised text response.
        ``image_paths``  — list of absolute paths to diagrams that informed the answer.
        ``source_nodes`` — summary of all retrieved source nodes.
    """
    logger.info("Query: %s", query)
    response = engine.query(query)

    answer = str(response)
    image_paths: list[str] = []
    source_summaries: list[dict] = []

    for node_with_score in response.source_nodes:
        node = node_with_score.node
        meta = node.metadata or {}
        score = node_with_score.score

        summary = {
            "score": round(score, 4) if score else None,
            "source_pdf": meta.get("source_pdf", "unknown"),
            "page_number": meta.get("page_number", 0),
            "node_type": meta.get("node_type", "unknown"),
            "text_preview": node.text,
        }

        # ── Check for image metadata flag ────────────────────────────
        if meta.get("has_image"):
            img_path = meta.get("image_path", "")
            if img_path:
                image_paths.append(img_path)
                summary["image_path"] = img_path

        source_summaries.append(summary)

    # ── Console output ───────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("QUERY RESULT")
    print("=" * 70)
    print(f"\nQ: {query}\n")
    print(f"A: {answer}\n")

    if image_paths:
        print("-" * 70)
        print("REFERENCED CLINICAL DIAGRAMS:")
        for path in image_paths:
            print(f"  -> {path}")
    else:
        print("(No clinical diagrams were referenced in this answer)")

    print("-" * 70)
    print(f"Source nodes retrieved: {len(source_summaries)}")
    for i, s in enumerate(source_summaries, 1):
        tag = "[IMAGE]" if "image_path" in s else "[TEXT] "
        print(f"  {i}. {tag}  score={s['score']}  {s['source_pdf']}  p{s['page_number']}")
    print("=" * 70 + "\n")

    return {
        "answer": answer,
        "image_paths": image_paths,
        "source_nodes": source_summaries,
    }
