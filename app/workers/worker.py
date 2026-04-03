import asyncio
import logging
from typing import Any

from app.core.pipelines import PIPELINE_DEFINITIONS
from app.schemas.jobs import JobStatus
from app.schemas.ocr import POSTPROCESS_TASKS
from app.services.document_qa import ALLOWED_RETRIEVAL_MODES, answer_document_query
from app.services.indexing import extract_ocr_document, index_ocr_document
from app.services.pipeline_runner import PipelineNotFoundError, run_pipeline
from app.services.ocr_postprocess import run_ocr_postprocess
from app.workers.queue import clear_job_secrets, dequeue_job, get_job, get_job_input, update_job

logger = logging.getLogger(__name__)

_worker_task: asyncio.Task[None] | None = None


async def _simulate_job_execution(job_input: dict) -> dict[str, str]:
    await asyncio.sleep(2)
    if job_input.get("should_fail") is True:
        raise RuntimeError("Simulated job failure")
    return {"message": "Job completed successfully"}


def _get_required_file_path(job_input: dict[str, Any]) -> str:
    file_path = job_input.get("file_path")
    if not isinstance(file_path, str) or not file_path.strip():
        raise ValueError("ocr.extract jobs require a non-empty file_path")
    return file_path


async def _process_ocr_extract_job(job_input: dict[str, Any]) -> dict[str, Any]:
    file_path = _get_required_file_path(job_input)

    engine_value = job_input.get("engine")
    if engine_value is not None and not isinstance(engine_value, str):
        raise ValueError("ocr.extract job engine must be a string when provided")

    prefer_structure = job_input.get("prefer_structure", False)
    if not isinstance(prefer_structure, bool):
        raise ValueError("ocr.extract job prefer_structure must be a boolean")

    _, result = await extract_ocr_document(
        file_path=file_path,
        ocr_engine=engine_value,
        prefer_structure=prefer_structure,
    )
    return result


def _get_required_str(job_input: dict[str, Any], key: str, *, job_type: str) -> str:
    value = job_input.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{job_type} jobs require a non-empty {key}")
    return value.strip()


async def _process_ocr_postprocess_job(job_input: dict[str, Any]) -> dict[str, Any]:
    ocr_result = job_input.get("ocr_result")
    if not isinstance(ocr_result, dict):
        raise ValueError("ocr.postprocess jobs require ocr_result as a dict")

    task = _get_required_str(job_input, "task", job_type="ocr.postprocess")
    if task not in POSTPROCESS_TASKS:
        raise ValueError(
            f"Invalid task '{task}'. Must be one of: {', '.join(sorted(POSTPROCESS_TASKS))}"
        )

    provider = _get_required_str(job_input, "provider", job_type="ocr.postprocess")
    model_name = _get_required_str(job_input, "model_name", job_type="ocr.postprocess")

    api_key = job_input.get("api_key")
    if api_key is not None and not isinstance(api_key, str):
        raise ValueError("ocr.postprocess job api_key must be a string when provided")

    temperature = job_input.get("temperature")
    if temperature is not None:
        if not isinstance(temperature, (int, float)) or temperature < 0:
            raise ValueError("ocr.postprocess job temperature must be a non-negative number")
        temperature = float(temperature)

    max_output_tokens = job_input.get("max_output_tokens")
    if max_output_tokens is not None:
        if not isinstance(max_output_tokens, int) or max_output_tokens <= 0:
            raise ValueError("ocr.postprocess job max_output_tokens must be a positive integer")

    return await run_ocr_postprocess(
        ocr_result=ocr_result,
        task=task,
        provider=provider,
        model_name=model_name,
        api_key=api_key,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
    )


async def _process_pipeline_run_job(job_input: dict[str, Any]) -> dict[str, Any]:
    pipeline_name = _get_required_str(job_input, "pipeline_name", job_type="pipeline.run")
    if pipeline_name not in PIPELINE_DEFINITIONS:
        raise PipelineNotFoundError(f"Pipeline '{pipeline_name}' not found")

    input_data = job_input.get("input")
    if not isinstance(input_data, dict):
        raise ValueError("pipeline.run jobs require input as a dict")

    pipeline_input = dict(input_data)
    api_key = job_input.get("api_key")
    if api_key is not None:
        if not isinstance(api_key, str):
            raise ValueError("pipeline.run job api_key must be a string when provided")
        pipeline_input["api_key"] = api_key

    return await run_pipeline(pipeline_name, pipeline_input)


async def _process_retrieval_index_ocr_job(job_input: dict[str, Any]) -> dict[str, Any]:
    doc_id = _get_required_str(job_input, "doc_id", job_type="retrieval.index_ocr")
    file_path = _get_required_str(job_input, "file_path", job_type="retrieval.index_ocr")
    embedding_provider = _get_required_str(job_input, "embedding_provider", job_type="retrieval.index_ocr")
    embedding_model_name = _get_required_str(job_input, "embedding_model_name", job_type="retrieval.index_ocr")

    ocr_engine = job_input.get("ocr_engine")
    if ocr_engine is not None and not isinstance(ocr_engine, str):
        raise ValueError("retrieval.index_ocr job ocr_engine must be a string when provided")

    prefer_structure = job_input.get("prefer_structure", False)
    if not isinstance(prefer_structure, bool):
        raise ValueError("retrieval.index_ocr job prefer_structure must be a boolean")

    api_key = job_input.get("api_key")
    if api_key is not None and not isinstance(api_key, str):
        raise ValueError("retrieval.index_ocr job api_key must be a string when provided")

    metadata = job_input.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        raise ValueError("retrieval.index_ocr job metadata must be a dict when provided")

    return await index_ocr_document(
        doc_id=doc_id,
        file_path=file_path,
        ocr_engine=ocr_engine,
        prefer_structure=prefer_structure,
        embedding_provider=embedding_provider,
        embedding_model_name=embedding_model_name,
        api_key=api_key,
        metadata=metadata,
    )


async def _process_retrieval_qa_job(job_input: dict[str, Any]) -> dict[str, Any]:
    query = _get_required_str(job_input, "query", job_type="retrieval.qa")
    provider = _get_required_str(job_input, "provider", job_type="retrieval.qa")
    model_name = _get_required_str(job_input, "model_name", job_type="retrieval.qa")

    api_key = job_input.get("api_key")
    if api_key is not None and not isinstance(api_key, str):
        raise ValueError("retrieval.qa job api_key must be a string when provided")

    retrieval_mode = job_input.get("retrieval_mode", "hybrid")
    if not isinstance(retrieval_mode, str) or retrieval_mode.strip().lower() not in ALLOWED_RETRIEVAL_MODES:
        raise ValueError("retrieval_mode must be one of: dense, hybrid")

    top_k = job_input.get("top_k", 5)
    if not isinstance(top_k, int) or top_k <= 0:
        raise ValueError("retrieval.qa job top_k must be a positive integer")

    use_rerank = job_input.get("use_rerank", True)
    if not isinstance(use_rerank, bool):
        raise ValueError("retrieval.qa job use_rerank must be a boolean")

    rerank_top_k = job_input.get("rerank_top_k", 5)
    if use_rerank and (not isinstance(rerank_top_k, int) or rerank_top_k <= 0):
        raise ValueError("retrieval.qa job rerank_top_k must be a positive integer when use_rerank is true")

    temperature = job_input.get("temperature")
    if temperature is not None:
        if not isinstance(temperature, (int, float)) or temperature < 0:
            raise ValueError("retrieval.qa job temperature must be a non-negative number")
        temperature = float(temperature)

    max_output_tokens = job_input.get("max_output_tokens")
    if max_output_tokens is not None:
        if not isinstance(max_output_tokens, int) or max_output_tokens <= 0:
            raise ValueError("retrieval.qa job max_output_tokens must be a positive integer")

    return await answer_document_query(
        query=query,
        provider=provider,
        model_name=model_name,
        api_key=api_key,
        retrieval_mode=retrieval_mode,
        top_k=top_k,
        use_rerank=use_rerank,
        rerank_top_k=rerank_top_k,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
    )


async def _execute_job(job_type: str, job_input: dict[str, Any]) -> dict[str, Any]:
    if job_type == "ocr.extract":
        return await _process_ocr_extract_job(job_input)

    if job_type == "ocr.postprocess":
        return await _process_ocr_postprocess_job(job_input)

    if job_type == "retrieval.index_ocr":
        return await _process_retrieval_index_ocr_job(job_input)

    if job_type == "retrieval.qa":
        return await _process_retrieval_qa_job(job_input)

    if job_type == "pipeline.run":
        return await _process_pipeline_run_job(job_input)

    return await _simulate_job_execution(job_input)


async def _process_job(job_id: str) -> None:
    job = get_job(job_id)
    if job is None:
        logger.warning("Job %s not found, skipping", job_id)
        return

    job_input = get_job_input(job_id)
    if job_input is None:
        logger.warning("Job %s input not found, skipping", job_id)
        return

    update_job(job_id, status=JobStatus.PROCESSING)
    logger.info("Processing job %s (type=%s)", job_id, job.type)

    try:
        result = await _execute_job(job.type, job_input)
        if result.get("status") == "failed":
            failed_step = next(
                (step for step in result.get("steps", []) if step.get("status") == "failed"),
                None,
            )
            update_job(
                job_id,
                status=JobStatus.FAILED,
                result=result,
                error=(failed_step or {}).get("error", f"Pipeline '{job.type}' failed"),
            )
            logger.info("Job %s failed", job_id)
            return

        update_job(
            job_id,
            status=JobStatus.COMPLETED,
            result=result,
        )
        logger.info("Job %s completed", job_id)
    except Exception as exc:
        update_job(job_id, status=JobStatus.FAILED, error=str(exc))
        logger.exception("Job %s failed", job_id)
    finally:
        clear_job_secrets(job_id)


async def _run_worker() -> None:
    logger.info("Background worker started")
    while True:
        job_id = await dequeue_job()
        await _process_job(job_id)


def start_worker() -> None:
    global _worker_task
    if _worker_task is not None and not _worker_task.done():
        return
    _worker_task = asyncio.create_task(_run_worker())


async def stop_worker() -> None:
    global _worker_task
    if _worker_task is not None:
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
        _worker_task = None
    logger.info("Background worker stopped")
