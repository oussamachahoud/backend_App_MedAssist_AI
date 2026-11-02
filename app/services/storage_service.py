"""
app/services/storage_service.py
MinIO / S3 object storage service for MedAssist AI V2.
Handles storing patient lesion photos and generated Grad-CAM++ explanation maps.
Provides instant local fallback with zero-timeout socket detection when MinIO is offline.
"""

import io
import os
import socket
import time
from datetime import timedelta
from pathlib import Path
from typing import Optional
from loguru import logger
from minio import Minio
from minio.error import S3Error

from app.core.config import get_settings


class StorageService:
    def __init__(self):
        self.settings = get_settings()
        self._client: Optional[Minio] = None
        self._minio_online: Optional[bool] = None
        self._last_minio_check: float = 0.0

    @property
    def local_uploads_dir(self) -> Path:
        base_dir = Path(__file__).resolve().parent.parent.parent
        uploads = base_dir / "uploads"
        uploads.mkdir(parents=True, exist_ok=True)
        return uploads

    def _save_locally(self, object_name: str, image_bytes: bytes) -> str:
        dest = self.local_uploads_dir / object_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(image_bytes)
        logger.info(f"💾 Saved image locally (fallback): {dest}")
        return object_name

    def is_minio_reachable(self) -> bool:
        """
        Fast non-blocking socket check to verify if MinIO server port is open.
        Cached for 15 seconds to avoid repeating socket checks on every request.
        """
        now = time.time()
        if self._minio_online is not None and (now - self._last_minio_check) < 15.0:
            return self._minio_online

        self._last_minio_check = now
        endpoint = self.settings.minio_endpoint.replace("http://", "").replace("https://", "")
        if ":" in endpoint:
            host, port_str = endpoint.split(":", 1)
            port = int(port_str)
        else:
            host = endpoint
            port = 443 if self.settings.minio_secure else 9000

        try:
            with socket.create_connection((host, port), timeout=0.15):
                self._minio_online = True
        except (OSError, socket.timeout):
            self._minio_online = False

        return self._minio_online

    @property
    def client(self) -> Minio:
        if self._client is None:
            self._client = Minio(
                endpoint=self.settings.minio_endpoint,
                access_key=self.settings.minio_access_key,
                secret_key=self.settings.minio_secret_key,
                secure=self.settings.minio_secure,
                region="us-east-1",
            )
        return self._client

    def ensure_bucket_exists(self, bucket_name: Optional[str] = None) -> None:
        """Ensure the specified bucket exists in MinIO; create it if absent."""
        if not self.is_minio_reachable():
            return

        bucket = bucket_name or self.settings.minio_bucket_analyses
        try:
            if not self.client.bucket_exists(bucket):
                self.client.make_bucket(bucket)
                logger.info(f"Created MinIO bucket '{bucket}'")
            else:
                logger.debug(f"MinIO bucket '{bucket}' already exists")
        except Exception as e:
            logger.warning(f"MinIO bucket check skipped/unavailable for '{bucket}': {e}")

    def upload_image(
        self,
        image_bytes: bytes,
        object_name: str,
        content_type: str = "image/jpeg",
        bucket_name: Optional[str] = None,
    ) -> str:
        """Upload raw image bytes to MinIO with instantaneous local disk fallback."""
        if not self.is_minio_reachable():
            return self._save_locally(object_name, image_bytes)

        bucket = bucket_name or self.settings.minio_bucket_analyses
        try:
            self.ensure_bucket_exists(bucket)
            data_stream = io.BytesIO(image_bytes)
            self.client.put_object(
                bucket_name=bucket,
                object_name=object_name,
                data=data_stream,
                length=len(image_bytes),
                content_type=content_type,
            )
            logger.info(f"Uploaded object '{object_name}' to MinIO bucket '{bucket}'")
            return object_name
        except Exception as e:
            logger.warning(f"MinIO upload unavailable ({e}), using local filesystem fallback for '{object_name}'")
            return self._save_locally(object_name, image_bytes)

    def get_presigned_url(
        self,
        object_name: str,
        expires_seconds: int = 3600,
        bucket_name: Optional[str] = None,
    ) -> str:
        """Generate a presigned GET URL, or return static /uploads/... local URL if MinIO is unavailable."""
        local_path = self.local_uploads_dir / object_name
        if local_path.is_file() or not self.is_minio_reachable():
            return f"/uploads/{object_name}"

        bucket = bucket_name or self.settings.minio_bucket_analyses
        try:
            url = self.client.presigned_get_object(
                bucket_name=bucket,
                object_name=object_name,
                expires=timedelta(seconds=expires_seconds),
            )
            return url
        except Exception as e:
            logger.warning(f"Error generating presigned URL for '{object_name}': {e}")
            return f"/uploads/{object_name}"

    def delete_image(
        self,
        object_name: str,
        bucket_name: Optional[str] = None,
    ) -> bool:
        """Delete an object from MinIO and local fallback."""
        deleted = False
        local_path = self.local_uploads_dir / object_name
        if local_path.is_file():
            try:
                local_path.unlink()
                deleted = True
            except Exception as e:
                logger.warning(f"Failed to delete local fallback '{local_path}': {e}")

        if not self.is_minio_reachable():
            return deleted

        bucket = bucket_name or self.settings.minio_bucket_analyses
        try:
            self.client.remove_object(bucket_name=bucket, object_name=object_name)
            logger.info(f"Deleted '{object_name}' from MinIO bucket '{bucket}'")
            deleted = True
        except Exception as e:
            logger.warning(f"MinIO delete skipped for '{object_name}': {e}")

        return deleted


storage_service = StorageService()
