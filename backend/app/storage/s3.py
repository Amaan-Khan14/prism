"""S3ArtifactStore — AWS S3 implementation for production.

Objects are stored with SSE-S3 server-side encryption (the bucket policy
already enforces encryption; we request it explicitly for defence-in-depth).
The bucket must be private; we never produce public URLs — callers retrieve
raw bytes through :meth:`get` and serve them via the backend.

Authentication uses the AWS SDK's default credential chain so local
``~/.aws`` profiles and an EC2 instance role both work without any
long-lived keys in source control.

Requires ``boto3`` (declared in ``requirements.txt``).
"""
from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from app.storage.base import ArtifactStore, StoredArtifact

if TYPE_CHECKING:
    import boto3 as _boto3  # pragma: no cover


class S3ArtifactStore(ArtifactStore):
    """Stores artifacts in a private S3 bucket.

    Args:
        bucket_name: Name of the target S3 bucket.
        region_name: AWS region (e.g. ``"ap-south-1"``).
            Passed to the boto3 session so the SDK resolves the correct
            regional endpoint; the bucket must already exist in this region.
        endpoint_url: Optional override for the S3 endpoint, used only in
            tests to point at a local stub (e.g. moto / localstack).
    """

    def __init__(
        self,
        bucket_name: str,
        region_name: str,
        endpoint_url: str | None = None,
    ) -> None:
        import boto3  # imported lazily so missing boto3 only fails at S3 init

        self._bucket = bucket_name
        self._client = boto3.client(
            "s3",
            region_name=region_name,
            **({"endpoint_url": endpoint_url} if endpoint_url else {}),
        )

    # ------------------------------------------------------------------
    # Interface implementation
    # ------------------------------------------------------------------

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> StoredArtifact:
        """Upload *data* to S3 under *key*.

        The bucket policy already requires HTTPS and SSE-S3; we also set
        ``ServerSideEncryption="AES256"`` explicitly for defence-in-depth.
        """
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            ServerSideEncryption="AES256",
        )
        return StoredArtifact(
            key=key,
            size_bytes=len(data),
            sha256=_sha256(data),
        )

    def get(self, key: str) -> bytes:
        """Download and return raw bytes for *key*.  Raises :exc:`KeyError` if missing."""
        from botocore.exceptions import ClientError

        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            return response["Body"].read()
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code in ("NoSuchKey", "404"):
                raise KeyError(f"Artifact not found in S3: {key!r}") from exc
            raise

    def delete(self, key: str) -> None:
        """Delete *key* from S3.  No-op if the key does not exist."""
        self._client.delete_object(Bucket=self._bucket, Key=key)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
