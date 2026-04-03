from typing import Any

from app.core.settings import settings
from app.ocr.base import BaseOCREngine


class GLMOCREngine(BaseOCREngine):
    @property
    def engine_name(self) -> str:
        return "glm-ocr"

    @property
    def model_name(self) -> str:
        return settings.ollama_glm_ocr_model

    @property
    def prompt(self) -> str:
        return (
            "Extract all text from this image with structured formatting. "
            "Identify and preserve sections, headings, lists, and tables. "
            "For tables, use markdown table syntax. "
            "Clearly separate layout regions."
        )

    def _normalize(self, text: str, raw: dict[str, Any], file_path: str) -> dict[str, Any]:
        return {
            "engine": self.engine_name,
            "text": text,
            "layout": {"pages": 1, "structure": True},
            "tables": [],
            "confidence": 0.0,
            "metadata": {
                "model": raw.get("model", self.model_name),
                "total_duration_ns": raw.get("total_duration"),
                "eval_count": raw.get("eval_count"),
                "file_path": file_path,
            },
        }
