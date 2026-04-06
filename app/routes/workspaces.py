from fastapi import APIRouter, Depends, HTTPException

from app.schemas import (
    PublicWorkspaceSearchRequest,
    WorkspaceCreate,
    WorkspaceRenameRequest,
    WorkspaceVisibilityUpdate,
)
from app.serializers import to_jsonable
from app.utils import get_current_user
from database.mongodb.main import workspaces_db

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.post("/")
async def create_workspace(payload: WorkspaceCreate, user_id: str = Depends(get_current_user)):
    workspace = await workspaces_db.create_workspace(
        owner_user_id=user_id,
        name=payload.name,
        is_private=payload.is_private,
    )
    return to_jsonable(workspace)


@router.get("/my")
async def list_my_workspaces(user_id: str = Depends(get_current_user)):
    return to_jsonable(await workspaces_db.list_owned(owner_user_id=user_id))


@router.get("/library")
async def list_library(user_id: str = Depends(get_current_user)):
    return to_jsonable(await workspaces_db.list_library(user_id=user_id))


@router.post("/search_public")
async def search_public(payload: PublicWorkspaceSearchRequest, user_id: str = Depends(get_current_user)):
    _ = user_id
    return to_jsonable(await workspaces_db.search_public(query=payload.query))


@router.post("/{workspace_id}/add_to_library")
async def add_public_workspace_to_library(workspace_id: str, user_id: str = Depends(get_current_user)):
    updated = await workspaces_db.add_to_library(workspace_id=workspace_id, user_id=user_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Workspace not found or private")
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


@router.delete("/{workspace_id}")
async def delete_workspace(workspace_id: str, user_id: str = Depends(get_current_user)):
    deleted = await workspaces_db.delete_workspace(
        workspace_id=workspace_id,
        owner_user_id=user_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {"status": "ok"}
