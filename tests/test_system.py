from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_info_returns_expected_fields() -> None:
    response = client.get("/info")
    assert response.status_code == 200
    data = response.json()
    assert data["app_name"] == "DocuMind"
    assert data["version"] == "0.1.0"
    assert "python_version" in data
    assert data["supported_providers"] == ["ollama", "openai", "gemini", "anthropic"]
    assert data["supported_ocr_engines"] == ["deepseek-ocr", "glm-ocr"]
