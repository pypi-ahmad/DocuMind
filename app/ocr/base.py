import base64
import logging
import pathlib
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.core.settings import settings
from app.ocr.pdf import is_pdf, pdf_page_count, render_pdf_page_to_base64

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp"})
SUPPORTED_FILE_EXTENSIONS = SUPPORTED_IMAGE_EXTENSIONS | frozenset({".pdf"})


def validate_file(file_path: str) -> pathlib.Path:
    path = pathlib.Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")
    if path.suffix.lower() not in SUPPORTED_FILE_EXTENSIONS:
        raise ValueError(
            f"Unsupported file extension '{path.suffix}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_FILE_EXTENSIONS))}"
        )
    return path


def encode_image_base64(path: pathlib.Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


class BaseOCREngine(ABC):
    @property
    @abstractmethod
    def engine_name(self) -> str: ...

    @property
    @abstractmethod
    def model_name(self) -> str: ...

    @property
    @abstractmethod
    def prompt(self) -> str: ...

    async def _call_ollama(self, image_b64: str) -> tuple[str, dict[str, Any]]:
        """Send a single base64-encoded image to Ollama and return (text, raw_response)."""
        payload = {
            "model": self.model_name,
            "prompt": self.prompt,
            "images": [image_b64],
            "stream": False,
            "keep_alive": settings.ollama_keep_alive,
        }

        url = f"{settings.ollama_base_url.rstrip('/')}/api/generate"

        try:
            async with httpx.AsyncClient(timeout=settings.ollama_http_timeout_seconds) as client:
                response = await client.post(url, json=payload)
        except httpx.TimeoutException as exc:
            raise TimeoutError(f"Ollama request timed out for {self.engine_name}") from exc
        except httpx.ConnectError as exc:
            raise ConnectionError(f"Cannot connect to Ollama at {settings.ollama_base_url}") from exc
        except httpx.HTTPError as exc:
            raise ConnectionError(f"Ollama HTTP error for {self.engine_name}: {exc}") from exc

        if response.is_error:
            raise RuntimeError(
                f"Ollama returned status {response.status_code}: {response.text[:200]}"
            )

        data = response.json()
        text = data.get("response", "")
        return text, data

    async def extract(self, file_path: str) -> dict[str, Any]:
        path = validate_file(file_path)

        if is_pdf(path):
            return await self._extract_pdf(path, file_path)

        image_b64 = encode_image_base64(path)
        text, data = await self._call_ollama(image_b64)
        return self._normalize(text, data, file_path)

    async def _extract_pdf(self, path: pathlib.Path, file_path: str) -> dict[str, Any]:
        """OCR every page of a PDF and merge into a single result."""
        num_pages = pdf_page_count(path)
        if num_pages == 0:
            raise ValueError(f"PDF has no pages: {file_path}")

        page_results: list[dict[str, Any]] = []
        all_texts: list[str] = []
        total_eval_count = 0
        total_duration_ns = 0

        for page_idx in range(num_pages):
            image_b64 = render_pdf_page_to_base64(path, page_idx)
            text, raw = await self._call_ollama(image_b64)

            page_results.append({
                "page": page_idx + 1,
                "text": text,
                "confidence": 0.0,
                "metadata": {
                    "model": raw.get("model", self.model_name),
                    "total_duration_ns": raw.get("total_duration"),
                    "eval_count": raw.get("eval_count"),
                },
            })
            all_texts.append(text)

            if raw.get("eval_count"):
                total_eval_count += raw["eval_count"]
            if raw.get("total_duration"):
                total_duration_ns += raw["total_duration"]

        combined_text = "\n\n".join(all_texts)

        merged_raw = {
            "model": self.model_name,
            "total_duration": total_duration_ns,
            "eval_count": total_eval_count,
        }

        result = self._normalize(combined_text, merged_raw, file_path)
        result["layout"]["pages"] = num_pages
        result["pages"] = page_results
        return result

    @abstractmethod
    def _normalize(self, text: str, raw: dict[str, Any], file_path: str) -> dict[str, Any]: ...
