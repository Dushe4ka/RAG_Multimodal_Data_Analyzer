from __future__ import annotations

from datetime import timedelta
from io import BytesIO

from minio import Minio
from minio.error import S3Error

from config import settings


class MinioService:
    def __init__(self):
        self.client = Minio(
            endpoint=settings.S3_ENDPOINT,
            access_key=settings.S3_ACCESS_KEY,
            secret_key=settings.S3_SECRET_KEY,
            secure=settings.S3_SECURE,
        )
        self.bucket = settings.S3_BUCKET_UPLOADS

    def ensure_bucket(self) -> None:
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def upload_bytes(self, object_key: str, content: bytes, content_type: str) -> str:
        self.ensure_bucket()
        self.client.put_object(
            bucket_name=self.bucket,
            object_name=object_key,
            data=BytesIO(content),
            length=len(content),
            content_type=content_type,
        )
        return object_key

    def presigned_get_url(self, object_key: str) -> str:
        return self.client.presigned_get_object(
            bucket_name=self.bucket,
            object_name=object_key,
            expires=timedelta(seconds=settings.S3_PRESIGNED_EXPIRE_SEC),
        )

    def stat(self, object_key: str):
        try:
            return self.client.stat_object(self.bucket, object_key)
        except S3Error:
            return None

    def delete(self, object_key: str) -> None:
        self.client.remove_object(self.bucket, object_key)
