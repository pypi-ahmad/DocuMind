from typing import Any

from app.core.model_manager import model_manager
from app.core.secrets import resolve_provider_api_key
from app.providers.base import ProviderGenerateResult
from app.providers.registry import API_KEY_REQUIRED, PROVIDER_FACTORIES
from app.schemas.ocr import POSTPROCESS_TASKS


def _extract_text_block(ocr_result: dict[str, Any]) -> str:
    parts: list[str] = []

    normalized = ocr_result.get("normalized_text")
    if isinstance(normalized, str) and normalized.strip():
        parts.append(normalized.strip())
    else:
        raw = ocr_result.get("text")
        if isinstance(raw, str) and raw.strip():
            parts.append(raw.strip())

    structured = ocr_result.get("structured")
    if isinstance(structured, dict):
        sections = structured.get("sections")
        if isinstance(sections, list):
            for section in sections:
                if isinstance(section, dict):
                    heading = section.get("heading")
                    if isinstance(heading, str) and heading.strip():
                        parts.append(f"[Section: {heading.strip()}]")
                    body = section.get("body")
                    if isinstance(body, str) and body.strip():
                        parts.append(body.strip())

        paragraphs = structured.get("paragraphs")
        if isinstance(paragraphs, list):
            for para in paragraphs:
                if isinstance(para, str) and para.strip():
                    text = para.strip()
                    if text not in parts:
                        parts.append(text)

    return "\n\n".join(parts) if parts else ""


def build_postprocess_prompt(ocr_result: dict[str, Any], task: str) -> str:
    text_block = _extract_text_block(ocr_result)

    if not text_block:
        text_block = "(No usable text was extracted from the document.)"

    if task == "cleanup":
        instruction = (
            "The following text was extracted from a document using OCR. "
            "Produce a cleaner, human-readable version of this text. "
            "Fix obvious OCR artifacts, broken words, and formatting issues. "
            "Do not invent or add any information that is not present in the original text."
        )
    elif task == "summary":
        instruction = (
            "The following text was extracted from a document using OCR. "
            "Provide a concise, factual summary of the content. "
            "Include only information that is explicitly present in the text. "
            "Do not infer, speculate, or add any information beyond what is stated."
        )
    elif task == "extract_key_fields":
        instruction = (
            "The following text was extracted from a document using OCR. "
            "Identify and list the key fields present in the text "
            "(e.g. names, dates, amounts, IDs, addresses, titles). "
            "Format each field as 'Field: Value' on its own line. "
            "Only extract fields that are explicitly present. "
            "Do not guess or fabricate any missing information."
        )
    else:
        raise ValueError(f"Unsupported task: {task}")

    return f"{instruction}\n\n---\n\n{text_block}"


async def run_ocr_postprocess(
    *,
    ocr_result: dict[str, Any],
    task: str,
    provider: str,
    model_name: str,
    api_key: str | None = None,
    temperature: float | None = None,
    max_output_tokens: int | None = None,
) -> dict[str, Any]:
    if task not in POSTPROCESS_TASKS:
        raise ValueError(
            f"Invalid task '{task}'. Must be one of: {', '.join(sorted(POSTPROCESS_TASKS))}"
        )

    provider_name = provider.strip().lower()
    factory = PROVIDER_FACTORIES.get(provider_name)
    if factory is None:
        raise ValueError(f"Unknown provider: {provider_name}")

    provider_client = factory()
    resolved_key = resolve_provider_api_key(provider_name, api_key.strip() if api_key else None)

    if provider_name in API_KEY_REQUIRED and not resolved_key:
        raise ValueError(f"{provider_name} requires api_key")

    prompt = build_postprocess_prompt(ocr_result, task)

    if provider_name == "ollama":
        await model_manager.activate(provider_name, model_name.strip())

    model_manager.mark_busy()
    try:
        result = await provider_client.generate_text(
            model_name=model_name.strip(),
            prompt=prompt,
            api_key=resolved_key,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
    finally:
        model_manager.mark_idle()

    if isinstance(result, ProviderGenerateResult):
        result_dict = result.to_dict()
    else:
        result_dict = result

    return {
        "task": task,
        "provider": result_dict.get("provider", provider_name),
        "model_name": result_dict.get("model_name", model_name),
        "output_text": result_dict.get("text", ""),
        "usage": result_dict.get("usage", {}),
        "metadata": result_dict.get("metadata", {}),
    }
