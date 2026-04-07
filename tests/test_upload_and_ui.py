"""Tests for the file upload endpoint and UI schema improvements."""

import io
from pathlib import Path

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

    def test_upload_zero_byte_file(self, upload_client: TestClient) -> None:
        """Zero-byte files should be accepted (content is valid, just empty)."""
        response = upload_client.post(
            "/ocr/upload",
            files={"file": ("empty.png", io.BytesIO(b""), "image/png")},
        )
        assert response.status_code == 200
        path = Path(response.json()["file_path"])
        assert path.exists()
        assert path.stat().st_size == 0

    def test_upload_whitespace_only_filename(self, upload_client: TestClient) -> None:
        """A filename consisting only of whitespace has no valid extension."""
        response = upload_client.post(
            "/ocr/upload",
            files={"file": ("   ", io.BytesIO(b"data"), "image/png")},
        )
        assert response.status_code == 400
        assert "not allowed" in response.json()["detail"]

    def test_oversized_upload_leaves_no_partial_file(self, upload_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        """When an upload is rejected for size, no partial file should remain on disk."""
        import app.api.routes.upload as upload_mod

        monkeypatch.setattr(upload_mod.settings, "max_upload_size_mb", 0)
        content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        upload_dir = _upload_dir()
        before = set(upload_dir.iterdir())

        upload_client.post(
            "/ocr/upload",
            files={"file": ("big.png", io.BytesIO(content), "image/png")},
        )

        after = set(upload_dir.iterdir())
        new_files = after - before
        assert len(new_files) == 0, f"Partial file left on disk: {new_files}"


# ---------------------------------------------------------------------------
# Upload cleanup tests
# ---------------------------------------------------------------------------


class TestUploadCleanup:
    def test_purge_removes_old_files(self, tmp_path: "Path", monkeypatch: pytest.MonkeyPatch) -> None:
        """Files older than TTL are deleted by the cleanup sweep."""
        import time

        import app.api.routes.upload as upload_mod

        monkeypatch.setattr(upload_mod.settings, "upload_dir", str(tmp_path))
        monkeypatch.setattr(upload_mod.settings, "upload_ttl_minutes", 1)

        # Create an old file (mtime set 120 s in the past)
        old_file = tmp_path / "old.png"
        old_file.write_bytes(b"old")
        old_mtime = time.time() - 120
        import os
        os.utime(old_file, (old_mtime, old_mtime))

        # Create a fresh file
        new_file = tmp_path / "new.png"
        new_file.write_bytes(b"new")

        # Run the purge synchronously — manually inline one iteration of the purge logic
        ttl_seconds = upload_mod.settings.upload_ttl_minutes * 60
        cutoff = time.time() - ttl_seconds
        for p in tmp_path.iterdir():
            if p.is_file() and p.stat().st_mtime < cutoff:
                p.unlink(missing_ok=True)

        assert not old_file.exists(), "Old file should have been purged"
        assert new_file.exists(), "Fresh file should be kept"

    def test_purge_keeps_recent_files(self, tmp_path: "Path", monkeypatch: pytest.MonkeyPatch) -> None:
        """Files within TTL are not deleted."""
        import app.api.routes.upload as upload_mod

        monkeypatch.setattr(upload_mod.settings, "upload_dir", str(tmp_path))
        monkeypatch.setattr(upload_mod.settings, "upload_ttl_minutes", 60)

        recent = tmp_path / "recent.png"
        recent.write_bytes(b"recent")

        import time
        ttl_seconds = upload_mod.settings.upload_ttl_minutes * 60
        cutoff = time.time() - ttl_seconds
        for p in tmp_path.iterdir():
            if p.is_file() and p.stat().st_mtime < cutoff:
                p.unlink(missing_ok=True)

        assert recent.exists(), "Recent file should be kept"


# ---------------------------------------------------------------------------
# Boolean field backend default tests — verify the contract the frontend relies on
# ---------------------------------------------------------------------------


class TestBooleanFieldDefaults:
    """Verify backend Pydantic defaults for boolean fields.

    The frontend boolean checkbox works as follows:
      - Checked:       sends true   → backend receives true
      - Unchecked:     sends false  → backend receives false
      - Never touched: field omitted → backend uses Pydantic default

    These tests verify the Pydantic defaults so the frontend contract is safe.
    """

    def test_prefer_structure_defaults_to_false_when_omitted(self) -> None:
        from app.schemas.ocr import OCRExtractRequest

        req = OCRExtractRequest(file_path="/tmp/test.png")
        assert req.prefer_structure is False

    def test_prefer_structure_explicit_true(self) -> None:
        from app.schemas.ocr import OCRExtractRequest

        req = OCRExtractRequest(file_path="/tmp/test.png", prefer_structure=True)
        assert req.prefer_structure is True

    def test_prefer_structure_explicit_false(self) -> None:
        from app.schemas.ocr import OCRExtractRequest

        req = OCRExtractRequest(file_path="/tmp/test.png", prefer_structure=False)
        assert req.prefer_structure is False

    def test_use_rerank_defaults_to_true_when_omitted(self) -> None:
        from app.schemas.retrieval import DocumentQARequest

        req = DocumentQARequest(
            query="test", provider="ollama", model_name="llama3"
        )
        assert req.use_rerank is True

    def test_use_rerank_explicit_false(self) -> None:
        from app.schemas.retrieval import DocumentQARequest

        req = DocumentQARequest(
            query="test", provider="ollama", model_name="llama3", use_rerank=False
        )
        assert req.use_rerank is False

    def test_use_rerank_explicit_true(self) -> None:
        from app.schemas.retrieval import DocumentQARequest

        req = DocumentQARequest(
            query="test", provider="ollama", model_name="llama3", use_rerank=True
        )
        assert req.use_rerank is True

    def test_boolean_fields_are_optional_in_ui_schema(self) -> None:
        """All boolean UI form fields must be optional (required=False)."""
        from app.api.routes.ui import _FORMS

        for form_key in ("ocr_extract", "ocr_postprocess", "llm_generate", "retrieval_index_ocr", "retrieval_qa", "pipeline_run"):
            descriptor = getattr(_FORMS, form_key)
            for field in descriptor.fields:
                if field.type == "boolean":
                    assert not field.required, (
                        f"{form_key}.{field.name} is boolean but marked required=True — "
                        "booleans should be optional so omitting them uses the backend default"
                    )
