from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.main import app
from app.services.reranker import _parse_rerank_score, build_rerank_prompt

client = TestClient(app)


# --- Unit tests for build_rerank_prompt ---


def test_build_rerank_prompt_includes_query_and_text() -> None:
    prompt = build_rerank_prompt("what is revenue?", {"text": "Revenue was $10M", "metadata": {}})
    assert "what is revenue?" in prompt
    assert "Revenue was $10M" in prompt
    assert "Relevance score:" in prompt


def test_build_rerank_prompt_includes_metadata_when_present() -> None:
    hit = {"text": "chunk text", "metadata": {"doc_id": "abc", "page": 3}}
    prompt = build_rerank_prompt("query", hit)
    assert "doc_id: abc" in prompt
    assert "page: 3" in prompt


def test_build_rerank_prompt_omits_metadata_when_empty() -> None:
    prompt = build_rerank_prompt("query", {"text": "chunk", "metadata": {}})
    assert "Chunk metadata" not in prompt


def test_build_rerank_prompt_grounding_rules() -> None:
    prompt = build_rerank_prompt("query", {"text": "chunk"})
    assert "Do NOT answer the query" in prompt
    assert "Do NOT invent" in prompt
    assert "single numeric score between 0 and 1" in prompt


# --- Unit tests for _parse_rerank_score ---


def test_parse_rerank_score_valid_float() -> None:
    assert _parse_rerank_score("0.85") == 0.85


def test_parse_rerank_score_zero() -> None:
    assert _parse_rerank_score("0") == 0.0


def test_parse_rerank_score_one() -> None:
    assert _parse_rerank_score("1") == 1.0


def test_parse_rerank_score_with_surrounding_text() -> None:
    assert _parse_rerank_score("The relevance score is 0.72.") == 0.72


def test_parse_rerank_score_garbage_returns_zero() -> None:
    assert _parse_rerank_score("I cannot score this") == 0.0


def test_parse_rerank_score_empty_returns_zero() -> None:
    assert _parse_rerank_score("") == 0.0


def test_parse_rerank_score_clamps_to_one() -> None:
    assert _parse_rerank_score("1.0") == 1.0


# --- Route validation tests ---


def test_rerank_empty_query_returns_400() -> None:
    response = client.post(
        "/retrieval/rerank",
        json={
            "query": "   ",
            "hits": [{"text": "chunk", "score": 0.5}],
            "provider": "ollama",
            "model_name": "test",
        },
    )
    assert response.status_code == 400
    assert "query must not be empty" in response.json()["detail"]


def test_rerank_empty_hits_returns_400() -> None:
    response = client.post(
        "/retrieval/rerank",
        json={
            "query": "what is revenue?",
            "hits": [],
            "provider": "ollama",
            "model_name": "test",
        },
    )
    assert response.status_code == 400
    assert "hits must not be empty" in response.json()["detail"]


def test_rerank_invalid_top_k_returns_400() -> None:
    response = client.post(
        "/retrieval/rerank",
        json={
            "query": "what is revenue?",
            "hits": [{"text": "chunk", "score": 0.5}],
            "provider": "ollama",
            "model_name": "test",
            "top_k": 0,
        },
    )
    assert response.status_code == 400
    assert "top_k must be greater than 0" in response.json()["detail"]


def test_rerank_unknown_provider_returns_400() -> None:
    response = client.post(
        "/retrieval/rerank",
        json={
            "query": "what is revenue?",
            "hits": [{"text": "chunk", "score": 0.5}],
            "provider": "nonexistent",
            "model_name": "test",
        },
    )
    assert response.status_code == 400
    assert "Unknown provider" in response.json()["detail"]


def test_rerank_cloud_provider_without_key_returns_400() -> None:
    response = client.post(
        "/retrieval/rerank",
        json={
            "query": "what is revenue?",
            "hits": [{"text": "chunk", "score": 0.5}],
            "provider": "openai",
            "model_name": "gpt-4",
        },
    )
    assert response.status_code == 400
    assert "requires api_key" in response.json()["detail"]


# --- Integration tests with mocked provider ---


def test_rerank_with_ollama_returns_scored_hits(monkeypatch) -> None:
    from app.core.model_manager import model_manager
    from app.providers.ollama import OllamaProvider

    async def fake_activate(provider: str, model_name: str) -> dict:
        return {}

    monkeypatch.setattr(model_manager, "activate", fake_activate)
    monkeypatch.setattr(model_manager, "mark_busy", lambda: None)
    monkeypatch.setattr(model_manager, "mark_idle", lambda: None)

    async def fake_generate_text(self, model_name, prompt, api_key=None, temperature=None, max_output_tokens=None):
        return {"provider": "ollama", "model_name": model_name, "text": "0.9", "usage": {}, "metadata": {}}

    monkeypatch.setattr(OllamaProvider, "generate_text", fake_generate_text)

    response = client.post(
        "/retrieval/rerank",
        json={
            "query": "total revenue",
            "hits": [
                {"doc_id": "d1", "chunk_id": "c1", "text": "Revenue was $10M", "score": 0.8, "metadata": {}},
                {"doc_id": "d1", "chunk_id": "c2", "text": "Weather in NYC", "score": 0.6, "metadata": {}},
            ],
            "provider": "ollama",
            "model_name": "llama3",
            "top_k": 2,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "total revenue"
    assert len(data["hits"]) == 2

    first_hit = data["hits"][0]
    assert first_hit["original_score"] == 0.8
    assert first_hit["rerank_score"] == 0.9
    assert first_hit["final_score"] == round(0.5 * 0.8 + 0.5 * 0.9, 6)
    assert "provider" in data["metadata"]
    assert data["metadata"]["candidates"] == 2
    assert data["metadata"]["returned"] == 2


def test_rerank_top_k_limits_output(monkeypatch) -> None:
    from app.core.model_manager import model_manager
    from app.providers.ollama import OllamaProvider

    monkeypatch.setattr(model_manager, "activate", AsyncMock(return_value={}))
    monkeypatch.setattr(model_manager, "mark_busy", lambda: None)
    monkeypatch.setattr(model_manager, "mark_idle", lambda: None)

    async def fake_generate_text(self, model_name, prompt, api_key=None, temperature=None, max_output_tokens=None):
        return {"provider": "ollama", "model_name": model_name, "text": "0.5", "usage": {}, "metadata": {}}

    monkeypatch.setattr(OllamaProvider, "generate_text", fake_generate_text)

    hits = [
        {"doc_id": "d1", "chunk_id": f"c{i}", "text": f"chunk {i}", "score": 0.5, "metadata": {}}
        for i in range(5)
    ]
    response = client.post(
        "/retrieval/rerank",
        json={
            "query": "revenue",
            "hits": hits,
            "provider": "ollama",
            "model_name": "llama3",
            "top_k": 2,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["hits"]) == 2
    assert data["metadata"]["candidates"] == 5
    assert data["metadata"]["returned"] == 2


def test_rerank_failed_hit_gets_zero_score(monkeypatch) -> None:
    from app.core.model_manager import model_manager
    from app.providers.ollama import OllamaProvider

    monkeypatch.setattr(model_manager, "activate", AsyncMock(return_value={}))
    monkeypatch.setattr(model_manager, "mark_busy", lambda: None)
    monkeypatch.setattr(model_manager, "mark_idle", lambda: None)

    call_count = 0

    async def fake_generate_text(self, model_name, prompt, api_key=None, temperature=None, max_output_tokens=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("LLM error")
        return {"provider": "ollama", "model_name": model_name, "text": "0.7", "usage": {}, "metadata": {}}

    monkeypatch.setattr(OllamaProvider, "generate_text", fake_generate_text)

    response = client.post(
        "/retrieval/rerank",
        json={
            "query": "revenue",
            "hits": [
                {"doc_id": "d1", "chunk_id": "c1", "text": "fails", "score": 0.8, "metadata": {}},
                {"doc_id": "d1", "chunk_id": "c2", "text": "succeeds", "score": 0.6, "metadata": {}},
            ],
            "provider": "ollama",
            "model_name": "llama3",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["hits"]) == 2

    failed_hit = next(h for h in data["hits"] if h["chunk_id"] == "c1")
    success_hit = next(h for h in data["hits"] if h["chunk_id"] == "c2")

    assert failed_hit["rerank_score"] == 0.0
    assert failed_hit["final_score"] == round(0.5 * 0.8 + 0.5 * 0.0, 6)

    assert success_hit["rerank_score"] == 0.7
    assert success_hit["final_score"] == round(0.5 * 0.6 + 0.5 * 0.7, 6)


def test_rerank_all_hits_fail_returns_valid_response(monkeypatch) -> None:
    from app.core.model_manager import model_manager
    from app.providers.ollama import OllamaProvider

    monkeypatch.setattr(model_manager, "activate", AsyncMock(return_value={}))
    monkeypatch.setattr(model_manager, "mark_busy", lambda: None)
    monkeypatch.setattr(model_manager, "mark_idle", lambda: None)

    async def fake_generate_text(self, model_name, prompt, api_key=None, temperature=None, max_output_tokens=None):
        raise RuntimeError("Always fails")

    monkeypatch.setattr(OllamaProvider, "generate_text", fake_generate_text)

    response = client.post(
        "/retrieval/rerank",
        json={
            "query": "revenue",
            "hits": [
                {"doc_id": "d1", "chunk_id": "c1", "text": "chunk1", "score": 0.9, "metadata": {}},
                {"doc_id": "d1", "chunk_id": "c2", "text": "chunk2", "score": 0.3, "metadata": {}},
            ],
            "provider": "ollama",
            "model_name": "llama3",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["hits"]) == 2
    for hit in data["hits"]:
        assert hit["rerank_score"] == 0.0
        assert hit["final_score"] == round(0.5 * hit["original_score"], 6)


def test_rerank_preserves_original_score(monkeypatch) -> None:
    from app.core.model_manager import model_manager
    from app.providers.ollama import OllamaProvider

    monkeypatch.setattr(model_manager, "activate", AsyncMock(return_value={}))
    monkeypatch.setattr(model_manager, "mark_busy", lambda: None)
    monkeypatch.setattr(model_manager, "mark_idle", lambda: None)

    async def fake_generate_text(self, model_name, prompt, api_key=None, temperature=None, max_output_tokens=None):
        return {"provider": "ollama", "model_name": model_name, "text": "0.6", "usage": {}, "metadata": {}}

    monkeypatch.setattr(OllamaProvider, "generate_text", fake_generate_text)

    response = client.post(
        "/retrieval/rerank",
        json={
            "query": "revenue",
            "hits": [
                {"doc_id": "d1", "chunk_id": "c1", "text": "chunk", "score": 0.75, "metadata": {}},
            ],
            "provider": "ollama",
            "model_name": "llama3",
        },
    )

    assert response.status_code == 200
    hit = response.json()["hits"][0]
    assert hit["original_score"] == 0.75
    assert hit["rerank_score"] == 0.6
    assert hit["final_score"] == round(0.5 * 0.75 + 0.5 * 0.6, 6)
