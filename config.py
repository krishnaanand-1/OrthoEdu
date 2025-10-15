from pydantic import BaseModel
import os
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

class Settings(BaseModel):
    env: str = os.getenv("ENV", "dev")
    # OpenAI / Qdrant
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    qdrant_url: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_api_key: Optional[str] = os.getenv("QDRANT_API_KEY")
    collection: str = os.getenv("QDRANT_COLLECTION", "org_demo_chunks")
    max_context_tokens: int = int(os.getenv("MAX_CONTEXT_TOKENS", "3500"))

    # AWS / S3
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    s3_bucket: str = os.getenv("S3_BUCKET", "clinical-rag-uploads-dev")
    s3_presign_expiry: int = int(os.getenv("S3_PRESIGN_EXPIRY", "900"))  # seconds

settings = Settings()

