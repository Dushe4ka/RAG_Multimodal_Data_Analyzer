from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException
from qdrant_client import QdrantClient

from config import settings
from database.mongodb.files_db import AsyncWorkspaceFilesDatabase
from services.storage.minio_service import MinioService


def ensure_workspace_access(
    workspace: Optional[dict[str, Any]],
    user_id: str,
    *,
    write: bool = False,
) -> None:
    """
    write=False — просмотр/скачивание: владелец, подписчик или любой пользователь для публичного WS.
    write=True — загрузка/изменение: только member_user_ids.
    """
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if user_id in workspace.get("member_user_ids", []):
        return
    if not write and not workspace.get("is_private", True):
        return
    raise HTTPException(status_code=403, detail="No access to workspace")


async def delete_workspace_data(
    *,
    workspace_id: str,
    files_db: AsyncWorkspaceFilesDatabase,
) -> dict[str, Any]:
    """Удаляет файлы из MinIO, метаданные из MongoDB и коллекцию Qdrant."""
    await files_db.ensure_connection()
    files = await files_db.list_workspace_files(workspace_id)
    minio = MinioService()
    minio_deleted = 0
    for file_doc in files:
        object_key = file_doc.get("object_key")
        if object_key:
            try:
                minio.delete(object_key)
                minio_deleted += 1
            except Exception:
                pass

    mongo_deleted = await files_db.delete_by_workspace(workspace_id)

    qdrant_deleted = False
    collection_name = f"workspace_{workspace_id}"
    try:
        client = QdrantClient(url=settings.QDRANT_URL)
        collections = {c.name for c in client.get_collections().collections}
        if collection_name in collections:
            client.delete_collection(collection_name)
            qdrant_deleted = True
    except Exception:
        pass

    return {
        "files_in_minio": minio_deleted,
        "files_in_mongo": mongo_deleted,
        "qdrant_collection_removed": qdrant_deleted,
    }
