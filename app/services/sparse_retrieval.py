from typing import Any

from rank_bm25 import BM25L

from app.services import retrieval_store


def _tokenize(text: str) -> list[str]:
    normalized = text.lower().strip()
    if not normalized:
        return []
    return normalized.split()


def build_sparse_index(records: list[dict[str, Any]]) -> tuple[BM25L, list[dict[str, Any]]]:
    tokenized_corpus = [_tokenize(str(record.get("text") or "")) for record in records]
    return BM25L(tokenized_corpus), records


def search_sparse(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    records = retrieval_store.get_records()
    if not records:
        return []

    index, indexed_records = build_sparse_index(records)
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    raw_scores = index.get_scores(query_tokens)
    scored = list(zip(raw_scores.tolist(), indexed_records, strict=False))
    scored.sort(key=lambda item: item[0], reverse=True)

    filtered = [item for item in scored if float(item[0]) > 0]

    hits: list[dict[str, Any]] = []
    for score, record in filtered[:top_k]:
        hits.append(
            {
                "doc_id": record["doc_id"],
                "chunk_id": record["chunk_id"],
                "text": record["text"],
                "score": float(score),
                "retrieval_type": "sparse",
                "metadata": record.get("metadata", {}),
            }
        )

    return hits