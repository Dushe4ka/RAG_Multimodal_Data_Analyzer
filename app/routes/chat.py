import uuid

from fastapi import APIRouter, Depends, HTTPException
from langchain_openai import ChatOpenAI

from ai.llm.rag_agent.agent import chat_once, create_rag_agent
from ai.llm.rag_agent.memory import init_agent_memory
from ai.llm.rag_agent.tools import run_smart_search
from ai.vector.embed_model import EmbedModel
from ai.vector.vector_store import VectorStore
from app.schemas import ChatCreateRequest, ChatMessageRequest, ChatRenameRequest
from app.serializers import to_jsonable
from app.utils import get_current_user
from config import get_memory_db_url, settings
from database.mongodb.main import chats_db, workspaces_db
from services.storage.minio_service import MinioService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/create")
async def create_chat(payload: ChatCreateRequest, user_id: str = Depends(get_current_user)):
    chat_id = str(uuid.uuid4())
    chat = await chats_db.create_chat(
        chat_id=chat_id,
        user_id=user_id,
        title=payload.title,
        thread_id=chat_id,
        workspace_ids=payload.workspace_ids,
    )
    return await chats_db.convert_chat_for_api_response(chat)


@router.get("/list")
async def list_chats(user_id: str = Depends(get_current_user)):
    chats = await chats_db.get_all_chats_by_user_id(user_id=user_id)
    return await chats_db.convert_chat_for_api_response(chats)


@router.delete("/{chat_id}")
async def delete_chat(chat_id: str, user_id: str = Depends(get_current_user)):
    chat = await chats_db.get_chat_by_chat_id(chat_id=chat_id)
    if not chat or chat["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Chat not found")
    await chats_db.delete_chat_by_chat_id(chat_id=chat_id)
    return {"status": "deleted"}


@router.patch("/{chat_id}")
async def rename_chat(chat_id: str, payload: ChatRenameRequest, user_id: str = Depends(get_current_user)):
    updated = await chats_db.rename_chat(chat_id=chat_id, user_id=user_id, title=payload.title)
    if not updated:
        raise HTTPException(status_code=404, detail="Chat not found")
    return {"status": "ok"}


@router.get("/{chat_id}/history")
async def get_chat_history(chat_id: str, user_id: str = Depends(get_current_user)):
    chat = await chats_db.get_chat_by_chat_id(chat_id=chat_id)
    if not chat or chat["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Chat not found")
    history = await chats_db.get_message_history(chat_id=chat_id)
    return to_jsonable(history)


@router.post("/{chat_id}/attach_workspaces")
async def attach_workspaces(chat_id: str, payload: dict, user_id: str = Depends(get_current_user)):
    chat = await chats_db.get_chat_by_chat_id(chat_id=chat_id)
    if not chat or chat["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Chat not found")
    workspace_ids = payload.get("workspace_ids", [])
    await chats_db.update_chat_workspaces(chat_id=chat_id, workspace_ids=workspace_ids)
    return {"status": "ok"}


@router.post("/{chat_id}/message")
async def send_message(chat_id: str, payload: ChatMessageRequest, user_id: str = Depends(get_current_user)):
    chat = await chats_db.get_chat_by_chat_id(chat_id=chat_id)
    if not chat or chat["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Chat not found")

    workspace_ids = chat.get("workspace_ids", [])
    answer = ""
    sources = []
    retrieval_trace = []

    if workspace_ids:
        workspace_id = workspace_ids[0]
        workspace = await workspaces_db.get_workspace(workspace_id)
        if workspace and user_id in workspace.get("member_user_ids", []):
            with init_agent_memory(get_memory_db_url()) as memory:
                agent = create_rag_agent(
                    memory=memory,
                    user_id=user_id,
                    workspace_id=workspace_id,
                    collection_name=f"workspace_{workspace_id}",
                    qdrant_url=settings.QDRANT_URL,
                    use_sparse=settings.USE_SPARSE,
                    smart_search=payload.smart_search,
                    smart_iterations=payload.smart_iterations,
                    smart_extra_queries=payload.smart_extra_queries,
                )
                answer = chat_once(
                    agent=agent,
                    message=payload.message,
                    thread_id=chat.get("thread_id", chat_id),
                    user_id=user_id,
                )

            vector_store = VectorStore(
                collection_name=f"workspace_{workspace_id}",
                embed_model=EmbedModel(provider=settings.DENSE_MODEL_PROVIDER),
                qdrant_url=settings.QDRANT_URL,
                use_sparse=settings.USE_SPARSE,
                sparse_model_name=settings.SPARSE_MODEL_NAME,
            )
            if payload.smart_search:
                hits, retrieval_trace = run_smart_search(
                    vector_store=vector_store,
                    query=payload.message,
                    workspace_id=workspace_id,
                    limit=3,
                    mode="hybrid",
                    iterations=payload.smart_iterations,
                    extra_queries=payload.smart_extra_queries,
                )
            else:
                hits = vector_store.search(payload.message, limit=3, mode="hybrid")
            minio_service = MinioService()
            for hit in hits:
                p = hit.get("payload", {})
                source = {
                    "file_id": p.get("file_id"),
                    "workspace_id": p.get("workspace_id"),
                    "score": hit.get("score"),
                    "text": p.get("text", ""),
                    "source": p.get("source"),
                }
                if p.get("object_key"):
                    source["download_url"] = minio_service.presigned_get_url(p["object_key"])
                sources.append(source)
        else:
            raise HTTPException(status_code=403, detail="No access to attached workspace")
    else:
        llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=0.2,
            max_tokens=2048,
        )
        response = llm.invoke(payload.message)
        answer = response.content if isinstance(response.content, str) else str(response.content)

    await chats_db.append_message(chat_id=chat_id, role="user", content=payload.message)
    await chats_db.append_message(chat_id=chat_id, role="assistant", content=answer, sources=sources)
    await chats_db.touch_chat(chat_id=chat_id)
    return {"chat_id": chat_id, "answer": answer, "sources": sources, "retrieval_trace": retrieval_trace}
