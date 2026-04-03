from typing import Any

from pydantic import BaseModel, Field


class PipelineSummary(BaseModel):
    pipeline_name: str
    description: str


class PipelineStepResult(BaseModel):
    step_name: str
    status: str
    output: dict[str, Any] | None = None
    error: str | None = None


class RunPipelineRequest(BaseModel):
    pipeline_name: str = Field(min_length=1)
    input: dict[str, Any]


class RunPipelineResponse(BaseModel):
    pipeline_name: str
    status: str
    steps: list[PipelineStepResult]
    final_output: dict[str, Any] | None = None