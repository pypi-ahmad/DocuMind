from typing import Any

from app.core.model_manager import model_manager
from app.core.secrets import resolve_provider_api_key
from app.providers.base import ProviderGenerateResult
from app.providers.registry import API_KEY_REQUIRED, PROVIDER_FACTORIES
from app.services import retrieval_store
from app.services.embedding_service import search_similar
from app.services.hybrid_retrieval import hybrid_search
from app.services.reranker import rerank_hits

ALLOWED_RETRIEVAL_MODES = {"dense", "hybrid"}
_NO_INDEXED_CONTENT_ANSWER = "No indexed content is available to answer that question."
_NO_SUPPORTING_CONTEXT_ANSWER = (
    "I cannot answer that from the indexed content because I could not find enough supporting context."
)


def _require_non_empty_string(value: str | None, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _normalize_dense_hits(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "doc_id": match.get("doc_id", ""),
            "chunk_id": match.get("chunk_id", ""),
            "text": match.get("text", ""),
            "score": float(match.get("score", 0.0)),
            "metadata": match.get("metadata", {}),
            "retrieval_type": "dense",
        }
        for match in matches
    ]


def _normalize_reranked_hits(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "doc_id": hit.get("doc_id", ""),
            "chunk_id": hit.get("chunk_id", ""),
            "text": hit.get("text", ""),
            "score": float(hit.get("final_score", hit.get("original_score", 0.0))),
            "metadata": hit.get("metadata", {}),
        }
        for hit in hits
    ]


def _build_citations(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "doc_id": hit.get("doc_id", ""),
            "chunk_id": hit.get("chunk_id", ""),
            "text": hit.get("text", ""),
            "metadata": hit.get("metadata", {}),
        }
        for hit in hits
    ]


def build_qa_context(hits: list[dict[str, Any]]) -> str:
    sections: list[str] = []
    for index, hit in enumerate(hits, start=1):
        metadata = hit.get("metadata") or {}
        parts = [
            f"Source {index}",
            f"Doc ID: {hit.get('doc_id', '')}",
            f"Chunk ID: {hit.get('chunk_id', '')}",
        ]
        if metadata:
            metadata_text = ", ".join(f"{key}: {value}" for key, value in metadata.items())
            parts.append(f"Metadata: {metadata_text}")
        parts.append("Text:")
        parts.append(str(hit.get("text") or "").strip())
        sections.append("\n".join(parts).strip())

    return "\n\n---\n\n".join(section for section in sections if section)


def build_qa_prompt(query: str, context: str) -> str:
    return (
        "You are answering a question about indexed document content.\n"
        "Use ONLY the provided context below.\n"
        "If the answer is not supported by the context, say clearly that you cannot answer from the provided context.\n"
        "Do NOT invent facts.\n"
        "Do NOT use outside knowledge.\n"
        "Provide a concise grounded answer only.\n"
        "Do NOT mention retrieval, ranking, or scoring in the answer.\n\n"
        f"Question:\n{query}\n\n"
        f"Context:\n{context}"
    )


async def _retrieve_hits(
    *,
    query: str,
    provider: str,
    model_name: str,
    api_key: str | None,
    retrieval_mode: str,
    top_k: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if retrieval_mode == "dense":
        dense_result = await search_similar(
            query=query,
            provider=provider,
            model_name=model_name,
            api_key=api_key,
            top_k=top_k,
        )
        hits = _normalize_dense_hits(dense_result.get("matches", []))
        return hits, {"retrieved_hit_count": len(hits)}

    hybrid_result = await hybrid_search(
        query=query,
        provider=provider,
        model_name=model_name,
        api_key=api_key,
        top_k=top_k,
    )
    hits = list(hybrid_result.get("hits", []))
    return hits, dict(hybrid_result.get("metadata", {}))


async def _generate_answer(
    *,
    query: str,
    context: str,
    provider: str,
    model_name: str,
    api_key: str | None,
    temperature: float | None,
    max_output_tokens: int | None,
) -> tuple[str, dict[str, Any]]:
    provider_name = provider.strip().lower()
    factory = PROVIDER_FACTORIES.get(provider_name)
    if factory is None:
        raise ValueError(f"Unknown provider: {provider_name}")

    provider_client = factory()
    resolved_key = resolve_provider_api_key(provider_name, api_key.strip() if api_key else None)
    if provider_name in API_KEY_REQUIRED and not resolved_key:
        raise ValueError(f"{provider_name} requires api_key")

    if provider_name == "ollama":
        await model_manager.activate(provider_name, model_name.strip())

    prompt = build_qa_prompt(query, context)

    model_manager.mark_busy()
    try:
        result = await provider_client.generate_text(
            model_name=model_name.strip(),
            prompt=prompt,
            api_key=resolved_key,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
    finally:
        model_manager.mark_idle()

    if isinstance(result, ProviderGenerateResult):
        result_dict = result.to_dict()
    else:
        result_dict = result

    metadata = {
        "provider": result_dict.get("provider", provider_name),
        "model_name": result_dict.get("model_name", model_name),
        "usage": result_dict.get("usage", {}),
        "provider_metadata": result_dict.get("metadata", {}),
    }
    return str(result_dict.get("text") or "").strip(), metadata


async def answer_document_query(
    *,
    query: str,
    provider: str,
    model_name: str,
    api_key: str | None = None,
    retrieval_mode: str = "hybrid",
    top_k: int = 5,
    use_rerank: bool = True,
    rerank_top_k: int = 5,
    temperature: float | None = None,
    max_output_tokens: int | None = None,
) -> dict[str, Any]:
    resolved_query = _require_non_empty_string(query, "query")
    resolved_provider = _require_non_empty_string(provider, "provider")
    resolved_model_name = _require_non_empty_string(model_name, "model_name")
    resolved_mode = retrieval_mode.strip().lower()

    if resolved_mode not in ALLOWED_RETRIEVAL_MODES:
        raise ValueError("retrieval_mode must be one of: dense, hybrid")
    if top_k <= 0:
        raise ValueError("top_k must be greater than 0")
    if use_rerank and rerank_top_k <= 0:
        raise ValueError("rerank_top_k must be greater than 0 when use_rerank is true")

    if not retrieval_store.get_records():
        return {
            "query": resolved_query,
            "answer": _NO_INDEXED_CONTENT_ANSWER,
            "citations": [],
            "retrieval_mode": resolved_mode,
            "used_rerank": False,
            "metadata": {
                "retrieval_mode": resolved_mode,
                "retrieved_hit_count": 0,
                "final_hit_count": 0,
                "retrieval_store_empty": True,
            },
        }

    retrieved_hits, retrieval_metadata = await _retrieve_hits(
        query=resolved_query,
        provider=resolved_provider,
        model_name=resolved_model_name,
        api_key=api_key,
        retrieval_mode=resolved_mode,
        top_k=top_k,
    )

    final_hits = list(retrieved_hits)
    rerank_metadata: dict[str, Any] = {}
    used_rerank = False
    if use_rerank and retrieved_hits:
        rerank_result = await rerank_hits(
            query=resolved_query,
            hits=retrieved_hits,
            provider=resolved_provider,
            model_name=resolved_model_name,
            api_key=api_key,
            top_k=rerank_top_k,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        final_hits = _normalize_reranked_hits(rerank_result.get("hits", []))
        rerank_metadata = dict(rerank_result.get("metadata", {}))
        used_rerank = True

    citations = _build_citations(final_hits)
    context = build_qa_context(final_hits)

    if not citations or not context.strip():
        return {
            "query": resolved_query,
            "answer": _NO_SUPPORTING_CONTEXT_ANSWER,
            "citations": citations,
            "retrieval_mode": resolved_mode,
            "used_rerank": used_rerank,
            "metadata": {
                "retrieval_mode": resolved_mode,
                "retrieved_hit_count": len(retrieved_hits),
                "final_hit_count": len(final_hits),
                "retrieval_metadata": retrieval_metadata,
                "rerank_metadata": rerank_metadata,
            },
        }

    answer_text, answer_metadata = await _generate_answer(
        query=resolved_query,
        context=context,
        provider=resolved_provider,
        model_name=resolved_model_name,
        api_key=api_key,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
    )

    return {
        "query": resolved_query,
        "answer": answer_text or _NO_SUPPORTING_CONTEXT_ANSWER,
        "citations": citations,
        "retrieval_mode": resolved_mode,
        "used_rerank": used_rerank,
        "metadata": {
            "retrieval_mode": resolved_mode,
            "retrieved_hit_count": len(retrieved_hits),
            "final_hit_count": len(final_hits),
            "context_length": len(context),
            "retrieval_metadata": retrieval_metadata,
            "rerank_metadata": rerank_metadata,
            "answer_metadata": answer_metadata,
        },
    }