from typing import Annotated

from fastapi import APIRouter, Body

from app.core.model_manager import model_manager
from app.schemas.runtime import ActivateModelRequest, ActivateModelResponse, DeactivateModelResponse, RuntimeStatusResponse

router = APIRouter(prefix="/runtime", tags=["runtime"])

_ACTIVATE_MODEL_EXAMPLES = {
    "ollama": {
        "summary": "Activate an Ollama model",
        "value": {
            "provider": "ollama",
            "model_name": "llama3",
        },
    }
}


@router.get(
    "/status",
    response_model=RuntimeStatusResponse,
    summary="Get runtime status",
    description="Return the currently active model provider, model name, and busy state.",
)
def get_runtime_status() -> RuntimeStatusResponse:
    return RuntimeStatusResponse(**model_manager.get_status())


@router.post(
    "/activate",
    response_model=ActivateModelResponse,
    summary="Activate a model",
    description="Activate the selected provider/model pair for subsequent runtime operations.",
)
async def activate_model(
    payload: Annotated[ActivateModelRequest, Body(openapi_examples=_ACTIVATE_MODEL_EXAMPLES)],
) -> ActivateModelResponse:
    response = await model_manager.activate(payload.provider, payload.model_name)
    return ActivateModelResponse(**response)


@router.post(
    "/deactivate",
    response_model=DeactivateModelResponse,
    summary="Deactivate the active model",
    description="Unload the currently active model from the runtime manager.",
)
async def deactivate_model() -> DeactivateModelResponse:
    response = await model_manager.deactivate()
    return DeactivateModelResponse(**response)