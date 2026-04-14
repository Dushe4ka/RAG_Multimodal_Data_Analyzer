from typing import Optional

from pydantic import BaseModel, Field

class SUserAuth(BaseModel):
    login: str
    password: str


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    is_private: bool = True


class WorkspaceVisibilityUpdate(BaseModel):
    is_private: bool


class WorkspaceRenameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class WorkspaceAttachRequest(BaseModel):
    workspace_ids: list[str] = Field(default_factory=list)


class ChatCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    workspace_ids: list[str] = Field(default_factory=list)


class ChatMessageRequest(BaseModel):
    message: str = Field(min_length=1)
    smart_search: bool = False
    smart_iterations: int = Field(default=3, ge=1, le=3)
    smart_extra_queries: int = Field(default=2, ge=0, le=2)


class ChatRenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class ChatMessageResponse(BaseModel):
    chat_id: str
    answer: str
    sources: list[dict] = Field(default_factory=list)


class PublicWorkspaceSearchRequest(BaseModel):
    query: str = ""


class UploadResponse(BaseModel):
    file_id: str
    workspace_id: str
    filename: str
    media_type: str
    extraction_status: str
    message: Optional[str] = None