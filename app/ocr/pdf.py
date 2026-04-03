"""PDF page-splitting utilities for multi-page OCR support.

Uses PyMuPDF (fitz) to render each page of a PDF as a PNG image
so it can be sent to vision-based OCR engines.
"""

import base64
import pathlib

import fitz  # PyMuPDF


def is_pdf(path: pathlib.Path) -> bool:
    return path.suffix.lower() == ".pdf"


def pdf_page_count(file_path: pathlib.Path) -> int:
    with fitz.open(str(file_path)) as doc:
        return len(doc)


def render_pdf_page_to_base64(
    file_path: pathlib.Path,
    page_index: int,
    *,
    dpi: int = 300,
) -> str:
    """Render a single PDF page to a base64-encoded PNG string."""
    with fitz.open(str(file_path)) as doc:
        page = doc[page_index]
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        png_bytes = pix.tobytes("png")
    return base64.b64encode(png_bytes).decode("utf-8")
