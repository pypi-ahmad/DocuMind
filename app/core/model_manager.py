import asyncio
from datetime import datetime, timezone


class ModelManager:
    def __init__(self) -> None:
        self.active_provider: str | None = None
        self.active_model: str | None = None
        self.loaded_at: str | None = None
        self.busy: bool = False
        self._lock = asyncio.Lock()

    def get_status(self) -> dict[str, str | bool | None]:
        return {
            "active_provider": self.active_provider,
            "active_model": self.active_model,
            "busy": self.busy,
            "loaded_at": self.loaded_at,
        }

    async def activate(self, provider: str, model_name: str) -> dict[str, str | bool | None]:
        async with self._lock:
            if self.active_provider == provider and self.active_model == model_name:
                return {
                    **self.get_status(),
                    "message": "Requested model is already active",
                }

            message = "Model activated successfully"
            if self.active_provider is not None and self.active_model is not None:
                message = "Active model replaced successfully"

            self.active_provider = provider
            self.active_model = model_name
            self.loaded_at = datetime.now(timezone.utc).isoformat()
            self.busy = False

            return {
                **self.get_status(),
                "message": message,
            }

    async def deactivate(self) -> dict[str, str | bool]:
        async with self._lock:
            if self.active_provider is None and self.active_model is None:
                self.busy = False
                return {
                    "success": True,
                    "message": "No active model to deactivate",
                }

            self.active_provider = None
            self.active_model = None
            self.loaded_at = None
            self.busy = False

            return {
                "success": True,
                "message": "Model deactivated successfully",
            }

    def mark_busy(self) -> None:
        self.busy = True

    def mark_idle(self) -> None:
        self.busy = False


model_manager = ModelManager()