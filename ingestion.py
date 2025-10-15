import os, tempfile, logging
from types import SimpleNamespace as NS
from typing import List, Dict, Any
import boto3
from botocore.config import Config as BotoConfig
from pypdf import PdfReader
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from openai import OpenAI
from ..core.config import settings

log = logging.getLogger("ingestion")
log.setLevel(logging.INFO)

STATUS: Dict[str, Dict[str, Any]] = {}
EMBED_MODEL = "text-embedding-3-small"  # 1536 dims
PRECEDENCE = {"AAOS":100, "HOSPITAL_POLICY":90, "PEER_REVIEW":80, "OTHER":50}

def _s3():
    return boto3.client("s3", region_name=settings.aws_region, config=BotoConfig(retries={"max_attempts": 3}))

def _qdrant():
    kw = dict(url=settings.qdrant_url, timeout=90)
    if settings.qdrant_api_key: kw["api_key"] = settings.qdrant_api_key
    return QdrantClient(**kw)

def _openai(): return OpenAI(api_key=settings.openai_api_key)

def _ensure_collection(cli: QdrantClient):
    try: cli.get_collection(settings.collection)
    except Exception:
        cli.recreate_collection(collection_name=settings.collection, vectors_config=VectorParams(size=1536, distance=Distance.COSINE))

def _download(bucket: str, key: str) -> str:
    _s3().head_object(Bucket=bucket, Key=key)  # raises if missing
    fd, path = tempfile.mkstemp(prefix="doc-", suffix=os.path.splitext(key)[1]); os.close(fd)
    with open(path, "wb") as f: _s3().download_fileobj(bucket, key, f)
    return path

def _parse_pdf_fast(path: str) -> List[NS]:
    r = PdfReader(path); out=[]
    for i, p in enumerate(r.pages):
        t = (p.extract_text() or "").strip()
        if t: out.append(NS(text=t, metadata=NS(page_number=i+1, category=None)))
    return out

def _split(text: str, max_chars=1800, overlap=200) -> List[str]:
    if not text: return []
    chunks=[]; i=0; L=len(text)
    while i < L:
        j=min(L, i+max_chars)
        cut=text.rfind(". ", i, j); cut=j if cut==-1 or cut < i+max_chars*0.6 else cut+1
        piece=text[i:cut].strip();  piece and chunks.append(piece)
        i=max(cut-overlap,0)
    return chunks

def _to_chunks(elems: List[NS]) -> List[Dict[str, Any]]:
    out=[]
    for el in elems:
        txt=(getattr(el,"text","") or "").strip()
        if not txt: continue
        page=getattr(getattr(el,"metadata",NS()),"page_number",None)
        for sub in _split(txt): out.append({"text":sub,"page":page,"section":None})
    return out

def _embed(texts: List[str]) -> List[List[float]]:
    if not texts: return []
    cli=_openai(); out=[]; B=128
    for i in range(0,len(texts),B):
        resp=cli.embeddings.create(model=EMBED_MODEL, input=texts[i:i+B])
        out.extend([d.embedding for d in resp.data])
    return out

def process_document(s3_key: str, source_type: str = "OTHER", org_id: str = "demo"):
    bucket=settings.s3_bucket; doc_id=s3_key
    STATUS[doc_id]={"state":"processing"}
    log.info("INGEST start %s", s3_key)
    try:
        path=_download(bucket, s3_key); log.info("Downloaded %s", path)
        elems=_parse_pdf_fast(path)
        if not elems: raise RuntimeError("No text extracted (PDF may be scanned). Use searchable PDF or add OCR.")
        chunks=_to_chunks(elems); log.info("Chunks pre-embed=%d", len(chunks))
        vecs=_embed([c["text"] for c in chunks])
        if len(vecs)!=len(chunks): raise RuntimeError("Embedding mismatch")
        cli=_qdrant(); _ensure_collection(cli)
        rank=PRECEDENCE.get(source_type.upper(), PRECEDENCE["OTHER"])
        points=[]
        for i,(c,v) in enumerate(zip(chunks,vecs)):
            pid=f"{doc_id}:{i}"
            payload={"document_id":doc_id,"org_id":org_id,"source_type":source_type,"precedence":rank,
                     "page":c.get("page"),"section":c.get("section"),"text":c["text"]}
            points.append(PointStruct(id=pid, vector=v, payload=payload))
        cli.upsert(collection_name=settings.collection, points=points)
        STATUS[doc_id]={"state":"done","chunks":len(chunks),"vectors":len(vecs)}
        log.info("INGEST done %s chunks=%d", s3_key, len(chunks))
    except Exception as e:
        STATUS[doc_id]={"state":"error","error":str(e)}
        log.exception("INGEST failed %s: %s", s3_key, e)
        raise

