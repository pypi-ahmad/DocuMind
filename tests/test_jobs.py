from fastapi.testclient import TestClient

from app.main import app
from app.workers.queue import create_job, get_job, get_job_input

client = TestClient(app)


def test_create_job_redacts_api_key_from_stored_input() -> None:
    job = create_job(
        "ocr.postprocess",
        {
            "ocr_result": {"normalized_text": "hello"},
            "task": "summary",
            "provider": "openai",
            "model_name": "gpt-5",
            "api_key": "secret-key",
        },
    )

    stored_job = get_job(job.job_id)
    assert stored_job is not None
    assert "api_key" not in stored_job.input

    resolved_input = get_job_input(job.job_id)
    assert resolved_input is not None
    assert resolved_input["api_key"] == "secret-key"


def test_submit_job_response_redacts_api_key() -> None:
    response = client.post(
        "/jobs",
        json={
            "type": "ocr.postprocess",
            "input": {
                "ocr_result": {"normalized_text": "hello"},
                "task": "summary",
                "provider": "openai",
                "model_name": "gpt-5",
                "api_key": "secret-key",
            },
        },
    )

    assert response.status_code == 201
    assert "api_key" not in response.json()["input"]