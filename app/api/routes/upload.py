"""File upload endpoint for browser-based document submission."""

import logging
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, status

from app.core.settings import settings

router = APIRouter(prefix="/ocr", tags=["ocr"])

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".pdf"}


def _upload_dir() -> Path:
    """Return the configured upload directory, creating it if needed."""
    if settings.upload_dir:
        directory = Path(settings.upload_dir)
    else:
        directory = Path(tempfile.gettempdir()) / "documind_uploads"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


@router.post(
    "/upload",
    summary="Upload a document",
    description=(
        "Upload an image or PDF from your browser. Returns a server file path "
        "that can be passed to any endpoint expecting `file_path`."
    ),
    responses={
        400: {"description": "File type not allowed or file too large."},
    },
)
async def upload_document(file: UploadFile) -> dict[str, str]:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided.",
        )

    extension = Path(file.filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"File type '{extension}' is not allowed. "
                f"Accepted types: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            ),
        )

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    content = await file.read()
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds the {settings.max_upload_size_mb} MB size limit.",
        )

    safe_name = f"{uuid.uuid4().hex}{extension}"
    dest = _upload_dir() / safe_name
    dest.write_bytes(content)
    logger.info("Uploaded %s (%d bytes) → %s", file.filename, len(content), dest)

    return {"file_path": str(dest)}
