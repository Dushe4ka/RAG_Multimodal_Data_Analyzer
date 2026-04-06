import pytest

from app.routes import workspaces
from app.schemas import WorkspaceCreate


class DummyWorkspacesDb:
    async def create_workspace(self, owner_user_id: str, name: str, is_private: bool):
        return {
            "workspace_id": "ws-1",
            "owner_user_id": owner_user_id,
            "name": name,
            "is_private": is_private,
        }


@pytest.mark.asyncio
async def test_create_workspace_route(monkeypatch):
    monkeypatch.setattr(workspaces, "workspaces_db", DummyWorkspacesDb())
    payload = WorkspaceCreate(name="Test WS", is_private=False)
    result = await workspaces.create_workspace(payload=payload, user_id="user-1")
    assert result["workspace_id"] == "ws-1"
    assert result["name"] == "Test WS"
