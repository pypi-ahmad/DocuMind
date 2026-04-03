"""Milvus-backed vector store implementing the same interface as the in-memory store."""

from typing import Any

from pymilvus import (
    CollectionSchema,
    DataType,
    FieldSchema,
    MilvusClient,
)

from app.core.settings import settings

_client: MilvusClient | None = None


def _get_client() -> MilvusClient:
    global _client
    if _client is None:
        _client = MilvusClient(
            uri=settings.milvus_uri,
            token=settings.milvus_token or None,
        )
        _ensure_collection()
    return _client


def _ensure_collection() -> None:
    client = _client
    assert client is not None
    name = settings.milvus_collection_name
    if client.has_collection(name):
        return

    fields = [
        FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=512),
        FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=512),
        FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=512),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=settings.milvus_vector_dim),
        FieldSchema(name="metadata_json", dtype=DataType.VARCHAR, max_length=65535),
    ]
    schema = CollectionSchema(fields=fields, enable_dynamic_field=False)

    client.create_collection(
        collection_name=name,
        schema=schema,
    )
    # Create vector index for search
    client.create_index(
        collection_name=name,
        field_name="vector",
        index_params={"index_type": "IVF_FLAT", "metric_type": "COSINE", "params": {"nlist": 128}},
    )


def add_documents(records: list[dict[str, Any]]) -> int:
    import json
    client = _get_client()
    name = settings.milvus_collection_name

    rows: list[dict[str, Any]] = []
    for record in records:
        vec = record["vector"]
        if hasattr(vec, "tolist"):
            vec = vec.tolist()
        rows.append({
            "id": record["chunk_id"],
            "doc_id": record["doc_id"],
            "chunk_id": record["chunk_id"],
            "text": record["text"],
            "vector": vec,
            "metadata_json": json.dumps(record.get("metadata", {})),
        })

    if rows:
        client.insert(collection_name=name, data=rows)
    return len(rows)


def search(query_vector: list[float], top_k: int = 5) -> list[dict[str, Any]]:
    import json
    client = _get_client()
    name = settings.milvus_collection_name

    results = client.search(
        collection_name=name,
        data=[query_vector],
        limit=top_k,
        output_fields=["doc_id", "chunk_id", "text", "metadata_json"],
        anns_field="vector",
    )

    hits: list[dict[str, Any]] = []
    for result_set in results:
        for hit in result_set:
            entity = hit.get("entity", {})
            meta_raw = entity.get("metadata_json", "{}")
            meta = json.loads(meta_raw) if isinstance(meta_raw, str) else {}
            hits.append({
                "doc_id": entity.get("doc_id", ""),
                "chunk_id": entity.get("chunk_id", ""),
                "text": entity.get("text", ""),
                "score": round(float(hit.get("distance", 0.0)), 6),
                "retrieval_type": "dense",
                "metadata": meta,
            })
    return hits


def clear_store() -> None:
    client = _get_client()
    name = settings.milvus_collection_name
    if client.has_collection(name):
        client.drop_collection(name)
    _ensure_collection()


def list_documents() -> list[dict[str, Any]]:
    import json
    client = _get_client()
    name = settings.milvus_collection_name

    all_results = client.query(
        collection_name=name,
        filter="",
        output_fields=["doc_id", "chunk_id", "metadata_json"],
        limit=16384,
    )

    doc_map: dict[str, dict[str, Any]] = {}
    for row in all_results:
        doc_id = row.get("doc_id", "")
        if doc_id not in doc_map:
            meta_raw = row.get("metadata_json", "{}")
            meta = json.loads(meta_raw) if isinstance(meta_raw, str) else {}
            doc_map[doc_id] = {
                "doc_id": doc_id,
                "chunk_count": 0,
                "metadata": meta,
            }
        doc_map[doc_id]["chunk_count"] += 1
    return list(doc_map.values())


def get_records() -> list[dict[str, Any]]:
    import json
    client = _get_client()
    name = settings.milvus_collection_name

    all_results = client.query(
        collection_name=name,
        filter="",
        output_fields=["doc_id", "chunk_id", "text", "vector", "metadata_json"],
        limit=16384,
    )

    records: list[dict[str, Any]] = []
    for row in all_results:
        meta_raw = row.get("metadata_json", "{}")
        meta = json.loads(meta_raw) if isinstance(meta_raw, str) else {}
        records.append({
            "doc_id": row.get("doc_id", ""),
            "chunk_id": row.get("chunk_id", ""),
            "text": row.get("text", ""),
            "vector": row.get("vector", []),
            "metadata": meta,
        })
    return records
