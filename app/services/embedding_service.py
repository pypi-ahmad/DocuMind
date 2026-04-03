from typing import Any

from app.services import retrieval_store
from app.core.secrets import resolve_provider_api_key
from app.providers.registry import PROVIDER_FACTORIES
from app.services.chunking import chunk_for_retrieval


async def embed_texts(
    *,
    provider: str,
    model_name: str,
    input_texts: list[str],
    api_key: str | None = None,
) -> dict[str, Any]:
    provider_name = provider.strip().lower()
    factory = PROVIDER_FACTORIES.get(provider_name)
    if factory is None:
        raise ValueError(f"Unknown provider: {provider_name}")

    provider_client = factory()
    resolved_key = resolve_provider_api_key(provider_name, api_key.strip() if api_key else None)

    if provider_name in {"openai", "gemini", "anthropic"} and not resolved_key:
        raise ValueError(f"{provider_name} requires api_key")

    return await provider_client.generate_embeddings(
        model_name=model_name.strip(),
        input_texts=input_texts,
        api_key=resolved_key,
    )


async def index_document_text(
    *,
    doc_id: str,
    text: str,
    provider: str,
    model_name: str,
    api_key: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    chunks = chunk_for_retrieval(text)
    if not chunks:
        return {"doc_id": doc_id, "chunks_indexed": 0, "metadata": metadata or {}}

    result = await embed_texts(
        provider=provider,
        model_name=model_name,
        input_texts=chunks,
        api_key=api_key,
    )

    vectors = result.get("vectors", [])
    records: list[dict[str, Any]] = []
    for i, chunk_text in enumerate(chunks):
        vector = vectors[i]["vector"] if i < len(vectors) else []
        records.append({
            "doc_id": doc_id,
            "chunk_id": f"{doc_id}:chunk:{i}",
            "text": chunk_text,
            "vector": vector,
            "metadata": metadata or {},
        })

    added = retrieval_store.add_documents(records)
    return {"doc_id": doc_id, "chunks_indexed": added, "metadata": metadata or {}}


async def search_similar(
    *,
    query: str,
    provider: str,
    model_name: str,
    api_key: str | None = None,
    top_k: int = 5,
) -> dict[str, Any]:
    result = await embed_texts(
        provider=provider,
        model_name=model_name,
        input_texts=[query],
        api_key=api_key,
    )

    vectors = result.get("vectors", [])
    if not vectors:
        return {"query": query, "matches": []}

    query_vector = vectors[0]["vector"]
    matches = retrieval_store.search(query_vector, top_k=top_k)
    return {"query": query, "matches": matches}
