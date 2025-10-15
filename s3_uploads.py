import uuid
import boto3
from botocore.config import Config as BotoConfig
from ..core.config import settings

_s3 = None
def s3():
    global _s3
    if _s3 is None:
        _s3 = boto3.client(
            "s3",
            region_name=settings.aws_region,
            config=BotoConfig(retries={"max_attempts": 3}),
        )
    return _s3

def new_object_key(org_id: str, filename: str) -> str:
    # keep original extension if present
    ext = filename.split(".")[-1].lower() if "." in filename else "bin"
    return f"uploads/{org_id}/{uuid.uuid4().hex}.{ext}"

def presign_post(org_id: str, filename: str, content_type: str = "application/octet-stream"):
    key = new_object_key(org_id, filename)
    fields = {"Content-Type": content_type}
    conditions = [
        {"Content-Type": content_type},
        ["content-length-range", 1, 50 * 1024 * 1024],  # max 50 MB
    ]
    resp = s3().generate_presigned_post(
        Bucket=settings.s3_bucket,
        Key=key,
        Fields=fields,
        Conditions=conditions,
        ExpiresIn=settings.s3_presign_expiry,
    )
    # match router’s expected shape
    return {"bucket": settings.s3_bucket, "key": key, **resp}

