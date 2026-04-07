from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, status

from app.providers.base import (
    ProviderConfigurationError,
    ProviderNotImplementedError,
    ProviderUnauthorizedError,
    ProviderUpstreamError,
)
from app.schemas.common import ErrorResponse
from app.schemas.retrieval import (
    DocumentQARequest,
    DocumentQAResponse,
    DocumentSummary,
    HybridSearchRequest,
    HybridSearchResponse,
    IndexDocumentRequest,
    IndexDocumentResponse,
    OCRIndexRequest,
    OCRIndexResponse,
    RerankRequest,
    RerankResponse,
    SearchRequest,
    SearchResponse,
)
from app.services import retrieval_store
from app.services.embedding_service import index_document_text, search_similar
from app.services.document_qa import ALLOWED_RETRIEVAL_MODES, answer_document_query
from app.services.hybrid_retrieval import hybrid_search
from app.services.indexing import index_ocr_document
from app.services.reranker import rerank_hits

router = APIRouter(prefix="/retrieval", tags=["retrieval"])

_INDEX_DOCUMENT_EXAMPLES = {
    "text": {
        "summary": "Index plain document text",
        "value": {
            "doc_id": "invoice-001",
            "text": "Invoice #001. Total due is $150. Due date is April 30.",
            "provider": "ollama",
            "model_name": "nomic-embed-text",
            "metadata": {"source": "invoice"},
        },
    }
}

_INDEX_OCR_EXAMPLES = {
    "ocr_index": {
        "summary": "Extract and index an OCR document",
        "value": {
            "doc_id": "contract-2025",
            "file_path": "sample-docs/contract.png",
            "prefer_structure": True,
            "embedding_provider": "ollama",
            "embedding_model_name": "nomic-embed-text",
            "metadata": {"source": "contract"},
        },
    }
}

_SEARCH_EXAMPLES = {
    "dense": {
        "summary": "Dense retrieval search",
        "value": {
            "query": "What is the invoice total?",
            "provider": "ollama",
            "model_name": "nomic-embed-text",
            "top_k": 3,
        },
    }
}

_HYBRID_SEARCH_EXAMPLES = {
    "hybrid": {
        "summary": "Hybrid retrieval search",
        "value": {
            "query": "When does the contract start?",
            "provider": "ollama",
            "model_name": "nomic-embed-text",
            "top_k": 5,
            "dense_weight": 0.5,
            "sparse_weight": 0.5,
        },
    }
}

_RERANK_EXAMPLES = {
    "rerank": {
        "summary": "Rerank candidate hits",
        "value": {
            "query": "When does the contract start?",
            "hits": [
                {
                    "doc_id": "contract-2025",
                    "chunk_id": "contract-2025:chunk:0",
                    "text": "The contract effective date is March 1, 2025.",
                    "score": 0.78,
                    "metadata": {"page": 1},
                }
            ],
            "provider": "ollama",
            "model_name": "llama3",
            "top_k": 1,
        },
    }
}

_QA_EXAMPLES = {
    "qa": {
        "summary": "Ask a grounded question over indexed content",
        "value": {
            "query": "When does the contract start?",
            "provider": "ollama",
            "model_name": "llama3",
            "retrieval_mode": "hybrid",
            "top_k": 5,
            "use_rerank": True,
            "rerank_top_k": 3,
        },
    }
}


def _handle_provider_errors(exc: Exception) -> None:
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if isinstance(exc, ProviderNotImplementedError):
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc)) from exc
    if isinstance(exc, ProviderConfigurationError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if isinstance(exc, ProviderUnauthorizedError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    if isinstance(exc, ProviderUpstreamError):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post(
    "/index",
    response_model=IndexDocumentResponse,
    summary="Index document text",
    description="Chunk document text, embed it, and store it in the in-memory retrieval index.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid indexing request."},
        401: {"model": ErrorResponse, "description": "Provider authentication failed."},
        501: {"model": ErrorResponse, "description": "Provider capability not implemented."},
        502: {"model": ErrorResponse, "description": "Embedding provider upstream failure."},
    },
)
async def index_document(
    payload: Annotated[IndexDocumentRequest, Body(openapi_examples=_INDEX_DOCUMENT_EXAMPLES)],
) -> IndexDocumentResponse:
    try:
        result = await index_document_text(
            doc_id=payload.doc_id,
            text=payload.text,
            provider=payload.provider,
            model_name=payload.model_name,
            api_key=payload.api_key,
            metadata=payload.metadata,
        )
    except Exception as exc:
        _handle_provider_errors(exc)
        raise

    return IndexDocumentResponse(**result)


@router.post(
    "/index-ocr",
    response_model=OCRIndexResponse,
    summary="Extract and index OCR content",
    description="Run OCR extraction and then index the resulting text for retrieval and QA.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid OCR indexing request."},
        401: {"model": ErrorResponse, "description": "Provider authentication failed."},
        502: {"model": ErrorResponse, "description": "OCR or embedding upstream failure."},
    },
)
async def index_ocr(
    payload: Annotated[OCRIndexRequest, Body(openapi_examples=_INDEX_OCR_EXAMPLES)],
) -> OCRIndexResponse:
    try:
        result = await index_ocr_document(
            doc_id=payload.doc_id,
            file_path=payload.file_path,
            ocr_engine=payload.ocr_engine,
            prefer_structure=payload.prefer_structure,
            embedding_provider=payload.embedding_provider,
            embedding_model_name=payload.embedding_model_name,
            api_key=payload.api_key,
            metadata=payload.metadata,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except (TimeoutError, ConnectionError, RuntimeError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except Exception as exc:
        _handle_provider_errors(exc)
        raise

    return OCRIndexResponse(**result)


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Run dense retrieval search",
    description="Search indexed documents using embedding similarity.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid retrieval request."},
        401: {"model": ErrorResponse, "description": "Provider authentication failed."},
        501: {"model": ErrorResponse, "description": "Provider capability not implemented."},
        502: {"model": ErrorResponse, "description": "Embedding provider upstream failure."},
    },
)
async def search_documents(
    payload: Annotated[SearchRequest, Body(openapi_examples=_SEARCH_EXAMPLES)],
) -> SearchResponse:
    try:
        result = await search_similar(
            query=payload.query,
            provider=payload.provider,
            model_name=payload.model_name,
            api_key=payload.api_key,
            top_k=payload.top_k,
        )
    except Exception as exc:
        _handle_provider_errors(exc)
        raise

    return SearchResponse(**result)


@router.post(
    "/hybrid-search",
    response_model=HybridSearchResponse,
    summary="Run hybrid retrieval search",
    description="Combine dense and sparse retrieval signals over the indexed document store.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid hybrid retrieval request."},
        401: {"model": ErrorResponse, "description": "Provider authentication failed."},
        501: {"model": ErrorResponse, "description": "Provider capability not implemented."},
        502: {"model": ErrorResponse, "description": "Embedding provider upstream failure."},
    },
)
async def hybrid_search_documents(
    payload: Annotated[HybridSearchRequest, Body(openapi_examples=_HYBRID_SEARCH_EXAMPLES)],
) -> HybridSearchResponse:
    if not payload.query.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="query must not be empty")
    if payload.top_k <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="top_k must be greater than 0")
    if payload.dense_weight < 0 or payload.sparse_weight < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="weights must be non-negative")
    if payload.dense_weight == 0 and payload.sparse_weight == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="at least one weight must be greater than 0")

    try:
        result = await hybrid_search(
            query=payload.query,
            provider=payload.provider,
            model_name=payload.model_name,
            api_key=payload.api_key,
            top_k=payload.top_k,
            dense_weight=payload.dense_weight,
            sparse_weight=payload.sparse_weight,
        )
    except Exception as exc:
        _handle_provider_errors(exc)
        raise

    return HybridSearchResponse(**result)


@router.post(
    "/rerank",
    response_model=RerankResponse,
    summary="Rerank retrieval hits",
    description="Score and reorder candidate retrieval hits using an LLM-backed reranker.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid rerank request."},
        401: {"model": ErrorResponse, "description": "Provider authentication failed."},
        501: {"model": ErrorResponse, "description": "Provider capability not implemented."},
        502: {"model": ErrorResponse, "description": "Reranker upstream failure."},
    },
)
async def rerank_documents(
    payload: Annotated[RerankRequest, Body(openapi_examples=_RERANK_EXAMPLES)],
) -> RerankResponse:
    if not payload.query.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="query must not be empty")
    if not payload.hits:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="hits must not be empty")
    if payload.top_k <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="top_k must be greater than 0")

    try:
        result = await rerank_hits(
            query=payload.query,
            hits=payload.hits,
            provider=payload.provider,
            model_name=payload.model_name,
            api_key=payload.api_key,
            top_k=payload.top_k,
            temperature=payload.temperature,
            max_output_tokens=payload.max_output_tokens,
        )
    except Exception as exc:
        _handle_provider_errors(exc)
        raise

    return RerankResponse(**result)


@router.post(
    "/qa",
    response_model=DocumentQAResponse,
    summary="Answer grounded document questions",
    description="Answer a question using only indexed document context with optional reranking.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid document QA request."},
        401: {"model": ErrorResponse, "description": "Provider authentication failed."},
        501: {"model": ErrorResponse, "description": "Provider capability not implemented."},
        502: {"model": ErrorResponse, "description": "Retrieval or generation upstream failure."},
    },
)
async def qa_documents(
    payload: Annotated[DocumentQARequest, Body(openapi_examples=_QA_EXAMPLES)],
) -> DocumentQAResponse:
    if not payload.query.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="query must not be empty")
    if payload.retrieval_mode.strip().lower() not in ALLOWED_RETRIEVAL_MODES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="retrieval_mode must be one of: dense, hybrid")
    if payload.top_k <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="top_k must be greater than 0")
    if payload.use_rerank and payload.rerank_top_k <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="rerank_top_k must be greater than 0 when use_rerank is true",
        )

    try:
        result = await answer_document_query(
            query=payload.query,
            provider=payload.provider,
            model_name=payload.model_name,
            api_key=payload.api_key,
            retrieval_mode=payload.retrieval_mode,
            top_k=payload.top_k,
            use_rerank=payload.use_rerank,
            rerank_top_k=payload.rerank_top_k,
            temperature=payload.temperature,
            max_output_tokens=payload.max_output_tokens,
        )
    except Exception as exc:
        _handle_provider_errors(exc)
        raise

    return DocumentQAResponse(**result)


@router.get(
    "/documents",
    response_model=list[DocumentSummary],
    summary="List indexed documents",
    description="Return a compact summary of documents currently stored in the retrieval index.",
)
def get_documents() -> list[DocumentSummary]:
    docs = retrieval_store.list_documents()
    return [DocumentSummary(**d) for d in docs]


@router.delete(
    "/documents",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear indexed documents",
    description="Remove all documents from the in-memory retrieval index.",
)
def delete_documents() -> None:
    retrieval_store.clear_store()


@router.delete(
    "/documents/{doc_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a single indexed document",
    description="Remove all chunks belonging to the given document ID from the retrieval index.",
    responses={404: {"model": ErrorResponse, "description": "Document not found."}},
)
def delete_document(doc_id: str) -> None:
    found = retrieval_store.delete_document(doc_id)
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{doc_id}' not found")
