from typing import Any

from app.core.model_manager import model_manager
from app.ocr.normalize import normalize_ocr_result
from app.ocr.router import resolve_engine, select_engine
from app.ocr.structure import structure_ocr_result
from app.services.embedding_service import index_document_text


def _require_non_empty_string(value: str | None, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _build_paragraph_text(ocr_result: dict[str, Any]) -> str:
    structured = ocr_result.get("structured")
    if not isinstance(structured, dict):
        return ""

    paragraphs = structured.get("paragraphs")
    if not isinstance(paragraphs, list):
        return ""

    clean_paragraphs = [paragraph.strip() for paragraph in paragraphs if isinstance(paragraph, str) and paragraph.strip()]
    return "\n\n".join(clean_paragraphs)


def _is_richer_text(candidate_text: str, baseline_text: str) -> bool:
    if not candidate_text.strip():
        return False
    if not baseline_text.strip():
        return True

    candidate_word_count = len(candidate_text.split())
    baseline_word_count = len(baseline_text.split())
    if candidate_word_count != baseline_word_count:
        return candidate_word_count > baseline_word_count

    return len(candidate_text) > len(baseline_text)


async def extract_ocr_document(
    *,
    file_path: str,
    ocr_engine: str | None = None,
    prefer_structure: bool = False,
) -> tuple[str, dict[str, Any]]:
    resolved_file_path = _require_non_empty_string(file_path, "file_path")

    selected_engine_name = (
        _require_non_empty_string(ocr_engine, "ocr_engine")
        if ocr_engine is not None
        else select_engine(resolved_file_path, prefer_structure)["selected_engine"]
    )
    engine = resolve_engine(selected_engine_name, resolved_file_path, prefer_structure)

    await model_manager.activate("ollama", engine.model_name)
    model_manager.mark_busy()
    try:
        result = await engine.extract(resolved_file_path)
        result = normalize_ocr_result(result)
        result = structure_ocr_result(result)
    finally:
        model_manager.mark_idle()

    return selected_engine_name, result


def select_retrieval_text(ocr_result: dict[str, Any]) -> dict[str, str]:
    normalized_text = ocr_result.get("normalized_text")
    raw_text = ocr_result.get("text")

    retrieval_text = ""
    source = ""

    if isinstance(normalized_text, str) and normalized_text.strip():
        retrieval_text = normalized_text.strip()
        source = "normalized_text"
    elif isinstance(raw_text, str) and raw_text.strip():
        retrieval_text = raw_text.strip()
        source = "text"

    paragraph_text = _build_paragraph_text(ocr_result)
    if _is_richer_text(paragraph_text, retrieval_text):
        retrieval_text = paragraph_text
        source = "structured.paragraphs"

    return {
        "retrieval_text": retrieval_text,
        "source": source,
    }


async def index_ocr_document(
    *,
    doc_id: str,
    file_path: str,
    ocr_engine: str | None = None,
    prefer_structure: bool = False,
    embedding_provider: str,
    embedding_model_name: str,
    api_key: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_doc_id = _require_non_empty_string(doc_id, "doc_id")
    resolved_provider = _require_non_empty_string(embedding_provider, "embedding_provider")
    resolved_model_name = _require_non_empty_string(embedding_model_name, "embedding_model_name")

    if metadata is not None and not isinstance(metadata, dict):
        raise ValueError("metadata must be a dict when provided")

    selected_engine_name, ocr_result = await extract_ocr_document(
        file_path=file_path,
        ocr_engine=ocr_engine,
        prefer_structure=prefer_structure,
    )

    selection = select_retrieval_text(ocr_result)
    retrieval_text = selection["retrieval_text"].strip()
    if not retrieval_text:
        raise ValueError("OCR-derived retrieval text is empty")

    index_metadata = dict(metadata or {})
    response_metadata = dict(index_metadata)
    ocr_metadata = ocr_result.get("metadata")
    if isinstance(ocr_metadata, dict) and ocr_metadata:
        response_metadata["ocr_metadata"] = ocr_metadata

    index_result = await index_document_text(
        doc_id=resolved_doc_id,
        text=retrieval_text,
        provider=resolved_provider,
        model_name=resolved_model_name,
        api_key=api_key,
        metadata=index_metadata,
    )

    return {
        "doc_id": resolved_doc_id,
        "ocr_engine": selected_engine_name,
        "indexed_chunk_count": int(index_result.get("chunks_indexed", 0)),
        "indexed_text_length": len(retrieval_text),
        "retrieval_text_source": selection["source"],
        "metadata": response_metadata,
    }