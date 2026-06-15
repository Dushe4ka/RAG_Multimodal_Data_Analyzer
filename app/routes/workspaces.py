from fastapi import APIRouter, Depends, HTTPException

from app.schemas import (
    PublicWorkspaceSearchRequest,
    WorkspaceCreate,
    WorkspaceRenameRequest,
    WorkspaceVisibilityUpdate,
)
from app.serializers import to_jsonable
from app.utils import get_current_user
from app.workspace_serializers import enrich_workspaces
from database.mongodb.main import db, workspace_files_db, workspaces_db
from services.workspace_cleanup import delete_workspace_data, ensure_workspace_access

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


async def _enrich(workspaces, user_id: str):
    return to_jsonable(await enrich_workspaces(workspaces, users_db=db, current_user_id=user_id))


@router.post("/")
async def create_workspace(payload: WorkspaceCreate, user_id: str = Depends(get_current_user)):
    workspace = await workspaces_db.create_workspace(
        owner_user_id=user_id,
        name=payload.name,
        is_private=payload.is_private,
    )
    enriched = await enrich_workspaces([workspace], users_db=db, current_user_id=user_id)
    return to_jsonable(enriched[0])


@router.get("/my")
async def list_my_workspaces(user_id: str = Depends(get_current_user)):
    return await _enrich(await workspaces_db.list_owned(owner_user_id=user_id), user_id)


@router.get("/library")
async def list_library(user_id: str = Depends(get_current_user)):
    return await _enrich(await workspaces_db.list_library(user_id=user_id), user_id)


@router.post("/search_public")
async def search_public(payload: PublicWorkspaceSearchRequest, user_id: str = Depends(get_current_user)):
    workspaces = await workspaces_db.search_public(query=payload.query, user_id=user_id)
    return await _enrich(workspaces, user_id)


@router.post("/{workspace_id}/add_to_library")
async def add_public_workspace_to_library(workspace_id: str, user_id: str = Depends(get_current_user)):
    updated = await workspaces_db.add_to_library(workspace_id=workspace_id, user_id=user_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Workspace not found or private")
    return {"status": "ok"}


@router.delete("/{workspace_id}/library")
async def remove_workspace_from_library(workspace_id: str, user_id: str = Depends(get_current_user)):
    removed = await workspaces_db.remove_from_library(workspace_id=workspace_id, user_id=user_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Workspace not in your library")
    return {"status": "ok"}


@router.patch("/{workspace_id}/visibility")
async def set_workspace_visibility(
    workspace_id: str,
    payload: WorkspaceVisibilityUpdate,
    user_id: str = Depends(get_current_user),
):
    updated = await workspaces_db.set_visibility(
        workspace_id=workspace_id,
        owner_user_id=user_id,
        is_private=payload.is_private,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {"status": "ok"}


@router.patch("/{workspace_id}")
async def rename_workspace(
    workspace_id: str,
    payload: WorkspaceRenameRequest,
    user_id: str = Depends(get_current_user),
):
    updated = await workspaces_db.rename_workspace(
        workspace_id=workspace_id,
        owner_user_id=user_id,
        name=payload.name,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {"status": "ok"}


@router.get("/{workspace_id}")
async def get_workspace(workspace_id: str, user_id: str = Depends(get_current_user)):
    workspace = await workspaces_db.get_workspace(workspace_id)
    ensure_workspace_access(workspace, user_id, write=False)
    enriched = await enrich_workspaces([workspace], users_db=db, current_user_id=user_id)
    return enriched[0]


@router.delete("/{workspace_id}")
async def delete_workspace(workspace_id: str, user_id: str = Depends(get_current_user)):
    workspace = await workspaces_db.get_workspace(workspace_id)
    if not workspace or workspace.get("owner_user_id") != user_id:
        raise HTTPException(status_code=404, detail="Workspace not found")

    cleanup = await delete_workspace_data(workspace_id=workspace_id, files_db=workspace_files_db)
    deleted = await workspaces_db.delete_workspace(
        workspace_id=workspace_id,
        owner_user_id=user_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {"status": "ok", "cleanup": cleanup}
