from typing import Any

from app.services import retrieval_store
from app.services.embedding_service import search_similar
from app.services.sparse_retrieval import search_sparse


def _normalize_scores(hits: list[dict[str, Any]]) -> dict[str, float]:
    if not hits:
        return {}

    raw_scores = [float(hit.get("score", 0.0)) for hit in hits]
    max_score = max(raw_scores)
    min_score = min(raw_scores)

    if max_score == min_score:
        if max_score <= 0:
            return {str(hit["chunk_id"]): 0.0 for hit in hits}
        return {str(hit["chunk_id"]): 1.0 for hit in hits}

    return {
        str(hit["chunk_id"]): (float(hit.get("score", 0.0)) - min_score) / (max_score - min_score)
        for hit in hits
    }


async def hybrid_search(
    query: str,
    provider: str,
    model_name: str,
    api_key: str | None = None,
    top_k: int = 5,
    dense_weight: float = 0.5,
    sparse_weight: float = 0.5,
) -> dict[str, Any]:
    if not retrieval_store.get_records():
        return {
            "query": query,
            "hits": [],
            "metadata": {
                "dense_weight": dense_weight,
                "sparse_weight": sparse_weight,
                "dense_hits": 0,
                "sparse_hits": 0,
            },
        }

    dense_result = await search_similar(
        query=query,
        provider=provider,
        model_name=model_name,
        api_key=api_key,
        top_k=top_k,
    )
    dense_hits = dense_result.get("matches", [])
    sparse_hits = search_sparse(query, top_k=top_k)

    normalized_dense = _normalize_scores(dense_hits)
    normalized_sparse = _normalize_scores(sparse_hits)

    merged: dict[str, dict[str, Any]] = {}

    for hit in dense_hits:
        chunk_id = str(hit["chunk_id"])
        dense_score = normalized_dense.get(chunk_id, 0.0)
        merged[chunk_id] = {
            "doc_id": hit["doc_id"],
            "chunk_id": chunk_id,
            "text": hit["text"],
            "score": dense_weight * dense_score,
            "retrieval_type": "dense",
            "metadata": {
                **hit.get("metadata", {}),
                "dense_score": round(dense_score, 6),
                "sparse_score": 0.0,
            },
        }

    for hit in sparse_hits:
        chunk_id = str(hit["chunk_id"])
        sparse_score = normalized_sparse.get(chunk_id, 0.0)
        if chunk_id in merged:
            merged[chunk_id]["score"] += sparse_weight * sparse_score
            merged[chunk_id]["retrieval_type"] = "hybrid"
            merged[chunk_id]["metadata"]["sparse_score"] = round(sparse_score, 6)
            continue

        merged[chunk_id] = {
            "doc_id": hit["doc_id"],
            "chunk_id": chunk_id,
            "text": hit["text"],
            "score": sparse_weight * sparse_score,
            "retrieval_type": "sparse",
            "metadata": {
                **hit.get("metadata", {}),
                "dense_score": 0.0,
                "sparse_score": round(sparse_score, 6),
            },
        }

    hits = sorted(merged.values(), key=lambda item: item["score"], reverse=True)[:top_k]
    for hit in hits:
        hit["score"] = round(float(hit["score"]), 6)

    return {
        "query": query,
        "hits": hits,
        "metadata": {
            "dense_weight": dense_weight,
            "sparse_weight": sparse_weight,
            "dense_hits": len(dense_hits),
            "sparse_hits": len(sparse_hits),
        },
    }