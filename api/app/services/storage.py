"""Cloudflare R2 (or AWS S3) object storage helpers."""
import uuid
from pathlib import Path

import boto3
from botocore.config import Config

from app.config import settings


def _client():
    endpoint = f"https://{settings.r2_account_id}.r2.cloudflarestorage.com"
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def upload_file(local_path: str | Path, key: str, content_type: str = "application/octet-stream") -> str:
    """Upload a local file to R2 and return its public URL."""
    _client().upload_file(
        str(local_path),
        settings.r2_bucket_name,
        key,
        ExtraArgs={"ContentType": content_type},
    )
    return f"{settings.r2_public_url}/{key}"


def upload_fileobj(fileobj, key: str, content_type: str = "application/octet-stream") -> str:
    """Upload a file-like object to R2 and return its public URL."""
    _client().upload_fileobj(
        fileobj,
        settings.r2_bucket_name,
        key,
        ExtraArgs={"ContentType": content_type},
    )
    return f"{settings.r2_public_url}/{key}"


def delete_file(key: str) -> None:
    _client().delete_object(Bucket=settings.r2_bucket_name, Key=key)


def game_raw_key(game_id: uuid.UUID, filename: str) -> str:
    ext = Path(filename).suffix
    return f"raw/{game_id}{ext}"


def clip_key(game_id: uuid.UUID, clip_id: uuid.UUID) -> str:
    return f"clips/{game_id}/{clip_id}.mp4"


def thumbnail_key(game_id: uuid.UUID, clip_id: uuid.UUID) -> str:
    return f"thumbs/{game_id}/{clip_id}.jpg"
