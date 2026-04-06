import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.schemas import UploadResponse
from app.serializers import to_jsonable
from app.utils import get_current_user
from database.mongodb.main import workspace_files_db, workspaces_db
from services.ingest.pipeline import IngestPipeline
from services.ingest.type_detector import detect_media_type
from services.storage.minio_service import MinioService

router = APIRouter(prefix="/files", tags=["files"])


@router.post("/upload/{workspace_id}", response_model=UploadResponse)
async def upload_file_to_workspace(
    workspace_id: str,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
):
    workspace = await workspaces_db.get_workspace(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if user_id not in workspace.get("member_user_ids", []):
        raise HTTPException(status_code=403, detail="No access to workspace")

    content = await file.read()
    media_type = detect_media_type(file.content_type or "", file.filename or "")
    object_key = f"{workspace_id}/{uuid.uuid4()}_{file.filename}"

    minio_service = MinioService()
    minio_service.upload_bytes(
        object_key=object_key,
        content=content,
        content_type=file.content_type or "application/octet-stream",
    )

    record = await workspace_files_db.create_file_record(
        workspace_id=workspace_id,
        owner_user_id=user_id,
        filename=file.filename or "uploaded.bin",
        media_type=media_type,
        object_key=object_key,
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(content),
    )

    pipeline = IngestPipeline(collection_name=f"workspace_{workspace_id}")
    try:
        result = await pipeline.process_and_index(
            content=content,
            filename=file.filename or "uploaded.bin",
            content_type=file.content_type or "application/octet-stream",
            workspace_id=workspace_id,
            file_id=record["file_id"],
            object_key=object_key,
        )
        status = "indexed" if result["status"] == "indexed" else "stub"
    except Exception as exc:
        result = {"status": "error", "error": str(exc)}
        status = "error"
    await workspace_files_db.set_extraction_status(record["file_id"], status, metadata=result)
    return UploadResponse(
        file_id=record["file_id"],
        workspace_id=workspace_id,
        filename=record["filename"],
        media_type=record["media_type"],
        extraction_status=status,
        message=result.get("status") if status != "error" else result.get("error"),
    )


@router.get("/workspace/{workspace_id}")
async def list_workspace_files(workspace_id: str, user_id: str = Depends(get_current_user)):
    workspace = await workspaces_db.get_workspace(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if user_id not in workspace.get("member_user_ids", []):
        raise HTTPException(status_code=403, detail="No access to workspace")
    return to_jsonable(await workspace_files_db.list_workspace_files(workspace_id=workspace_id))


@router.get("/{file_id}/download_link")
async def get_download_link(file_id: str, user_id: str = Depends(get_current_user)):
    file_doc = await workspace_files_db.get_file(file_id=file_id)
    if not file_doc:
        raise HTTPException(status_code=404, detail="File not found")
    workspace = await workspaces_db.get_workspace(file_doc["workspace_id"])
    if not workspace or user_id not in workspace.get("member_user_ids", []):
        raise HTTPException(status_code=403, detail="No access to file")

    link = MinioService().presigned_get_url(file_doc["object_key"])
    return {"url": link}
