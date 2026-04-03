import pytest

from app.services.chunking import chunk_for_retrieval


class TestChunkForRetrieval:
    def test_empty_text_returns_empty(self) -> None:
        assert chunk_for_retrieval("") == []
        assert chunk_for_retrieval("   ") == []

    def test_short_text_returns_single_chunk(self) -> None:
        text = "Hello world.\n\nThis is a document."
        chunks = chunk_for_retrieval(text, max_chars=2000)
        assert len(chunks) == 1
        assert "Hello world." in chunks[0]
        assert "This is a document." in chunks[0]

    def test_long_text_splits_into_multiple_chunks(self) -> None:
        paragraphs = [f"Paragraph {i}. " + ("x" * 100) for i in range(20)]
        text = "\n\n".join(paragraphs)
        chunks = chunk_for_retrieval(text, max_chars=500, overlap_chars=50)
        assert len(chunks) > 1

    def test_chunks_are_deterministic(self) -> None:
        text = "\n\n".join([f"Section {i} content here." for i in range(10)])
        a = chunk_for_retrieval(text, max_chars=100, overlap_chars=20)
        b = chunk_for_retrieval(text, max_chars=100, overlap_chars=20)
        assert a == b

    def test_preserves_paragraph_boundaries(self) -> None:
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        chunks = chunk_for_retrieval(text, max_chars=5000)
        assert len(chunks) == 1
        assert "\n\n" in chunks[0]
