from app.ocr.deepseek import DeepSeekOCREngine
from app.ocr.glm import GLMOCREngine


def test_ocr_engine_names() -> None:
    assert DeepSeekOCREngine().engine_name == "deepseek-ocr"
    assert GLMOCREngine().engine_name == "glm-ocr"
