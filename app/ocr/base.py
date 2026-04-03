import base64
import logging
import pathlib
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.core.settings import settings

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp"})


def validate_file(file_path: str) -> pathlib.Path:
    path = pathlib.Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")
    if path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
        raise ValueError(
            f"Unsupported file extension '{path.suffix}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_IMAGE_EXTENSIONS))}"
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

    async def extract(self, file_path: str) -> dict[str, Any]:
        path = validate_file(file_path)
        image_b64 = encode_image_base64(path)

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

        return self._normalize(text, data, file_path)

    @abstractmethod
    def _normalize(self, text: str, raw: dict[str, Any], file_path: str) -> dict[str, Any]: ...
