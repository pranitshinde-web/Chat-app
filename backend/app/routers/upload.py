import os
import uuid
import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.logging_config import get_logger
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.upload import UploadResponse

logger = get_logger(__name__)
router = APIRouter(tags=["Files"])

# ── Allowed extensions and their MIME types ───────────────────────────────────
ALLOWED_EXTENSIONS = {
    "jpg", "jpeg", "png", "gif", "webp",   # images
    "pdf", "doc", "docx", "txt", "zip",    # documents / archives
}

# Extension → canonical MIME whitelist (double-checked server-side)
ALLOWED_MIME_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "application/zip", "application/x-zip-compressed",
}


def _get_upload_dir() -> Path:
    """Return absolute Path to the uploads directory, creating it if needed."""
    upload_dir = Path(settings.UPLOAD_DIR)
    if not upload_dir.is_absolute():
        # Resolve relative to backend root (where the process runs from)
        upload_dir = Path.cwd() / upload_dir
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def _safe_filename(original: str) -> tuple[str, str]:
    """
    Return (safe_stored_name, extension) for an uploaded file.
    Generates a UUID-based name to prevent collisions and path injection.
    """
    original_lower = original.lower()
    # Strip leading dots / directory separators from the raw name
    stem = Path(original_lower).stem.lstrip("./\\")
    ext = Path(original_lower).suffix.lstrip(".").lower()
    stored_name = f"{uuid.uuid4().hex}.{ext}"
    return stored_name, ext


# ── POST /api/upload ──────────────────────────────────────────────────────────

@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a file",
    description=(
        "Accepts multipart/form-data. Validates file type and size. "
        "Saves the file to the local uploads directory and returns a URL."
    ),
)
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> UploadResponse:
    # ── 1. Extension validation ───────────────────────────────────────────────
    original_filename = file.filename or ""
    _, ext = _safe_filename(original_filename)

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"File type '.{ext}' is not allowed. "
                f"Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
            ),
        )

    # ── 2. MIME type validation (content-type header) ─────────────────────────
    content_type = file.content_type or ""
    # Strip parameters like '; charset=utf-8'
    mime_base = content_type.split(";")[0].strip().lower()
    if mime_base not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Content-Type '{mime_base}' is not permitted.",
        )

    # ── 3. Size validation (stream into memory with cap) ─────────────────────
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    chunk_size = 1024 * 64  # 64 KB chunks
    total_size = 0
    chunks: list[bytes] = []

    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total_size += len(chunk)
        if total_size > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=(
                    f"File exceeds the maximum allowed size of "
                    f"{settings.MAX_FILE_SIZE_MB} MB."
                ),
            )
        chunks.append(chunk)

    # ── 4. Persist to disk ────────────────────────────────────────────────────
    stored_name, _ = _safe_filename(original_filename)
    upload_dir = _get_upload_dir()
    dest_path = upload_dir / stored_name

    try:
        with open(dest_path, "wb") as f:
            for chunk in chunks:
                f.write(chunk)
    except OSError as exc:
        logger.error(f"Failed to write uploaded file: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save file. Please try again.",
        )

    file_url = f"/uploads/{stored_name}"
    logger.info(
        f"User {current_user.id} uploaded file '{original_filename}' "
        f"→ '{stored_name}' ({total_size} bytes)"
    )

    return UploadResponse(
        file_url=file_url,
        filename=stored_name,
        original_filename=original_filename,
        content_type=mime_base,
        size_bytes=total_size,
    )


# ── GET /uploads/{filename} ───────────────────────────────────────────────────

@router.get(
    "/uploads/{filename}",
    summary="Serve an uploaded file",
    description=(
        "Returns the raw file. Requires a valid Bearer token. "
        "Path traversal attempts are blocked."
    ),
)
async def serve_file(
    filename: str,
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    # ── Path traversal protection ─────────────────────────────────────────────
    # Reject any filename that contains directory separators or relative refs
    if any(c in filename for c in ("/", "\\", "..")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename.",
        )

    # Resolve absolute path and ensure it stays inside upload_dir
    upload_dir = _get_upload_dir()
    file_path = (upload_dir / filename).resolve()

    try:
        file_path.relative_to(upload_dir.resolve())
    except ValueError:
        # resolve() escaped the uploads root — path traversal detected
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename.",
        )

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found.",
        )

    # Guess MIME type from extension for a correct Content-Type response
    guessed_type, _ = mimetypes.guess_type(str(file_path))
    media_type = guessed_type or "application/octet-stream"

    return FileResponse(path=str(file_path), media_type=media_type, filename=filename)
