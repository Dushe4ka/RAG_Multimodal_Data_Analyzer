import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.schemas import UploadResponse
from app.serializers import to_jsonable
from app.utils import get_current_user
from database.mongodb.main import workspace_files_db, workspaces_db
from services.ingest.pipeline import IngestPipeline
from services.ingest.reprocess import reprocess_workspace_file, resolve_reprocess_stage, stage_label
from services.ingest.type_detector import detect_media_type
from services.storage.minio_service import MinioService
from services.workspace_cleanup import ensure_workspace_access

router = APIRouter(prefix="/files", tags=["files"])


@router.post("/upload/{workspace_id}", response_model=UploadResponse)
async def upload_file_to_workspace(
    workspace_id: str,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
):
    workspace = await workspaces_db.get_workspace(workspace_id)
    ensure_workspace_access(workspace, user_id, write=True)

    content = await file.read()
    media_type = detect_media_type(file.content_type or "", file.filename or "")
    object_key = f"{workspace_id}/{uuid.uuid4()}_{file.filename}"

    minio_service = MinioService()
    try:
        minio_service.upload_bytes(
            object_key=object_key,
            content=content,
            content_type=file.content_type or "application/octet-stream",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Хранилище файлов (MinIO) недоступно: {exc}",
        ) from exc

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
    result = await pipeline.process_and_index(
        content=content,
        filename=file.filename or "uploaded.bin",
        content_type=file.content_type or "application/octet-stream",
        workspace_id=workspace_id,
        file_id=record["file_id"],
        object_key=object_key,
    )
    if result.get("status") == "indexed":
        status = "indexed"
    elif result.get("status") == "error":
        status = "error"
    else:
        status = "stub"
    await workspace_files_db.set_extraction_status(record["file_id"], status, metadata=result)
    return UploadResponse(
        file_id=record["file_id"],
        workspace_id=workspace_id,
        filename=record["filename"],
        media_type=record["media_type"],
        extraction_status=status,
        failed_stage=result.get("failed_stage"),
        message=result.get("status") if status != "error" else result.get("error"),
    )


@router.post("/{file_id}/reprocess", response_model=UploadResponse)
async def reprocess_file(file_id: str, user_id: str = Depends(get_current_user)):
    file_doc = await workspace_files_db.get_file(file_id=file_id)
    if not file_doc:
        raise HTTPException(status_code=404, detail="File not found")

    workspace = await workspaces_db.get_workspace(file_doc["workspace_id"])
    ensure_workspace_access(workspace, user_id, write=True)

    reprocess_stage = resolve_reprocess_stage(file_doc.get("metadata"))
    await workspace_files_db.set_extraction_status(file_id, "pending", metadata={"reprocess_stage": reprocess_stage})

    status, result, stage = await reprocess_workspace_file(file_doc=file_doc)
    await workspace_files_db.set_extraction_status(file_id, status, metadata=result)

    return UploadResponse(
        file_id=file_id,
        workspace_id=file_doc["workspace_id"],
        filename=file_doc["filename"],
        media_type=file_doc.get("media_type", "text"),
        extraction_status=status,
        failed_stage=result.get("failed_stage"),
        reprocess_stage=stage,
        message=(
            f"Повтор: {stage_label(stage)}"
            if status == "indexed"
            else result.get("error") if status == "error" else result.get("status")
        ),
    )


@router.get("/workspace/{workspace_id}")
async def list_workspace_files(workspace_id: str, user_id: str = Depends(get_current_user)):
    workspace = await workspaces_db.get_workspace(workspace_id)
    ensure_workspace_access(workspace, user_id, write=False)
    return to_jsonable(await workspace_files_db.list_workspace_files(workspace_id=workspace_id))


@router.get("/{file_id}/download_link")
async def get_download_link(file_id: str, user_id: str = Depends(get_current_user)):
    file_doc = await workspace_files_db.get_file(file_id=file_id)
    if not file_doc:
        raise HTTPException(status_code=404, detail="File not found")
    workspace = await workspaces_db.get_workspace(file_doc["workspace_id"])
    ensure_workspace_access(workspace, user_id, write=False)

    link = MinioService().presigned_get_url(file_doc["object_key"])
    return {"url": link}
