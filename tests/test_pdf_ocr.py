"""Tests for multi-page PDF OCR support."""

import base64
import pathlib
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import fitz  # PyMuPDF
import pytest

from app.ocr.base import (
    SUPPORTED_FILE_EXTENSIONS,
    SUPPORTED_IMAGE_EXTENSIONS,
    BaseOCREngine,
    validate_file,
)
from app.ocr.pdf import is_pdf, pdf_page_count, render_pdf_page_to_base64
from app.schemas.ocr import OCRExtractResponse, OCRPageResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_test_pdf(path: pathlib.Path, num_pages: int = 1) -> None:
    """Create a minimal PDF with *num_pages* pages (each has a line of text)."""
    doc = fitz.open()
    for i in range(num_pages):
        page = doc.new_page(width=200, height=200)
        page.insert_text((10, 50), f"Page {i + 1}", fontsize=14)
    doc.save(str(path))
    doc.close()


class _StubOCREngine(BaseOCREngine):
    """Concrete engine used in tests (avoids hitting the real Ollama API)."""

    @property
    def engine_name(self) -> str:
        return "stub-ocr"

    @property
    def model_name(self) -> str:
        return "stub-model"

    @property
    def prompt(self) -> str:
        return "Extract text."

    def _normalize(self, text: str, raw: dict[str, Any], file_path: str) -> dict[str, Any]:
        return {
            "engine": self.engine_name,
            "text": text,
            "layout": {"pages": 1},
            "tables": [],
            "confidence": 0.0,
            "metadata": {
                "model": raw.get("model", self.model_name),
                "total_duration_ns": raw.get("total_duration"),
                "eval_count": raw.get("eval_count"),
                "file_path": file_path,
            },
        }


# ---------------------------------------------------------------------------
# pdf.py unit tests
# ---------------------------------------------------------------------------


class TestIsPdf:
    def test_pdf_extension(self, tmp_path: pathlib.Path) -> None:
        assert is_pdf(tmp_path / "doc.pdf") is True

    def test_pdf_extension_uppercase(self, tmp_path: pathlib.Path) -> None:
        assert is_pdf(tmp_path / "DOC.PDF") is True

    def test_non_pdf_extension(self, tmp_path: pathlib.Path) -> None:
        assert is_pdf(tmp_path / "image.png") is False


class TestPdfPageCount:
    def test_single_page(self, tmp_path: pathlib.Path) -> None:
        pdf = tmp_path / "one.pdf"
        _create_test_pdf(pdf, 1)
        assert pdf_page_count(pdf) == 1

    def test_multi_page(self, tmp_path: pathlib.Path) -> None:
        pdf = tmp_path / "three.pdf"
        _create_test_pdf(pdf, 3)
        assert pdf_page_count(pdf) == 3


class TestRenderPdfPageToBase64:
    def test_returns_valid_base64_png(self, tmp_path: pathlib.Path) -> None:
        pdf = tmp_path / "sample.pdf"
        _create_test_pdf(pdf, 2)
        b64 = render_pdf_page_to_base64(pdf, 0)
        raw = base64.b64decode(b64)
        # PNG magic bytes
        assert raw[:4] == b"\x89PNG"

    def test_each_page_renders(self, tmp_path: pathlib.Path) -> None:
        pdf = tmp_path / "sample.pdf"
        _create_test_pdf(pdf, 2)
        page_0 = render_pdf_page_to_base64(pdf, 0)
        page_1 = render_pdf_page_to_base64(pdf, 1)
        # Pages have different content, so the rendered images should differ
        assert page_0 != page_1


# ---------------------------------------------------------------------------
# validate_file – PDF acceptance
# ---------------------------------------------------------------------------


class TestValidateFilePdf:
    def test_accepts_pdf(self, tmp_path: pathlib.Path) -> None:
        pdf = tmp_path / "test.pdf"
        _create_test_pdf(pdf, 1)
        result = validate_file(str(pdf))
        assert result == pdf

    def test_rejects_unsupported(self, tmp_path: pathlib.Path) -> None:
        txt = tmp_path / "test.txt"
        txt.write_text("hello")
        with pytest.raises(ValueError, match="Unsupported file extension"):
            validate_file(str(txt))


class TestSupportedExtensions:
    def test_pdf_in_supported_file_extensions(self) -> None:
        assert ".pdf" in SUPPORTED_FILE_EXTENSIONS

    def test_image_extensions_unchanged(self) -> None:
        assert SUPPORTED_IMAGE_EXTENSIONS == frozenset({".png", ".jpg", ".jpeg", ".webp"})


# ---------------------------------------------------------------------------
# BaseOCREngine – single-image backward compat
# ---------------------------------------------------------------------------


class TestExtractSingleImage:
    async def test_single_image_unchanged(self, tmp_path: pathlib.Path) -> None:
        """Single-image extraction still works and does NOT populate pages."""
        img = tmp_path / "img.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)

        engine = _StubOCREngine()

        mock_response = MagicMock()
        mock_response.is_error = False
        mock_response.json.return_value = {
            "model": "stub-model",
            "response": "Hello world",
            "total_duration": 100,
            "eval_count": 5,
        }

        with patch("app.ocr.base.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await engine.extract(str(img))

        assert result["engine"] == "stub-ocr"
        assert result["text"] == "Hello world"
        assert result["layout"]["pages"] == 1
        # Single images do not set a "pages" key
        assert "pages" not in result


# ---------------------------------------------------------------------------
# BaseOCREngine – multi-page PDF extraction
# ---------------------------------------------------------------------------


class TestExtractPdf:
    async def test_multi_page_extraction(self, tmp_path: pathlib.Path) -> None:
        pdf = tmp_path / "doc.pdf"
        _create_test_pdf(pdf, 3)

        engine = _StubOCREngine()
        call_count = 0

        def _make_response(page_text: str) -> MagicMock:
            resp = MagicMock()
            resp.is_error = False
            resp.json.return_value = {
                "model": "stub-model",
                "response": page_text,
                "total_duration": 100,
                "eval_count": 10,
            }
            return resp

        async def _fake_post(url: str, json: dict) -> MagicMock:
            nonlocal call_count
            call_count += 1
            return _make_response(f"Text from page {call_count}")

        with patch("app.ocr.base.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = _fake_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await engine.extract(str(pdf))

        # Combined text from all pages
        assert "Text from page 1" in result["text"]
        assert "Text from page 2" in result["text"]
        assert "Text from page 3" in result["text"]

        # Layout reports correct page count
        assert result["layout"]["pages"] == 3

        # Per-page results
        assert len(result["pages"]) == 3
        assert result["pages"][0]["page"] == 1
        assert result["pages"][0]["text"] == "Text from page 1"
        assert result["pages"][2]["page"] == 3
        assert result["pages"][2]["text"] == "Text from page 3"

        # Ollama was called once per page
        assert call_count == 3

    async def test_single_page_pdf(self, tmp_path: pathlib.Path) -> None:
        pdf = tmp_path / "single.pdf"
        _create_test_pdf(pdf, 1)

        engine = _StubOCREngine()

        mock_response = MagicMock()
        mock_response.is_error = False
        mock_response.json.return_value = {
            "model": "stub-model",
            "response": "Only page",
            "total_duration": 50,
            "eval_count": 2,
        }

        with patch("app.ocr.base.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await engine.extract(str(pdf))

        assert result["text"] == "Only page"
        assert result["layout"]["pages"] == 1
        assert len(result["pages"]) == 1
        assert result["pages"][0]["text"] == "Only page"


# ---------------------------------------------------------------------------
# Schema – OCRPageResult & OCRExtractResponse.pages
# ---------------------------------------------------------------------------


class TestOCRPageResultSchema:
    def test_defaults(self) -> None:
        pr = OCRPageResult(page=1, text="hello")
        assert pr.confidence == 0.0
        assert pr.metadata == {}

    def test_explicit_values(self) -> None:
        pr = OCRPageResult(page=2, text="x", confidence=0.95, metadata={"k": "v"})
        assert pr.page == 2
        assert pr.confidence == 0.95


class TestOCRExtractResponsePages:
    def test_pages_default_empty(self) -> None:
        resp = OCRExtractResponse(
            engine="e",
            text="t",
            normalized_text="t",
            normalization={
                "removed_blank_lines": 0,
                "collapsed_whitespace": False,
                "merged_broken_lines": False,
                "cleaned_hyphenation": False,
            },
            structured={},
            layout={},
            tables=[],
            confidence=0.0,
            metadata={},
        )
        assert resp.pages == []

    def test_pages_populated(self) -> None:
        resp = OCRExtractResponse(
            engine="e",
            text="combined",
            normalized_text="combined",
            normalization={
                "removed_blank_lines": 0,
                "collapsed_whitespace": False,
                "merged_broken_lines": False,
                "cleaned_hyphenation": False,
            },
            structured={},
            layout={"pages": 2},
            tables=[],
            confidence=0.0,
            metadata={},
            pages=[
                {"page": 1, "text": "p1"},
                {"page": 2, "text": "p2"},
            ],
        )
        assert len(resp.pages) == 2
        assert resp.pages[0].page == 1
