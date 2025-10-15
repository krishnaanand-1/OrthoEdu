from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from ..services.s3_uploads import presign_post
from ..services.ingestion import process_document, STATUS

router = APIRouter()

class UploadInitRequest(BaseModel):
    filename: str
    content_type: str = "application/pdf"
    org_id: str = "demo"

class UploadInitResponse(BaseModel):
    upload_url: str
    fields: dict
    key: str
    bucket: str
    document_id: str

@router.post("/upload:init", response_model=UploadInitResponse)
async def upload_init(body: UploadInitRequest):
    signed = presign_post(org_id=body.org_id, filename=body.filename, content_type=body.content_type)
    return UploadInitResponse(upload_url=signed["url"], fields=signed["fields"], key=signed["key"],
                              bucket=signed["bucket"], document_id=signed["key"])

@router.post("/{document_id:path}/publish")
def publish(document_id: str, background: BackgroundTasks, source_type: str = "OTHER", org_id: str = "demo"):
    STATUS[document_id] = {"state": "queued"}
    background.add_task(process_document, document_id, source_type, org_id)
    return {"status": "queued", "document_id": document_id}

# Synchronous, JSON body (use this for now)
class IngestNowRequest(BaseModel):
    key: str
    source_type: str = "AAOS"
    org_id: str = "demo"

@router.post("/ingest_now")
def ingest_now_json(body: IngestNowRequest):
    STATUS[body.key] = {"state": "processing"}
    process_document(body.key, body.source_type, body.org_id)
    return STATUS[body.key]

@router.get("/{document_id:path}/status")
def status(document_id: str):
    return STATUS.get(document_id, {"state": "unknown"})

@router.get("/debug/statuses")
def all_statuses():
    return STATUS

