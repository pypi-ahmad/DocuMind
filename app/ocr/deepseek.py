from typing import Any

from app.core.settings import settings
from app.ocr.base import BaseOCREngine


class DeepSeekOCREngine(BaseOCREngine):
    @property
    def engine_name(self) -> str:
        return "deepseek-ocr"

    @property
    def model_name(self) -> str:
        return settings.ollama_deepseek_ocr_model

    @property
    def prompt(self) -> str:
        return (
            "Extract all text from this image with high accuracy. "
            "Produce clean, readable plain text. "
            "Preserve paragraph breaks and any obvious layout structure."
        )

    def _normalize(self, text: str, raw: dict[str, Any], file_path: str) -> dict[str, Any]:
        return {
            "engine": self.engine_name,
            "text": text,
            "layout": {"pages": 1},
            "tables": [],
            "confidence": 0.0,
            "metadata": {
                "model": raw.get("model", self.model_name),
                "total_duration_ns": raw.get("total_duration"),
                "eval_count": raw.get("eval_count"),
                "file_path": file_path,
            },
        }
