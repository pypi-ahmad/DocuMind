"""Tests for the file upload endpoint and UI schema improvements."""

import io

import pytest
from fastapi.testclient import TestClient

from app.api.routes.upload import ALLOWED_EXTENSIONS, _upload_dir
from app.schemas.ui import UIFormField


# ---------------------------------------------------------------------------
# UIFormField schema tests (B08)
# ---------------------------------------------------------------------------


class TestUIFormFieldLabel:
    def test_label_field_defaults_to_empty(self) -> None:
        field = UIFormField(name="x", type="string", required=True, description="d")
        assert field.label == ""

    def test_label_field_populated(self) -> None:
        field = UIFormField(name="x", type="string", required=True, description="d", label="My Label")
        assert field.label == "My Label"

    def test_placeholder_field_defaults_to_empty(self) -> None:
        field = UIFormField(name="x", type="string", required=True, description="d")
        assert field.placeholder == ""

    def test_placeholder_field_populated(self) -> None:
        field = UIFormField(name="x", type="string", required=True, description="d", placeholder="e.g. test")
        assert field.placeholder == "e.g. test"


class TestUIFormsLabels:
    """Verify that all forms serve human-readable labels."""

    def test_all_form_fields_have_labels(self) -> None:
        from app.api.routes.ui import _FORMS

        for form_key in ("ocr_extract", "ocr_postprocess", "llm_generate", "retrieval_index_ocr", "retrieval_qa", "pipeline_run"):
            descriptor = getattr(_FORMS, form_key)
            for field in descriptor.fields:
                assert field.label, f"{form_key}.{field.name} is missing a label"

    def test_no_field_uses_raw_name_as_label(self) -> None:
        from app.api.routes.ui import _FORMS

        for form_key in ("ocr_extract", "ocr_postprocess", "llm_generate", "retrieval_index_ocr", "retrieval_qa", "pipeline_run"):
            descriptor = getattr(_FORMS, form_key)
            for field in descriptor.fields:
                assert field.label != field.name, (
                    f"{form_key}.{field.name} label is identical to the raw name"
                )


# ---------------------------------------------------------------------------
# Upload endpoint tests (B13)
# ---------------------------------------------------------------------------

# Bypass auth for upload tests by creating a client with auth disabled.
@pytest.fixture()
def upload_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DOCUMIND_AUTH_ENABLED", "false")
    # Re-import to pick up the patched setting
    from importlib import reload

    import app.core.settings as settings_mod
    reload(settings_mod)
    import app.main as main_mod
    reload(main_mod)
    return TestClient(main_mod.app)


class TestUploadEndpoint:
    def test_upload_valid_png(self, upload_client: TestClient, tmp_path: object) -> None:
        content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        response = upload_client.post(
            "/ocr/upload",
            files={"file": ("test.png", io.BytesIO(content), "image/png")},
        )
        assert response.status_code == 200
        data = response.json()
        assert "file_path" in data
        assert data["file_path"].endswith(".png")

    def test_upload_valid_pdf(self, upload_client: TestClient) -> None:
        content = b"%PDF-1.4 " + b"\x00" * 100
        response = upload_client.post(
            "/ocr/upload",
            files={"file": ("doc.pdf", io.BytesIO(content), "application/pdf")},
        )
        assert response.status_code == 200
        assert response.json()["file_path"].endswith(".pdf")

    def test_upload_rejects_disallowed_extension(self, upload_client: TestClient) -> None:
        response = upload_client.post(
            "/ocr/upload",
            files={"file": ("malware.exe", io.BytesIO(b"MZ"), "application/octet-stream")},
        )
        assert response.status_code == 400
        assert "not allowed" in response.json()["detail"]

    def test_upload_rejects_oversized_file(self, upload_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        import app.api.routes.upload as upload_mod
        monkeypatch.setattr(upload_mod.settings, "max_upload_size_mb", 0)
        content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        response = upload_client.post(
            "/ocr/upload",
            files={"file": ("big.png", io.BytesIO(content), "image/png")},
        )
        assert response.status_code == 400
        assert "size limit" in response.json()["detail"]

    def test_upload_rejects_no_filename(self, upload_client: TestClient) -> None:
        response = upload_client.post(
            "/ocr/upload",
            files={"file": ("", io.BytesIO(b"data"), "application/octet-stream")},
        )
        assert response.status_code in (400, 422)

    def test_allowed_extensions_are_safe(self) -> None:
        """Ensure only image and PDF extensions are allowed."""
        for ext in ALLOWED_EXTENSIONS:
            assert ext in {".png", ".jpg", ".jpeg", ".webp", ".pdf"}

    def test_upload_creates_file_with_uuid_name(self, upload_client: TestClient) -> None:
        content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
        response = upload_client.post(
            "/ocr/upload",
            files={"file": ("../../etc/passwd.png", io.BytesIO(content), "image/png")},
        )
        assert response.status_code == 200
        path = response.json()["file_path"]
        # UUID hex filename — no path traversal
        import os
        basename = os.path.basename(path)
        assert ".." not in basename
        assert "/" not in basename
        assert len(basename) > 20  # uuid4 hex is 32 chars + extension
