from typing import Any

import numpy as np


_records: list[dict[str, Any]] = []


def add_documents(records: list[dict[str, Any]]) -> int:
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


def search(query_vector: list[float], top_k: int = 5) -> list[dict[str, Any]]:
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


def clear_store() -> None:
    _records.clear()


def list_documents() -> list[dict[str, Any]]:
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


def get_records() -> list[dict[str, Any]]:
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
