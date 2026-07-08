"""
generate_sample_data.py
========================
Creates a sample clinical PDF (with text + an embedded diagram) inside
``data/papers/`` so the extraction pipeline can be tested end-to-end
without requiring a real research paper.

Run once:  python generate_sample_data.py
"""

from pathlib import Path
import fitz  # PyMuPDF

PROJECT_ROOT = Path(__file__).resolve().parent
PAPERS_DIR = PROJECT_ROOT / "data" / "papers"
PAPERS_DIR.mkdir(parents=True, exist_ok=True)


def _create_pathway_diagram(width: int = 480, height: int = 320) -> bytes:
    """Draw a simple MAPK/ERK signaling pathway diagram and return PNG bytes."""
    # Create a temporary PDF page to use as a drawing canvas
    tmp_doc = fitz.open()
    page = tmp_doc.new_page(width=width, height=height)
    shape = page.new_shape()

    # ── Background ──
    shape.draw_rect(fitz.Rect(0, 0, width, height))
    shape.finish(fill=(0.96, 0.97, 1.0), color=(0.7, 0.75, 0.85), width=2)

    # Title
    page.insert_text(
        fitz.Point(100, 30),
        "MAPK/ERK Signaling Pathway",
        fontsize=14,
        fontname="helv",
        color=(0.15, 0.15, 0.4),
    )

    # ── Nodes ──
    nodes = [
        ("Growth Factor", 190, 60, (0.2, 0.6, 0.9)),
        ("RAS", 210, 110, (0.9, 0.4, 0.3)),
        ("RAF", 210, 160, (0.9, 0.55, 0.2)),
        ("MEK1/2", 200, 210, (0.3, 0.7, 0.4)),
        ("ERK1/2", 200, 260, (0.6, 0.3, 0.7)),
    ]
    for label, x, y, color in nodes:
        rect = fitz.Rect(x - 50, y - 12, x + 50, y + 12)
        shape.draw_rect(rect)
        shape.finish(fill=color, color=(0.2, 0.2, 0.2), width=1)
        page.insert_text(
            fitz.Point(x - len(label) * 3.2, y + 4),
            label,
            fontsize=10,
            fontname="helv",
            color=(1, 1, 1),
        )

    # ── Arrows ──
    arrow_pairs = [(80, 98), (130, 148), (180, 198), (230, 248)]
    for y_start, y_end in arrow_pairs:
        shape.draw_line(fitz.Point(220, y_start), fitz.Point(220, y_end))
        shape.finish(color=(0.3, 0.3, 0.3), width=1.5)
        # arrowhead
        shape.draw_line(fitz.Point(215, y_end - 6), fitz.Point(220, y_end))
        shape.draw_line(fitz.Point(225, y_end - 6), fitz.Point(220, y_end))
        shape.finish(color=(0.3, 0.3, 0.3), width=1.5)

    # Outcome annotations
    page.insert_text(
        fitz.Point(290, 265),
        "→ Cell Proliferation\n→ Differentiation\n→ Survival",
        fontsize=9,
        fontname="helv",
        color=(0.1, 0.5, 0.1),
    )

    # Inhibitor annotation
    page.insert_text(
        fitz.Point(20, 170),
        "Sorafenib ⊣",
        fontsize=9,
        fontname="helv",
        color=(0.8, 0.1, 0.1),
    )

    shape.commit()

    # Render page to PNG
    pix = page.get_pixmap(dpi=150)
    png_bytes = pix.tobytes("png")
    tmp_doc.close()
    return png_bytes


def create_sample_pdf() -> Path:
    """Build a multi-page sample clinical PDF with text and an embedded diagram."""
    doc = fitz.open()

    # ── Page 1: Abstract & Introduction ──────────────────────────────────
    p1 = doc.new_page(width=612, height=792)
    p1.insert_text(
        fitz.Point(72, 60),
        "Mutations in the MAPK/ERK Pathway and Their Impact on\n"
        "Downstream Enzyme Production: A Clinical Review",
        fontsize=16,
        fontname="helv",
        color=(0.1, 0.1, 0.3),
    )

    abstract = (
        "Abstract\n\n"
        "The MAPK/ERK signaling cascade is a critical pathway regulating cell "
        "proliferation, differentiation, and survival. Aberrant activation of "
        "this pathway — frequently driven by gain-of-function mutations in "
        "BRAF (V600E) and KRAS (G12V) — is implicated in approximately 30% of "
        "all human cancers. This review examines how specific point mutations "
        "alter kinase activity at each tier of the cascade (RAS → RAF → MEK → ERK) "
        "and quantify the downstream impact on transcription-factor phosphorylation "
        "and enzyme production.\n\n"
        "Introduction\n\n"
        "Receptor tyrosine kinases (RTKs) such as EGFR and FGFR activate RAS "
        "GTPases upon ligand binding. RAS-GTP recruits RAF kinases to the plasma "
        "membrane, initiating a phosphorylation cascade through MEK1/2 and ERK1/2. "
        "Activated ERK translocates to the nucleus where it phosphorylates "
        "transcription factors including ELK1, c-MYC, and RSK, ultimately driving "
        "the expression of genes encoding metabolic enzymes such as HK2 (hexokinase 2) "
        "and LDHA (lactate dehydrogenase A).\n\n"
        "Dysregulation of this cascade — whether through constitutive RAS activation, "
        "BRAF V600E mutation, or loss of negative regulators like DUSP6 — leads to "
        "uncontrolled enzyme production and metabolic reprogramming, hallmarks of the "
        "Warburg effect in cancer cells."
    )
    p1.insert_text(fitz.Point(72, 110), abstract, fontsize=10, fontname="helv")

    # ── Page 2: Pathway Diagram + Caption ────────────────────────────────
    p2 = doc.new_page(width=612, height=792)

    p2.insert_text(
        fitz.Point(72, 50),
        "Results\n\n"
        "Figure 1 illustrates the canonical MAPK/ERK signaling pathway. "
        "Sorafenib, a multi-kinase inhibitor, targets RAF and blocks downstream "
        "signal transduction. Quantitative proteomics data revealed that "
        "BRAF V600E mutant cell lines exhibit a 4.7-fold increase in phospho-ERK "
        "levels compared to wild-type controls (p < 0.001). This hyper-activation "
        "correlated with a 3.2-fold upregulation of HK2 mRNA and a 2.8-fold "
        "increase in LDHA protein expression.",
        fontsize=10,
        fontname="helv",
    )

    # Embed diagram image
    diagram_png = _create_pathway_diagram()
    img_rect = fitz.Rect(66, 200, 546, 520)
    p2.insert_image(img_rect, stream=diagram_png)

    # Caption below image
    p2.insert_text(
        fitz.Point(72, 545),
        "Figure 1: The MAPK/ERK signaling cascade. Growth factor binding activates "
        "RAS, which recruits RAF to initiate sequential phosphorylation of MEK1/2 "
        "and ERK1/2. Sorafenib inhibits RAF. Downstream outputs include cell "
        "proliferation, differentiation, and survival.",
        fontsize=9,
        fontname="helv",
        color=(0.3, 0.3, 0.3),
    )

    # ── Page 3: Discussion & Conclusions ─────────────────────────────────
    p3 = doc.new_page(width=612, height=792)

    discussion = (
        "Discussion\n\n"
        "Our analysis demonstrates that mutations at the RAS and RAF tiers of the "
        "MAPK/ERK pathway have a cascading impact on downstream enzyme production. "
        "The BRAF V600E mutation — the most prevalent oncogenic BRAF alteration — "
        "bypasses the requirement for RAS-GTP and constitutively activates MEK/ERK "
        "signaling. This results in sustained phosphorylation of nuclear targets "
        "and over-expression of glycolytic enzymes (HK2, LDHA, PKM2).\n\n"
        "Importantly, MEK inhibitors (trametinib, cobimetinib) and ERK inhibitors "
        "(ulixertinib) can partially restore normal enzyme levels in BRAF-mutant "
        "cell lines, suggesting that therapeutic intervention at multiple cascade "
        "nodes may be required for effective metabolic normalization.\n\n"
        "Conclusions\n\n"
        "Gain-of-function mutations in BRAF and KRAS significantly amplify "
        "downstream kinase signaling, resulting in aberrant enzyme production and "
        "metabolic reprogramming. Combination therapy targeting multiple tiers of "
        "the cascade represents a promising strategy for restoring metabolic "
        "homeostasis in MAPK-driven cancers.\n\n"
        "References\n\n"
        "1. Davies H et al. (2002) Mutations of the BRAF gene in human cancer. Nature.\n"
        "2. Dhillon AS et al. (2007) MAP kinase signalling pathways in cancer. Oncogene.\n"
        "3. Samatar AA, Poulikakos PI (2014) Targeting RAS-ERK signalling in cancer. "
        "Nature Reviews Drug Discovery."
    )
    p3.insert_text(fitz.Point(72, 60), discussion, fontsize=10, fontname="helv")

    # ── Save ─────────────────────────────────────────────────────────────
    output_path = PAPERS_DIR / "sample_mapk_clinical_review.pdf"
    doc.save(str(output_path))
    doc.close()

    print(f"[OK] Sample PDF created: {output_path}")
    return output_path


if __name__ == "__main__":
    create_sample_pdf()
