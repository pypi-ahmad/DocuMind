"""Tests verifying backend response shapes match FormattedResult.tsx type detectors.

The frontend FormattedResult component uses shape-based detection to decide
how to render results.  These tests ensure the backend Pydantic models
produce JSON that the frontend detectors will match correctly.
"""

from app.schemas.ocr import (
    OCRExtractResponse,
    OCRNormalizationSummary,
    OCRPostProcessResponse,
)
from app.schemas.llm import LLMGenerateResponse
from app.schemas.retrieval import DocumentQACitation, DocumentQAResponse, OCRIndexResponse


class TestOCRExtractShape:
    """isOCRExtractResponse: checks for 'text' + ('normalization' | 'pages')."""

    def test_has_text_and_normalization(self) -> None:
        resp = OCRExtractResponse(
            engine="tesseract",
            text="Hello world",
            normalized_text="Hello world",
            normalization=OCRNormalizationSummary(
                removed_blank_lines=0,
                collapsed_whitespace=False,
                merged_broken_lines=False,
                cleaned_hyphenation=False,
            ),
            structured={},
            layout={},
            tables=[],
            confidence=0.95,
            metadata={},
        )
        data = resp.model_dump()
        assert isinstance(data["text"], str)
        assert "normalization" in data

    def test_has_pages_key(self) -> None:
        resp = OCRExtractResponse(
            engine="tesseract",
            text="page text",
            normalized_text="page text",
            normalization=OCRNormalizationSummary(
                removed_blank_lines=0,
                collapsed_whitespace=False,
                merged_broken_lines=False,
                cleaned_hyphenation=False,
            ),
            structured={},
            layout={},
            tables=[],
            confidence=0.9,
            metadata={},
            pages=[],
        )
        data = resp.model_dump()
        assert "pages" in data


class TestQAAnswerShape:
    """isAnswerResponse: checks for 'answer'.  Frontend reads 'citations' ?? 'sources'."""

    def test_has_answer_field(self) -> None:
        resp = DocumentQAResponse(
            query="What is this?",
            answer="This is a test.",
            citations=[],
            retrieval_mode="hybrid",
            used_rerank=False,
        )
        data = resp.model_dump()
        assert isinstance(data["answer"], str)

    def test_citations_key_present(self) -> None:
        """Frontend uses value.citations ?? value.sources — 'citations' must exist."""
        resp = DocumentQAResponse(
            query="q",
            answer="a",
            citations=[
                DocumentQACitation(
                    doc_id="d1", chunk_id="c1", text="excerpt", metadata={}
                )
            ],
            retrieval_mode="hybrid",
            used_rerank=True,
        )
        data = resp.model_dump()
        assert "citations" in data
        assert isinstance(data["citations"], list)
        assert len(data["citations"]) == 1

    def test_citation_item_has_expected_fields(self) -> None:
        """Frontend reads doc_id, chunk_id, text, score from each citation."""
        citation = DocumentQACitation(
            doc_id="d1", chunk_id="c1", text="some text", metadata={}
        )
        data = citation.model_dump()
        assert "doc_id" in data
        assert "chunk_id" in data
        assert "text" in data


class TestPostProcessShape:
    """isOutputTextResponse: checks for 'output_text'."""

    def test_summary_has_output_text(self) -> None:
        resp = OCRPostProcessResponse(
            task="summary",
            provider="ollama",
            model_name="llama3",
            output_text="This document is about...",
        )
        data = resp.model_dump()
        assert isinstance(data["output_text"], str)
        # Must NOT have 'text' at top level (that would be caught by isTextResponse)
        assert "text" not in data

    def test_key_fields_has_output_text(self) -> None:
        resp = OCRPostProcessResponse(
            task="extract_key_fields",
            provider="ollama",
            model_name="llama3",
            output_text="Name: John\nDate: 2024-01-01",
        )
        data = resp.model_dump()
        assert isinstance(data["output_text"], str)

    def test_cleanup_has_output_text(self) -> None:
        resp = OCRPostProcessResponse(
            task="cleanup",
            provider="openai",
            model_name="gpt-4o",
            output_text="Cleaned text here",
        )
        data = resp.model_dump()
        assert isinstance(data["output_text"], str)


class TestShapeDisambiguation:
    """Verify that response shapes don't accidentally match the wrong detector."""

    def test_ocr_extract_is_not_plain_text(self) -> None:
        """OCR extract has 'text' + 'normalization' — must be caught by isOCRExtract, not isText."""
        resp = OCRExtractResponse(
            engine="tesseract",
            text="hi",
            normalized_text="hi",
            normalization=OCRNormalizationSummary(
                removed_blank_lines=0,
                collapsed_whitespace=False,
                merged_broken_lines=False,
                cleaned_hyphenation=False,
            ),
            structured={},
            layout={},
            tables=[],
            confidence=0.9,
            metadata={},
        )
        data = resp.model_dump()
        # Has 'text' AND 'normalization' → should match OCR extract, not generic text
        assert "text" in data and "normalization" in data

    def test_postprocess_does_not_have_text_key(self) -> None:
        """Postprocess uses 'output_text', not 'text' — avoids isTextResponse match."""
        resp = OCRPostProcessResponse(
            task="summary",
            provider="ollama",
            model_name="llama3",
            output_text="summary content",
        )
        data = resp.model_dump()
        assert "output_text" in data
        assert "text" not in data

    def test_qa_does_not_have_text_key(self) -> None:
        """QA uses 'answer', not 'text' — avoids isTextResponse match."""
        resp = DocumentQAResponse(
            query="q",
            answer="a",
            citations=[],
            retrieval_mode="hybrid",
            used_rerank=False,
        )
        data = resp.model_dump()
        assert "answer" in data
        assert "text" not in data


class TestLLMGenerateShape:
    """isTextResponse: checks for 'text' without 'normalization'/'pages'."""

    def test_has_text_field(self) -> None:
        resp = LLMGenerateResponse(
            provider="ollama", model_name="llama3", text="Generated output"
        )
        data = resp.model_dump()
        assert isinstance(data["text"], str)

    def test_no_normalization_or_pages(self) -> None:
        """LLM generate must NOT have normalization/pages (would trigger OCR detector)."""
        resp = LLMGenerateResponse(
            provider="ollama", model_name="llama3", text="Generated output"
        )
        data = resp.model_dump()
        assert "normalization" not in data
        assert "pages" not in data


class TestIndexResponseFallsToJson:
    """Index responses have no text/answer/output_text — must fall through to JSON."""

    def test_index_response_has_no_text_keys(self) -> None:
        resp = OCRIndexResponse(
            doc_id="d1",
            ocr_engine="tesseract",
            indexed_chunk_count=5,
            indexed_text_length=1000,
            retrieval_text_source="normalized_text",
        )
        data = resp.model_dump()
        assert "text" not in data
        assert "answer" not in data
        assert "output_text" not in data
        assert "key_fields" not in data
