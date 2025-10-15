# add at top
from typing import Optional
from openai import OpenAI
import uuid

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from ..core.config import settings
from ..core.logging import logger

_client: Optional[QdrantClient] = None
_oa: Optional[OpenAI] = None

def client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    return _client

def openai_client() -> OpenAI:
    global _oa
    if _oa is None:
        _oa = OpenAI(api_key=settings.openai_api_key)
    return _oa

def ensure_collection():
    c = client()
    try:
        c.get_collection(settings.collection)
    except Exception:
        logger.info("creating_collection", name=settings.collection)
        c.recreate_collection(
            collection_name=settings.collection,
            vectors_config=qmodels.VectorParams(size=3072, distance=qmodels.Distance.COSINE),
        )

def embed(text: str) -> list[float]:
    """Return a single 3072-dim embedding."""
    oa = openai_client()
    out = oa.embeddings.create(model="text-embedding-3-large", input=text)
    return out.data[0].embedding

def search(question: str, top_k: int = 6):
    vec = embed(question)
    c = client()
    return c.search(
        collection_name=settings.collection,
        query_vector=vec,
        limit=top_k,
        with_payload=True,
    )

# (optional) tiny seeder so we can test end-to-end before real ingestion
def seed_demo():
    ensure_collection()
    c = client()
    points = [
        qmodels.PointStruct(
            id=str(uuid.uuid4()),
            vector=embed("AAOS recommends risk stratification and VTE prophylaxis following TKA/THA."),
            payload={
                "title": "AAOS TKA/THA Guideline (demo)",
                "document_id": "aaos_demo",
                "page": 12,
                "section": "VTE prophylaxis",
                "source_type": "AAOS",
                "precedence_rank": 2,
                "text": "AAOS statement (demo): consider chemoprophylaxis based on risk."
            },
        ),
        qmodels.PointStruct(
            id=str(uuid.uuid4()),
            vector=embed("Hospital policy requires nasal decolonization pre-op for joint replacement."),
            payload={
                "title": "Hospital Policy 42 (demo)",
                "document_id": "policy_demo",
                "page": 2,
                "section": "Pre-op decolonization",
                "source_type": "HOSPITAL_POLICY",
                "precedence_rank": 1,
                "text": "Policy (demo): mupirocin + chlorhexidine wash protocol."
            },
        ),
    ]
    c.upsert(collection_name=settings.collection, points=points)
    logger.info("seed_demo_done", points=len(points))
