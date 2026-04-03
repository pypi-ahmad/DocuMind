import pytest

from app.services.retrieval_store import add_documents, clear_store, list_documents, search


@pytest.fixture(autouse=True)
def _clean_store():
    clear_store()
    yield
    clear_store()


class TestRetrievalStore:
    def test_add_and_list_documents(self) -> None:
        records = [
            {"doc_id": "d1", "chunk_id": "d1:0", "text": "hello", "vector": [1.0, 0.0, 0.0], "metadata": {}},
            {"doc_id": "d1", "chunk_id": "d1:1", "text": "world", "vector": [0.0, 1.0, 0.0], "metadata": {}},
        ]
        count = add_documents(records)
        assert count == 2

        docs = list_documents()
        assert len(docs) == 1
        assert docs[0]["doc_id"] == "d1"
        assert docs[0]["chunk_count"] == 2

    def test_search_returns_sorted_by_similarity(self) -> None:
        records = [
            {"doc_id": "d1", "chunk_id": "d1:0", "text": "hello", "vector": [1.0, 0.0, 0.0], "metadata": {}},
            {"doc_id": "d1", "chunk_id": "d1:1", "text": "world", "vector": [0.0, 1.0, 0.0], "metadata": {}},
            {"doc_id": "d2", "chunk_id": "d2:0", "text": "mixed", "vector": [0.7, 0.7, 0.0], "metadata": {}},
        ]
        add_documents(records)

        results = search([1.0, 0.0, 0.0], top_k=3)
        assert len(results) == 3
        assert results[0]["chunk_id"] == "d1:0"
        assert results[0]["score"] == 1.0

    def test_search_empty_store_returns_empty(self) -> None:
        results = search([1.0, 0.0], top_k=5)
        assert results == []

    def test_search_respects_top_k(self) -> None:
        records = [
            {"doc_id": "d1", "chunk_id": f"d1:{i}", "text": f"text{i}", "vector": [float(i), 1.0], "metadata": {}}
            for i in range(10)
        ]
        add_documents(records)

        results = search([1.0, 0.0], top_k=3)
        assert len(results) == 3

    def test_clear_store_empties_everything(self) -> None:
        add_documents([{"doc_id": "d1", "chunk_id": "d1:0", "text": "t", "vector": [1.0], "metadata": {}}])
        clear_store()
        assert list_documents() == []
        assert search([1.0], top_k=5) == []
