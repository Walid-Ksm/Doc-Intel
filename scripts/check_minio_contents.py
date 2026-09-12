import os
from dotenv import load_dotenv

load_dotenv()

import boto3
from botocore.client import Config

client = boto3.client(
    "s3",
    endpoint_url=os.getenv("MINIO_ENDPOINT"),
    aws_access_key_id=os.getenv("MINIO_ACCESS_KEY"),
    aws_secret_access_key=os.getenv("MINIO_SECRET_KEY"),
    config=Config(signature_version="s3v4"),
)

response = client.list_objects_v2(Bucket=os.getenv("MINIO_BUCKET_NAME"))
for obj in response.get("Contents", []):
    print(obj["Key"], obj["Size"], "bytes")
