"""
File Upload Service. Abstracts storage so the rest of the app never cares
whether files sit on local disk (dev) or Azure Blob Storage (production).
Switch via STORAGE_BACKEND env var without touching calling code.
"""
import os
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from fastapi import UploadFile, HTTPException, status

from app.core.config import settings


class StorageBackend(ABC):
    @abstractmethod
    def save(self, file: UploadFile, key: str) -> str:
        """Persist file, return a public/relative URL or path."""

    @abstractmethod
    def save_bytes(self, data: bytes, key: str) -> str:
        """Persist raw bytes (e.g. a generated PDF/Excel report) under the
        same storage backend as uploads, so generated exports are stored,
        served, and served consistently with everything else — reuses
        this class rather than a separate export-storage mechanism."""

    @abstractmethod
    def delete(self, key: str) -> None:
        ...


class LocalStorageBackend(StorageBackend):
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def save(self, file: UploadFile, key: str) -> str:
        dest = self.base_path / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            f.write(file.file.read())
        return f"/files/{key}"

    def save_bytes(self, data: bytes, key: str) -> str:
        dest = self.base_path / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            f.write(data)
        return f"/files/{key}"

    def delete(self, key: str) -> None:
        dest = self.base_path / key
        if dest.exists():
            dest.unlink()


class AzureBlobStorageBackend(StorageBackend):
    """
    Uses azure-storage-blob SDK. Kept import-local so the package is only
    required when STORAGE_BACKEND=azure_blob is actually selected.
    """
    def __init__(self, connection_string: str, container: str):
        from azure.storage.blob import BlobServiceClient  # lazy import
        self.client = BlobServiceClient.from_connection_string(connection_string)
        self.container = container
        try:
            self.client.create_container(container)
        except Exception:
            pass  # container already exists

    def save(self, file: UploadFile, key: str) -> str:
        blob_client = self.client.get_blob_client(container=self.container, blob=key)
        blob_client.upload_blob(file.file.read(), overwrite=True)
        return blob_client.url

    def save_bytes(self, data: bytes, key: str) -> str:
        blob_client = self.client.get_blob_client(container=self.container, blob=key)
        blob_client.upload_blob(data, overwrite=True)
        return blob_client.url

    def delete(self, key: str) -> None:
        blob_client = self.client.get_blob_client(container=self.container, blob=key)
        blob_client.delete_blob(delete_snapshots="include")


def get_storage_backend() -> StorageBackend:
    if settings.STORAGE_BACKEND == "azure_blob":
        return AzureBlobStorageBackend(settings.AZURE_STORAGE_CONNECTION_STRING, settings.AZURE_STORAGE_CONTAINER)
    return LocalStorageBackend(settings.LOCAL_STORAGE_PATH)


class FileUploadService:
    def __init__(self):
        self.backend = get_storage_backend()

    def validate(self, file: UploadFile) -> None:
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext not in settings.ALLOWED_UPLOAD_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type '{ext}' is not allowed. Allowed types: {', '.join(settings.ALLOWED_UPLOAD_EXTENSIONS)}",
            )

    def upload(self, file: UploadFile, entity_type: str, entity_id: int) -> dict:
        self.validate(file)
        file.file.seek(0, os.SEEK_END)
        size = file.file.tell()
        file.file.seek(0)
        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if size > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB",
            )

        ext = os.path.splitext(file.filename or "")[1].lower()
        key = f"{entity_type}/{entity_id}/{uuid.uuid4().hex}{ext}"
        url = self.backend.save(file, key)

        return {
            "file_name": file.filename,
            "file_path": key,
            "file_url": url,
            "file_size_bytes": size,
            "mime_type": file.content_type or "application/octet-stream",
            "storage_backend": settings.STORAGE_BACKEND,
        }

    def save_generated_bytes(self, data: bytes, file_name: str, mime_type: str, entity_type: str, entity_id: int) -> dict:
        """Same storage backend and same dict shape as upload() (both are
        meant to be passed straight into an Attachment record), just for
        content the server generated itself — e.g. a PDF/Excel report
        export — rather than something a person uploaded."""
        ext = os.path.splitext(file_name)[1].lower()
        key = f"{entity_type}/{entity_id}/{uuid.uuid4().hex}{ext}"
        url = self.backend.save_bytes(data, key)
        return {
            "file_name": file_name,
            "file_path": key,
            "file_url": url,
            "file_size_bytes": len(data),
            "mime_type": mime_type,
            "storage_backend": settings.STORAGE_BACKEND,
        }

    def delete(self, key: str) -> None:
        self.backend.delete(key)
