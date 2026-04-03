from typing import Any

from pydantic import BaseModel, Field


class IndexDocumentRequest(BaseModel):
    doc_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    api_key: str | None = None
    metadata: dict[str, Any] | None = None


class IndexDocumentResponse(BaseModel):
    doc_id: str
    chunks_indexed: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    api_key: str | None = None
    top_k: int = Field(default=5, gt=0)


class SearchMatch(BaseModel):
    doc_id: str
    chunk_id: str
    text: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    query: str
    matches: list[SearchMatch]


class RetrievalHit(BaseModel):
    doc_id: str
    chunk_id: str
    text: str
    score: float
    retrieval_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class HybridSearchRequest(BaseModel):
    query: str
    provider: str
    model_name: str
    api_key: str | None = None
    top_k: int = 5
    dense_weight: float = 0.5
    sparse_weight: float = 0.5


class HybridSearchResponse(BaseModel):
    query: str
    hits: list[RetrievalHit]
    metadata: dict[str, Any] = Field(default_factory=dict)


class OCRIndexRequest(BaseModel):
    doc_id: str = Field(min_length=1)
    file_path: str = Field(min_length=1)
    ocr_engine: str | None = None
    prefer_structure: bool = False
    embedding_provider: str = Field(min_length=1)
    embedding_model_name: str = Field(min_length=1)
    api_key: str | None = None
    metadata: dict[str, Any] | None = None


class OCRIndexResponse(BaseModel):
    doc_id: str
    ocr_engine: str
    indexed_chunk_count: int
    indexed_text_length: int
    retrieval_text_source: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentQACitation(BaseModel):
    doc_id: str
    chunk_id: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentQARequest(BaseModel):
    query: str
    provider: str
    model_name: str
    api_key: str | None = None
    retrieval_mode: str = "hybrid"
    top_k: int = 5
    use_rerank: bool = True
    rerank_top_k: int = 5
    temperature: float | None = None
    max_output_tokens: int | None = None


class DocumentQAResponse(BaseModel):
    query: str
    answer: str
    citations: list[DocumentQACitation]
    retrieval_mode: str
    used_rerank: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


class RerankHit(BaseModel):
    doc_id: str
    chunk_id: str
    text: str
    original_score: float
    rerank_score: float
    final_score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class RerankRequest(BaseModel):
    query: str
    hits: list[dict[str, Any]]
    provider: str
    model_name: str
    api_key: str | None = None
    top_k: int = 5
    temperature: float | None = None
    max_output_tokens: int | None = None


class RerankResponse(BaseModel):
    query: str
    hits: list[RerankHit]
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentSummary(BaseModel):
    doc_id: str
    chunk_count: int
    metadata: dict[str, Any] = Field(default_factory=dict)
