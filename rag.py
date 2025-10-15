import time
from fastapi import APIRouter, HTTPException
from ..models.schemas import QueryRequest, Answer, Citation
from ..core.logging import logger
from ..services import retrieval

router = APIRouter()

@router.post("/query", response_model=Answer)
async def rag_query(body: QueryRequest):
    t0 = time.time()
    q = body.question.strip()

    # Guardrails (very light MVP)
    ql = q.lower()
    if any(x in ql for x in ["chest pain", "shortness of breath", "suicid", "overdose"]):
        raise HTTPException(status_code=400, detail="This service can't provide emergency advice. Call your local emergency number.")

    retrieval.ensure_collection()
    hits = retrieval.search(q, top_k=6)

    if not hits:
        answer_text = "I couldn’t find an approved orthopedic source for that. Please contact your clinic."
        citations = []
    else:
        # naive summary for now: echo the most relevant payload text + list citations
        top = hits[0].payload
        answer_text = top.get("text", "Found relevant guidance (demo).")
        citations = []
        for h in hits[:3]:
            p = h.payload or {}
            citations.append(
                Citation(
                    title=p.get("title", "Unknown"),
                    document_id=p.get("document_id", "unknown"),
                    page=p.get("page"),
                    section=p.get("section"),
                )
            )

    latency_ms = int((time.time() - t0) * 1000)
    logger.info("rag_query", latency_ms=latency_ms, k=len(hits or []))
    return Answer(answer=answer_text, citations=citations, guardrails={"in_scope": True, "emergency": False}, latency_ms=latency_ms)

# Dev-only seed route (remove in prod)
@router.post("/dev/seed")
async def dev_seed():
    retrieval.seed_demo()
    return {"status": "seeded"}

