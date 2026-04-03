"""Retrieval store facade — delegates to in-memory or Milvus backend based on config."""

from typing import Any

from app.core.settings import settings

# --- In-memory backend (default) ---

import numpy as np

_records: list[dict[str, Any]] = []


def _memory_add_documents(records: list[dict[str, Any]]) -> int:
    added = 0
    for record in records:
        _records.append({
            "doc_id": record["doc_id"],
            "chunk_id": record["chunk_id"],
            "text": record["text"],
            "vector": np.asarray(record["vector"], dtype=np.float32),
            "metadata": record.get("metadata", {}),
        })
        added += 1
    return added


def _memory_search(query_vector: list[float], top_k: int = 5) -> list[dict[str, Any]]:
    if not _records:
        return []

    q = np.asarray(query_vector, dtype=np.float32)
    q_norm = np.linalg.norm(q)
    if q_norm == 0:
        return []

    scored: list[tuple[float, dict[str, Any]]] = []
    for record in _records:
        v = record["vector"]
        v_norm = np.linalg.norm(v)
        if v_norm == 0:
            continue
        similarity = float(np.dot(q, v) / (q_norm * v_norm))
        scored.append((similarity, record))

    scored.sort(key=lambda x: x[0], reverse=True)

    results: list[dict[str, Any]] = []
    for score, record in scored[:top_k]:
        results.append({
            "doc_id": record["doc_id"],
            "chunk_id": record["chunk_id"],
            "text": record["text"],
            "score": round(score, 6),
            "retrieval_type": "dense",
            "metadata": record["metadata"],
        })
    return results


def _memory_clear_store() -> None:
    _records.clear()


def _memory_list_documents() -> list[dict[str, Any]]:
    doc_map: dict[str, dict[str, Any]] = {}
    for record in _records:
        doc_id = record["doc_id"]
        if doc_id not in doc_map:
            doc_map[doc_id] = {
                "doc_id": doc_id,
                "chunk_count": 0,
                "metadata": record["metadata"],
            }
        doc_map[doc_id]["chunk_count"] += 1
    return list(doc_map.values())


def _memory_get_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for record in _records:
        records.append(
            {
                "doc_id": record["doc_id"],
                "chunk_id": record["chunk_id"],
                "text": record["text"],
                "vector": record["vector"].tolist(),
                "metadata": record["metadata"],
            }
        )
    return records


# --- Dispatch ---

def _use_milvus() -> bool:
    return settings.vector_store_backend.strip().lower() == "milvus"


def add_documents(records: list[dict[str, Any]]) -> int:
    if _use_milvus():
        from app.services.milvus_store import add_documents as _milvus_add
        return _milvus_add(records)
    return _memory_add_documents(records)


def search(query_vector: list[float], top_k: int = 5) -> list[dict[str, Any]]:
    if _use_milvus():
        from app.services.milvus_store import search as _milvus_search
        return _milvus_search(query_vector, top_k)
    return _memory_search(query_vector, top_k)


def clear_store() -> None:
    if _use_milvus():
        from app.services.milvus_store import clear_store as _milvus_clear
        _milvus_clear()
        return
    _memory_clear_store()


def list_documents() -> list[dict[str, Any]]:
    if _use_milvus():
        from app.services.milvus_store import list_documents as _milvus_list
        return _milvus_list()
    return _memory_list_documents()


def get_records() -> list[dict[str, Any]]:
    if _use_milvus():
        from app.services.milvus_store import get_records as _milvus_get
        return _milvus_get()
    return _memory_get_records()
