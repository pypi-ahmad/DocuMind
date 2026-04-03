from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class JobStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class CreateJobRequest(BaseModel):
    type: str
    input: dict[str, Any]


class JobResponse(BaseModel):
    job_id: str
    type: str
    status: JobStatus
    input: dict[str, Any]
    result: dict[str, Any] | None = None
    error: str | None = None
