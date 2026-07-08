"""
extractor.py — Phase 2: Intelligent PDF Parsing & Extraction
=============================================================
Uses PyMuPDF (fitz) to split every PDF in ``data/papers`` into two streams:

1. **Text Stream** — paragraphs → markdown-style text chunks.
2. **Image Stream** — embedded images → ``.png`` files in ``data/extracted_images``
   with caption metadata harvested from the surrounding text.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Sequence

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

# ───────────────────────── Data Classes ──────────────────────────────────────

@dataclass
class TextChunk:
    """A contiguous block of text extracted from a PDF page."""

    text: str
    source_pdf: str
    page_number: int
    chunk_index: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ImageRecord:
    """Metadata for a single image extracted from a PDF."""

    image_path: str          # absolute path to the saved .png
    source_pdf: str
    page_number: int
    image_index: int
    caption: str = ""
    surrounding_text: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ExtractionResult:
    """Aggregate output of the PDF extraction pipeline."""

    text_chunks: list[TextChunk] = field(default_factory=list)
    image_records: list[ImageRecord] = field(default_factory=list)


# ───────────────────── Helper Utilities ──────────────────────────────────────

_CAPTION_PATTERN = re.compile(
    r"((?:Fig(?:ure)?|Diagram|Scheme|Chart|Panel)\s*\.?\s*\d+[A-Za-z]?"
    r"(?:\s*[:\-–—]\s*[^\n]{0,200})?)",
    re.IGNORECASE,
)

MIN_PARAGRAPH_LENGTH = 60  # characters — skip very short noise fragments


def _find_caption(page_text: str, image_bbox: fitz.Rect, page: fitz.Page) -> str:
    """Attempt to locate a figure caption near the image bounding-box.

    Strategy:
    1. Look for text blocks whose vertical centre is just below the image.
    2. Fall back to regex matching ``Figure N: …`` in the full page text.
    """
    best_caption = ""
    best_distance = float("inf")

    for block in page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]:
        if block["type"] != 0:  # only text blocks
            continue
        block_rect = fitz.Rect(block["bbox"])
        # Caption is typically directly below the image
        vertical_gap = block_rect.y0 - image_bbox.y1
        if 0 <= vertical_gap <= 80:  # within 80 pts below
            block_text = " ".join(
                span["text"]
                for line in block["lines"]
                for span in line["spans"]
            ).strip()
            match = _CAPTION_PATTERN.search(block_text)
            if match and vertical_gap < best_distance:
                best_caption = block_text
                best_distance = vertical_gap

    # Fallback: regex on the full page text
    if not best_caption:
        match = _CAPTION_PATTERN.search(page_text)
        if match:
            best_caption = match.group(0).strip()

    return best_caption


def _extract_surrounding_text(page_text: str, max_chars: int = 500) -> str:
    """Return the first ``max_chars`` characters of the page text as context."""
    cleaned = " ".join(page_text.split())
    return cleaned[:max_chars]


# ──────────────────── Core Extraction Logic ──────────────────────────────────

def _chunk_page_text(
    page_text: str,
    source_pdf: str,
    page_number: int,
    max_chunk_size: int = 1000,
) -> list[TextChunk]:
    """Split page text into paragraph-level chunks.

    Paragraphs are identified by double-newline boundaries.  Chunks that are
    shorter than ``MIN_PARAGRAPH_LENGTH`` are merged with the previous chunk to
    avoid noisy micro-fragments.
    """
    raw_paragraphs = re.split(r"\n{2,}", page_text.strip())
    chunks: list[TextChunk] = []
    buffer = ""
    idx = 0

    for para in raw_paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(para) < MIN_PARAGRAPH_LENGTH and buffer:
            buffer += "\n\n" + para
            continue

        if buffer:
            # Flush buffer
            if len(buffer) > max_chunk_size:
                # Split long buffers at sentence boundaries
                sentences = re.split(r"(?<=[.!?])\s+", buffer)
                current = ""
                for sent in sentences:
                    if len(current) + len(sent) > max_chunk_size and current:
                        chunks.append(
                            TextChunk(
                                text=current.strip(),
                                source_pdf=source_pdf,
                                page_number=page_number,
                                chunk_index=idx,
                            )
                        )
                        idx += 1
                        current = sent
                    else:
                        current = current + " " + sent if current else sent
                if current.strip():
                    chunks.append(
                        TextChunk(
                            text=current.strip(),
                            source_pdf=source_pdf,
                            page_number=page_number,
                            chunk_index=idx,
                        )
                    )
                    idx += 1
            else:
                chunks.append(
                    TextChunk(
                        text=buffer.strip(),
                        source_pdf=source_pdf,
                        page_number=page_number,
                        chunk_index=idx,
                    )
                )
                idx += 1
            buffer = ""

        buffer = para

    # Final flush
    if buffer.strip():
        chunks.append(
            TextChunk(
                text=buffer.strip(),
                source_pdf=source_pdf,
                page_number=page_number,
                chunk_index=idx,
            )
        )

    return chunks


def _extract_images_from_page(
    page: fitz.Page,
    doc: fitz.Document,
    page_text: str,
    source_pdf: str,
    page_number: int,
    output_dir: Path,
    global_image_counter: int,
) -> tuple[list[ImageRecord], int]:
    """Extract all embedded images from a single page and save as PNG."""
    records: list[ImageRecord] = []
    image_list = page.get_images(full=True)

    for img_index, img_info in enumerate(image_list):
        xref = img_info[0]
        try:
            base_image = doc.extract_image(xref)
        except Exception as exc:
            logger.warning(
                "Could not extract image xref=%d on page %d of %s: %s",
                xref, page_number, source_pdf, exc,
            )
            continue

        image_bytes = base_image["image"]
        image_ext = base_image.get("ext", "png")

        # Skip tiny images (likely icons / bullets)
        width = base_image.get("width", 0)
        height = base_image.get("height", 0)
        if width < 50 or height < 50:
            logger.debug("Skipping tiny image %dx%d on page %d", width, height, page_number)
            continue

        # Determine a reasonable bounding box for caption search
        img_rects = page.get_image_rects(xref)
        image_bbox = img_rects[0] if img_rects else fitz.Rect(0, 0, width, height)

        # Save as PNG
        filename = f"{Path(source_pdf).stem}_p{page_number}_img{global_image_counter}.png"
        save_path = output_dir / filename

        # If the native format is not PNG, convert via fitz Pixmap
        if image_ext != "png":
            try:
                pix = fitz.Pixmap(image_bytes)
                if pix.alpha:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                pix.save(str(save_path))
            except Exception:
                # Last resort: save with original extension
                save_path = save_path.with_suffix(f".{image_ext}")
                save_path.write_bytes(image_bytes)
        else:
            save_path.write_bytes(image_bytes)

        caption = _find_caption(page_text, image_bbox, page)
        surrounding = _extract_surrounding_text(page_text)

        records.append(
            ImageRecord(
                image_path=str(save_path.resolve()),
                source_pdf=source_pdf,
                page_number=page_number,
                image_index=img_index,
                caption=caption,
                surrounding_text=surrounding,
            )
        )
        global_image_counter += 1

    return records, global_image_counter


# ──────────────────────── Public API ─────────────────────────────────────────

def extract_pdf(
    pdf_path: str | Path,
    image_output_dir: str | Path,
    max_chunk_size: int = 1000,
) -> ExtractionResult:
    """Parse a single PDF into text chunks and extracted images.

    Parameters
    ----------
    pdf_path:
        Path to the PDF file.
    image_output_dir:
        Directory where extracted ``.png`` images will be saved.
    max_chunk_size:
        Maximum character length per text chunk.

    Returns
    -------
    ExtractionResult
        Contains ``text_chunks`` and ``image_records``.
    """
    pdf_path = Path(pdf_path)
    image_output_dir = Path(image_output_dir)
    image_output_dir.mkdir(parents=True, exist_ok=True)

    result = ExtractionResult()
    global_image_counter = 0

    logger.info("Opening PDF: %s", pdf_path)
    doc = fitz.open(str(pdf_path))

    for page_number in range(len(doc)):
        page = doc[page_number]
        page_text = page.get_text("text")

        # ── Text Stream ──────────────────────────────────────────────
        text_chunks = _chunk_page_text(
            page_text,
            source_pdf=pdf_path.name,
            page_number=page_number + 1,  # 1-indexed for readability
            max_chunk_size=max_chunk_size,
        )
        result.text_chunks.extend(text_chunks)

        # ── Image Stream ─────────────────────────────────────────────
        image_records, global_image_counter = _extract_images_from_page(
            page=page,
            doc=doc,
            page_text=page_text,
            source_pdf=pdf_path.name,
            page_number=page_number + 1,
            output_dir=image_output_dir,
            global_image_counter=global_image_counter,
        )
        result.image_records.extend(image_records)

    doc.close()

    logger.info(
        "Extracted %d text chunks and %d images from %s",
        len(result.text_chunks),
        len(result.image_records),
        pdf_path.name,
    )
    return result


def extract_all_pdfs(
    papers_dir: str | Path,
    image_output_dir: str | Path,
    max_chunk_size: int = 1000,
) -> ExtractionResult:
    """Iterate over every PDF in ``papers_dir`` and extract content.

    Parameters
    ----------
    papers_dir:
        Directory containing one or more ``.pdf`` files.
    image_output_dir:
        Directory where all extracted images will be saved.
    max_chunk_size:
        Maximum character length per text chunk.

    Returns
    -------
    ExtractionResult
        Aggregated text chunks and image records from all PDFs.
    """
    papers_dir = Path(papers_dir)
    image_output_dir = Path(image_output_dir)

    pdf_files = sorted(papers_dir.glob("*.pdf"))
    if not pdf_files:
        logger.warning("No PDF files found in %s", papers_dir)
        return ExtractionResult()

    logger.info("Found %d PDF(s) in %s", len(pdf_files), papers_dir)

    combined = ExtractionResult()
    for pdf_file in pdf_files:
        result = extract_pdf(pdf_file, image_output_dir, max_chunk_size)
        combined.text_chunks.extend(result.text_chunks)
        combined.image_records.extend(result.image_records)

    return combined


def save_extraction_metadata(result: ExtractionResult, output_path: str | Path) -> None:
    """Persist extraction metadata as a JSON file for downstream consumers."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "text_chunks": [c.to_dict() for c in result.text_chunks],
        "image_records": [r.to_dict() for r in result.image_records],
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Saved extraction metadata to %s", output_path)
