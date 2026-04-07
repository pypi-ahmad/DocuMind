"""Tests for auth module, queue facade dispatch, and store facade dispatch."""

import time
from typing import Any
from unittest.mock import patch

import jwt
import pytest

from app.core.auth import (
    PUBLIC_PATHS,
    create_access_token,
    decode_access_token,
    get_current_user,
)
from app.core.settings import settings


# ---------------------------------------------------------------------------
# JWT token creation and decoding
# ---------------------------------------------------------------------------


class TestCreateAccessToken:
    def test_creates_valid_token(self) -> None:
        token = create_access_token({"sub": "testuser", "role": "admin"})
        assert isinstance(token, str)
        payload = jwt.decode(token, settings.auth_secret_key, algorithms=[settings.auth_algorithm])
        assert payload["sub"] == "testuser"
        assert payload["role"] == "admin"
        assert "exp" in payload

    def test_custom_expiry(self) -> None:
        from datetime import timedelta

        token = create_access_token({"sub": "u"}, expires_delta=timedelta(seconds=5))
        payload = jwt.decode(token, settings.auth_secret_key, algorithms=[settings.auth_algorithm])
        assert payload["exp"] - int(time.time()) <= 6


class TestDecodeAccessToken:
    def test_decode_valid(self) -> None:
        token = create_access_token({"sub": "u"})
        payload = decode_access_token(token)
        assert payload["sub"] == "u"

    def test_decode_invalid_raises(self) -> None:
        with pytest.raises(jwt.InvalidTokenError):
            decode_access_token("not.a.valid.token")

    def test_decode_wrong_key_raises(self) -> None:
        token = jwt.encode({"sub": "u"}, "wrong-key", algorithm="HS256")
        with pytest.raises(jwt.InvalidTokenError):
            decode_access_token(token)


# ---------------------------------------------------------------------------
# get_current_user dependency
# ---------------------------------------------------------------------------


class TestGetCurrentUser:
    async def test_returns_none_when_auth_disabled(self) -> None:
        with patch.object(settings, "auth_enabled", False):
            result = await get_current_user(token=None)
            assert result is None

    async def test_raises_when_no_token_and_auth_enabled(self) -> None:
        with patch.object(settings, "auth_enabled", True):
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(token=None)
            assert exc_info.value.status_code == 401

    async def test_valid_token_returns_payload(self) -> None:
        with patch.object(settings, "auth_enabled", True):
            token = create_access_token({"sub": "admin", "role": "admin"})
            result = await get_current_user(token=token)
            assert result is not None
            assert result["sub"] == "admin"

    async def test_expired_token_raises(self) -> None:
        from datetime import timedelta

        with patch.object(settings, "auth_enabled", True):
            token = create_access_token({"sub": "u"}, expires_delta=timedelta(seconds=-1))
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(token=token)
            assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# Public paths
# ---------------------------------------------------------------------------


class TestPublicPaths:
    def test_health_paths_are_public(self) -> None:
        assert "/health" in PUBLIC_PATHS
        assert "/health/live" in PUBLIC_PATHS
        assert "/health/ready" in PUBLIC_PATHS

    def test_auth_token_is_public(self) -> None:
        assert "/auth/token" in PUBLIC_PATHS

    def test_docs_is_public(self) -> None:
        assert "/docs" in PUBLIC_PATHS

    def test_oauth2_redirect_is_public(self) -> None:
        assert "/docs/oauth2-redirect" in PUBLIC_PATHS


# ---------------------------------------------------------------------------
# Queue facade dispatch
# ---------------------------------------------------------------------------


class TestQueueFacade:
    def test_memory_backend_by_default(self) -> None:
        with patch.object(settings, "job_queue_backend", "memory"):
            from app.workers.queue import _use_redis
            assert _use_redis() is False

    def test_redis_dispatch_detected(self) -> None:
        with patch.object(settings, "job_queue_backend", "redis"):
            from app.workers.queue import _use_redis
            assert _use_redis() is True

    def test_memory_create_and_get_job(self) -> None:
        with patch.object(settings, "job_queue_backend", "memory"):
            from app.workers.queue import create_job, get_job
            job = create_job("test.type", {"key": "value"})
            assert job.type == "test.type"
            assert job.status.value == "pending"

            fetched = get_job(job.job_id)
            assert fetched is not None
            assert fetched.job_id == job.job_id

    def test_memory_secret_scrubbing(self) -> None:
        with patch.object(settings, "job_queue_backend", "memory"):
            from app.workers.queue import create_job, get_job_input, clear_job_secrets
            job = create_job("test.type", {"key": "value", "api_key": "secret123"})
            job_input = get_job_input(job.job_id)
            assert job_input is not None
            assert job_input["api_key"] == "secret123"

            clear_job_secrets(job.job_id)
            job_input_after = get_job_input(job.job_id)
            assert job_input_after is not None
            assert "api_key" not in job_input_after


# ---------------------------------------------------------------------------
# Store facade dispatch
# ---------------------------------------------------------------------------


class TestStoreFacade:
    def test_memory_backend_by_default(self) -> None:
        with patch.object(settings, "vector_store_backend", "memory"):
            from app.services.retrieval_store import _use_milvus
            assert _use_milvus() is False

    def test_milvus_dispatch_detected(self) -> None:
        with patch.object(settings, "vector_store_backend", "milvus"):
            from app.services.retrieval_store import _use_milvus
            assert _use_milvus() is True

    def test_memory_add_and_search(self) -> None:
        with patch.object(settings, "vector_store_backend", "memory"):
            from app.services.retrieval_store import add_documents, search, clear_store

            clear_store()
            added = add_documents([
                {
                    "doc_id": "d1",
                    "chunk_id": "d1:c0",
                    "text": "hello world",
                    "vector": [1.0, 0.0, 0.0],
                    "metadata": {},
                }
            ])
            assert added == 1

            results = search([1.0, 0.0, 0.0], top_k=1)
            assert len(results) == 1
            assert results[0]["doc_id"] == "d1"
            assert results[0]["score"] > 0.9

            clear_store()

    def test_memory_list_documents(self) -> None:
        with patch.object(settings, "vector_store_backend", "memory"):
            from app.services.retrieval_store import add_documents, list_documents, clear_store

            clear_store()
            add_documents([
                {"doc_id": "d1", "chunk_id": "d1:c0", "text": "a", "vector": [1.0], "metadata": {}},
                {"doc_id": "d1", "chunk_id": "d1:c1", "text": "b", "vector": [1.0], "metadata": {}},
            ])
            docs = list_documents()
            assert len(docs) == 1
            assert docs[0]["chunk_count"] == 2
            clear_store()


# ---------------------------------------------------------------------------
# Settings – new fields exist with correct defaults
# ---------------------------------------------------------------------------


class TestNewSettings:
    def test_vector_store_backend_default(self) -> None:
        assert settings.vector_store_backend == "memory"

    def test_job_queue_backend_default(self) -> None:
        assert settings.job_queue_backend == "memory"

    def test_auth_disabled_by_default(self) -> None:
        assert settings.auth_enabled is False

    def test_milvus_defaults(self) -> None:
        assert settings.milvus_uri == "http://localhost:19530"
        assert settings.milvus_collection_name == "documind_chunks"
        assert settings.milvus_vector_dim == 768

    def test_redis_default(self) -> None:
        assert settings.redis_url == "redis://localhost:6379/0"

    def test_auth_defaults(self) -> None:
        assert settings.auth_secret_key == "change-me-in-production"
        assert settings.auth_algorithm == "HS256"
        assert settings.auth_access_token_expire_minutes == 30

    def test_worker_enabled_by_default(self) -> None:
        assert settings.worker_enabled is True


# ---------------------------------------------------------------------------
# Readiness probe — checks dict uses string values
# ---------------------------------------------------------------------------


class TestReadinessResponse:
    def test_readiness_check_values_are_strings(self) -> None:
        from app.schemas.common import ReadinessResponse
        r = ReadinessResponse(
            status="ok",
            checks={"queue_initialized": "ok", "model_manager_accessible": "ok"},
        )
        assert r.status == "ok"
        assert r.checks["queue_initialized"] == "ok"

    def test_readiness_degraded_when_check_fails(self) -> None:
        from app.schemas.common import ReadinessResponse
        r = ReadinessResponse(
            status="degraded",
            checks={"queue_initialized": "ok", "redis": "error: Connection refused"},
        )
        assert r.status == "degraded"
        assert "error" in r.checks["redis"]


# ---------------------------------------------------------------------------
# API-only mode (worker_enabled=False)
# ---------------------------------------------------------------------------


class TestApiOnlyMode:
    def test_worker_disabled_setting(self) -> None:
        with patch.object(settings, "worker_enabled", False):
            assert settings.worker_enabled is False

    def test_app_starts_without_worker(self) -> None:
        """When worker_enabled=False the app should still respond to requests."""
        with patch.object(settings, "worker_enabled", False):
            from fastapi.testclient import TestClient
            import app.main as m
            with TestClient(m.app) as client:
                r = client.get("/health/live")
                assert r.status_code == 200


# ---------------------------------------------------------------------------
# Health ready — memory backends return ok strings
# ---------------------------------------------------------------------------


class TestHealthReadyMemoryBackend:
    def test_ready_memory_backends_ok(self) -> None:
        with (
            patch.object(settings, "job_queue_backend", "memory"),
            patch.object(settings, "vector_store_backend", "memory"),
        ):
            from fastapi.testclient import TestClient
            import app.main as m
            with TestClient(m.app) as client:
                r = client.get("/health/ready")
                assert r.status_code == 200
                body = r.json()
                assert body["status"] == "ok"
                assert body["checks"]["queue_initialized"] == "ok"
                assert body["checks"]["model_manager_accessible"] == "ok"
                # memory mode — no redis/milvus keys expected
                assert "redis" not in body["checks"]
                assert "milvus" not in body["checks"]
