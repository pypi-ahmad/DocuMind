from app.ocr.base import BaseOCREngine
from app.ocr.deepseek import DeepSeekOCREngine
from app.ocr.glm import GLMOCREngine

ENGINES: dict[str, BaseOCREngine] = {
    "deepseek-ocr": DeepSeekOCREngine(),
    "glm-ocr": GLMOCREngine(),
}

VALID_ENGINES = frozenset(ENGINES.keys())


class OCRRouter:
    def select_engine(self, file_path: str, prefer_structure: bool = False) -> dict[str, str]:
        if prefer_structure:
            return {
                "selected_engine": "glm-ocr",
                "reason": "GLM-OCR selected for structured document extraction",
            }
        return {
            "selected_engine": "deepseek-ocr",
            "reason": "DeepSeek-OCR selected as default extraction engine",
        }

    def get_engine(self, engine_name: str) -> BaseOCREngine | None:
        return ENGINES.get(engine_name)

    def resolve_engine(self, engine_name: str | None, file_path: str, prefer_structure: bool = False) -> BaseOCREngine:
        selected_engine = engine_name
        if selected_engine is None:
            selected_engine = self.select_engine(file_path, prefer_structure)["selected_engine"]

        engine = self.get_engine(selected_engine)
        if engine is None:
            raise ValueError(
                f"Invalid OCR engine '{selected_engine}'. Must be one of: {', '.join(sorted(VALID_ENGINES))}"
            )

        return engine


ocr_router = OCRRouter()


def select_engine(file_path: str, prefer_structure: bool = False) -> dict[str, str]:
    return ocr_router.select_engine(file_path, prefer_structure)


def get_engine(engine_name: str) -> BaseOCREngine | None:
    return ocr_router.get_engine(engine_name)


def resolve_engine(engine_name: str | None, file_path: str, prefer_structure: bool = False) -> BaseOCREngine:
    return ocr_router.resolve_engine(engine_name, file_path, prefer_structure)
