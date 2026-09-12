import boto3
from botocore.client import Config

from app.domain.interfaces.file_storage import FileStorageInterface
from app.domain.exceptions import StorageError


class MinIOStorage(FileStorageInterface):
    def __init__(
        self, endpoint_url: str, access_key: str, secret_key: str, bucket_name: str
    ):
        self._bucket_name = bucket_name
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4"),
        )

        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        existing_buckets = [b["Name"] for b in self._client.list_buckets()["Buckets"]]
        if self._bucket_name not in existing_buckets:
            self._client.create_bucket(Bucket=self._bucket_name)

    def upload(self, file_bytes: bytes, destination_path: str) -> str:
        try:
            self._client.put_object(
                Bucket=self._bucket_name,
                Key=destination_path,
                Body=file_bytes,
            )
            return destination_path
        except Exception as e:
            raise StorageError("upload", destination_path, e) from e

    def download(self, storage_path: str) -> bytes:
        try:
            response = self._client.get_object(
                Bucket=self._bucket_name, Key=storage_path
            )
            return response["Body"].read()
        except Exception as e:
            raise StorageError("download", storage_path, e) from e

    def delete(self, storage_path: str) -> None:
        try:
            self._client.delete_object(Bucket=self._bucket_name, Key=storage_path)
        except Exception as e:
            raise StorageError("delete", storage_path, e) from e
