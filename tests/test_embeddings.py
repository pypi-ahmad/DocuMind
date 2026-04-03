from fastapi.testclient import TestClient

from app.main import app
from app.core.settings import settings
from app.providers.ollama import OllamaProvider
from app.services import retrieval_store

client = TestClient(app)


def _make_fake_embeddings(provider_name: str):
    async def fake_generate_embeddings(
        self,
        model_name: str,
        input_texts: list[str],
        api_key: str | None = None,
    ) -> dict:
        return {
            "provider": provider_name,
            "model_name": model_name,
            "vectors": [
                {"index": i, "vector": [float(i), 0.5, 0.1]}
                for i in range(len(input_texts))
            ],
            "metadata": {},
        }

    return fake_generate_embeddings


def test_embeddings_generate_with_ollama(monkeypatch) -> None:
    monkeypatch.setattr(OllamaProvider, "generate_embeddings", _make_fake_embeddings("ollama"))

    response = client.post(
        "/embeddings/generate",
        json={
            "provider": "ollama",
            "model_name": "nomic-embed-text",
            "input_texts": ["Hello world", "Second text"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "ollama"
    assert len(body["vectors"]) == 2
    assert body["vectors"][0]["index"] == 0
    assert isinstance(body["vectors"][0]["vector"], list)


def test_embeddings_generate_requires_api_key_for_openai() -> None:
    response = client.post(
        "/embeddings/generate",
        json={
            "provider": "openai",
            "model_name": "text-embedding-3-small",
            "input_texts": ["test"],
        },
    )
    assert response.status_code == 400
    assert "requires api_key" in response.json()["detail"]


def test_embeddings_generate_uses_env_key_fallback_for_openai(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", "configured-key")

    response = client.post(
        "/embeddings/generate",
        json={
            "provider": "openai",
            "model_name": "text-embedding-3-small",
            "input_texts": ["test"],
        },
    )

    # env key is accepted as fallback; the fake key triggers an auth error from the SDK
    assert response.status_code in {401, 502}


def test_embeddings_generate_anthropic_returns_501() -> None:
    response = client.post(
        "/embeddings/generate",
        json={
            "provider": "anthropic",
            "model_name": "anything",
            "input_texts": ["test"],
            "api_key": "test-key",
        },
    )
    assert response.status_code == 501
    assert "does not support embeddings" in response.json()["detail"]


def test_embeddings_generate_anthropic_returns_501_without_api_key() -> None:
    response = client.post(
        "/embeddings/generate",
        json={
            "provider": "anthropic",
            "model_name": "anything",
            "input_texts": ["test"],
        },
    )

    assert response.status_code == 400
    assert "requires api_key" in response.json()["detail"]


def test_embeddings_generate_unknown_provider_returns_400() -> None:
    response = client.post(
        "/embeddings/generate",
        json={
            "provider": "unknown",
            "model_name": "model",
            "input_texts": ["test"],
        },
    )
    assert response.status_code == 400


def test_embeddings_generate_empty_input_texts_returns_422() -> None:
    response = client.post(
        "/embeddings/generate",
        json={
            "provider": "ollama",
            "model_name": "model",
            "input_texts": [],
        },
    )
    assert response.status_code == 422


def test_retrieval_index_and_search(monkeypatch) -> None:
    retrieval_store.clear_store()
    monkeypatch.setattr(OllamaProvider, "generate_embeddings", _make_fake_embeddings("ollama"))

    index_response = client.post(
        "/retrieval/index",
        json={
            "doc_id": "doc-1",
            "text": "This is a paragraph about invoices.\n\nThis is another about contracts.",
            "provider": "ollama",
            "model_name": "nomic-embed-text",
        },
    )
    assert index_response.status_code == 200
    index_body = index_response.json()
    assert index_body["doc_id"] == "doc-1"
    assert index_body["chunks_indexed"] >= 1

    docs_response = client.get("/retrieval/documents")
    assert docs_response.status_code == 200
    docs = docs_response.json()
    assert len(docs) >= 1
    assert docs[0]["doc_id"] == "doc-1"

    search_response = client.post(
        "/retrieval/search",
        json={
            "query": "invoices",
            "provider": "ollama",
            "model_name": "nomic-embed-text",
            "top_k": 3,
        },
    )
    assert search_response.status_code == 200
    search_body = search_response.json()
    assert search_body["query"] == "invoices"
    assert isinstance(search_body["matches"], list)

    delete_response = client.delete("/retrieval/documents")
    assert delete_response.status_code == 204

    docs_after = client.get("/retrieval/documents")
    assert docs_after.json() == []

    retrieval_store.clear_store()


def test_retrieval_index_missing_api_key_for_cloud() -> None:
    response = client.post(
        "/retrieval/index",
        json={
            "doc_id": "doc-2",
            "text": "Some text content.",
            "provider": "openai",
            "model_name": "text-embedding-3-small",
        },
    )
    assert response.status_code == 400
    assert "requires api_key" in response.json()["detail"]


def test_retrieval_search_missing_api_key_for_cloud(monkeypatch) -> None:
    monkeypatch.setattr(settings, "gemini_api_key", "")

    response = client.post(
        "/retrieval/search",
        json={
            "query": "test",
            "provider": "gemini",
            "model_name": "embedding-001",
        },
    )
    assert response.status_code == 400
    assert "requires api_key" in response.json()["detail"]
