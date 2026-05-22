import uuid
from pathlib import Path

from fastapi import UploadFile

from config import settings


async def save_upload(file: UploadFile, sub_dir: str) -> str:
    """Write uploaded file to STORAGE_PATH/sub_dir/. Return relative storage_path."""
    base = Path(settings.storage_path) / sub_dir
    base.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename or "upload").name
    relative = f"{sub_dir}/{uuid.uuid4()}_{safe_name}"
    dest = Path(settings.storage_path) / relative
    content = await file.read()
    dest.write_bytes(content)
    await file.seek(0)
    return relative


def get_file_path(storage_path: str) -> Path:
    return Path(settings.storage_path) / storage_path
