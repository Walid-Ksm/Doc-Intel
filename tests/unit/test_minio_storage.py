import os
import pytest
from dotenv import load_dotenv

load_dotenv()

from app.infrastructure.storage.minio_storage import MinIOStorage


@pytest.fixture(scope="session")
def minio_storage():
    return MinIOStorage(
        endpoint_url=os.getenv("MINIO_ENDPOINT"),
        access_key=os.getenv("MINIO_ACCESS_KEY"),
        secret_key=os.getenv("MINIO_SECRET_KEY"),
        bucket_name=os.getenv("MINIO_BUCKET_NAME"),
    )


def test_upload_then_download_returns_same_bytes(minio_storage):
    original_bytes = b"Hello MinIO, this is a real pytest test."
    test_path = "tests/pytest_roundtrip_check.txt"

    minio_storage.upload(original_bytes, test_path)
    downloaded_bytes = minio_storage.download(test_path)

    assert downloaded_bytes == original_bytes


def test_upload_overwrites_existing_object_at_same_path(minio_storage):
    test_path = "tests/pytest_overwrite_check.txt"

    minio_storage.upload(b"first version", test_path)
    minio_storage.upload(b"second version", test_path)

    result = minio_storage.download(test_path)
    assert result == b"second version"
