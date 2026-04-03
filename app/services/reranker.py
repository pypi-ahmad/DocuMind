import re
from typing import Any

from app.core.model_manager import model_manager
from app.core.secrets import resolve_provider_api_key
from app.providers.base import ProviderGenerateResult
from app.providers.registry import API_KEY_REQUIRED, PROVIDER_FACTORIES

_SCORE_PATTERN = re.compile(r"([01](?:\.\d+)?)")


def build_rerank_prompt(query: str, hit: dict[str, Any]) -> str:
    chunk_text = str(hit.get("text") or "").strip()
    metadata = hit.get("metadata") or {}

    parts = [
        "You are a retrieval relevance judge.",
        "Given a user query and a candidate text chunk retrieved from a document, "
        "rate how relevant the chunk is to the query.",
        "",
        "Rules:",
        "- Output ONLY a single numeric score between 0 and 1.",
        "- 0 means completely irrelevant, 1 means perfectly relevant.",
        "- Do NOT answer the query.",
        "- Do NOT invent or add any facts.",
        "- Judge relevance based solely on the content provided.",
        "",
        f"Query: {query}",
        "",
        f"Chunk text: {chunk_text}",
    ]

    if metadata:
        meta_str = ", ".join(f"{k}: {v}" for k, v in metadata.items())
        parts.append(f"Chunk metadata: {meta_str}")

    parts.append("")
    parts.append("Relevance score:")
    return "\n".join(parts)


def _parse_rerank_score(raw_text: str) -> float:
    match = _SCORE_PATTERN.search(raw_text.strip())
    if match is None:
        return 0.0
    value = float(match.group(1))
    return max(0.0, min(1.0, value))


async def rerank_hits(
    query: str,
    hits: list[dict[str, Any]],
    provider: str,
    model_name: str,
    api_key: str | None = None,
    top_k: int = 5,
    temperature: float | None = None,
    max_output_tokens: int | None = None,
) -> dict[str, Any]:
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

    scored: list[dict[str, Any]] = []
    for hit in hits:
        prompt = build_rerank_prompt(query, hit)
        rerank_score = 0.0

        model_manager.mark_busy()
        try:
            result = await provider_client.generate_text(
                model_name=model_name.strip(),
                prompt=prompt,
                api_key=resolved_key,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )
            if isinstance(result, ProviderGenerateResult):
                raw_text = result.text
            else:
                raw_text = str(result.get("text", ""))
            rerank_score = _parse_rerank_score(raw_text)
        except Exception:
            rerank_score = 0.0
        finally:
            model_manager.mark_idle()

        original_score = float(hit.get("score", 0.0))
        final_score = round(0.5 * original_score + 0.5 * rerank_score, 6)

        scored.append({
            "doc_id": hit.get("doc_id", ""),
            "chunk_id": hit.get("chunk_id", ""),
            "text": hit.get("text", ""),
            "original_score": round(original_score, 6),
            "rerank_score": round(rerank_score, 6),
            "final_score": final_score,
            "metadata": hit.get("metadata", {}),
        })

    scored.sort(key=lambda item: item["final_score"], reverse=True)
    top_hits = scored[:top_k]

    return {
        "query": query,
        "hits": top_hits,
        "metadata": {
            "provider": provider_name,
            "model_name": model_name,
            "candidates": len(hits),
            "returned": len(top_hits),
        },
    }
