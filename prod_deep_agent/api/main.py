"""FastAPI приложение для чата с агентом (память + MCP)."""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

# Импорты из app (при запуске из корня: PYTHONPATH=. uvicorn prod_deep_agent.api.main:app)
try:
    from prod_deep_agent.app.agent_factory import create_agent_with_mcp_async
    from prod_deep_agent.app.memory import init_async_production_memory
    from prod_deep_agent.app.settings import load_settings
except ImportError:
    from app.agent_factory import create_agent_with_mcp_async
    from app.memory import init_async_production_memory
    from app.settings import load_settings


WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def _get_config(
    thread_id: str,
    checkpoint_id: str | None = None,
    user_id: str | None = None,
) -> dict:
    """Конфиг для агента: thread_id + checkpoint_ns по user_id, чтобы у каждого юзера свои потоки (у обоих может быть «поток 1»)."""
    uid = (user_id or "").strip() or ""
    config = {
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_ns": uid,  # изоляция чекпоинтов по пользователю: (thread_id, checkpoint_ns)
        }
    }
    if checkpoint_id:
        config["configurable"]["checkpoint_id"] = checkpoint_id
    if uid:
        config["configurable"]["user_id"] = uid
    return config


def _memory_user_id(request: Request, from_query_or_body: str | None) -> str:
    """user_id для доступа к памяти: если задан заголовок X-User-Id (например из сессии/авторизации), используем только его — иначе query/body."""
    header = (request.headers.get("X-User-Id") or "").strip()
    if header:
        return header
    return (from_query_or_body or "").strip() or "anonymous"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    async with init_async_production_memory(settings.database_url) as memory:
        agent = await create_agent_with_mcp_async(settings, memory)
        app.state.agent = agent
        app.state.memory = memory
        app.state.settings = settings
        yield


app = FastAPI(
    title="Prod Deep Agent API",
    description="Чат с агентом (кратко- и долговременная память, MCP)",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Pydantic models ---
class ChatRequest(BaseModel):
    thread_id: str
    message: str
    user_id: str | None = None
    from_checkpoint: str | None = None


class ChatResponse(BaseModel):
    reply: str
    thread_id: str


class RollbackRequest(BaseModel):
    checkpoint_id: str


class MemoryWriteRequest(BaseModel):
    path: str = "/memories/preferences.txt"
    content: str
    user_id: str | None = None  # долговременная память привязана к user_id, не к thread_id


# --- Routes ---
@app.post("/api/chat", response_model=ChatResponse)
async def api_chat(req: ChatRequest):
    """Отправить сообщение агенту и получить ответ. Чекпоинты — по thread_id, долговременная память (Store) — по user_id."""
    agent = app.state.agent
    config = _get_config(req.thread_id, checkpoint_id=req.from_checkpoint, user_id=req.user_id)
    user_id = (req.user_id or "").strip() or "anonymous"
    result = await agent.ainvoke(
        {"messages": [HumanMessage(content=req.message.strip())]},
        config=config,
        context={"user_id": user_id},
    )
    msgs = result.get("messages", [])
    if not msgs:
        raise HTTPException(status_code=502, detail="Пустой ответ агента")
    last = msgs[-1]
    content = getattr(last, "content", None) or str(last)
    return ChatResponse(reply=content if isinstance(content, str) else str(content), thread_id=req.thread_id)


@app.get("/api/threads")
async def api_threads():
    """Список диалогов: подсказка создать новый (thread_id генерируется на клиенте)."""
    return {"threads": [], "hint": "Используйте «Новый диалог» или введите свой thread_id"}


@app.get("/api/threads/new")
async def api_thread_new():
    """Сгенерировать новый thread_id для диалога."""
    return {"thread_id": str(uuid.uuid4())}


@app.get("/api/threads/{thread_id}/history")
async def api_history(request: Request, thread_id: str, limit: int = 20, user_id: str | None = None):
    """История чекпоинтов для отката. user_id (или X-User-Id) задаёт владельца потока — у каждого юзера свой набор потоков."""
    agent = app.state.agent
    config = _get_config(thread_id, user_id=_memory_user_id(request, user_id))
    snapshots = []
    async for s in agent.aget_state_history(config):
        snapshots.append(s)
        if len(snapshots) >= limit:
            break
    return {
        "thread_id": thread_id,
        "checkpoints": [
            {
                "checkpoint_id": s.config.get("configurable", {}).get("checkpoint_id", ""),
                "step": s.metadata.get("step"),
                "created_at": str(getattr(s, "created_at", "")),
            }
            for s in snapshots
        ],
    }


@app.post("/api/threads/{thread_id}/rollback")
async def api_rollback(thread_id: str, body: RollbackRequest):
    """Откат: следующий запрос в /api/chat с from_checkpoint=body.checkpoint_id продолжит с этого состояния."""
    return {
        "ok": True,
        "thread_id": thread_id,
        "checkpoint_id": body.checkpoint_id,
        "message": "При следующем сообщении передайте from_checkpoint в теле запроса /api/chat",
    }


@app.get("/api/memory")
async def api_memory_ls(request: Request, user_id: str | None = None):
    """Список файлов в долговременной памяти только текущего пользователя. При заголовке X-User-Id используется он (изоляция по сессии/авторизации)."""
    store = app.state.memory.store
    namespace = (_memory_user_id(request, user_id), "filesystem")
    try:
        items = await store.asearch(namespace, limit=100)
    except TypeError:
        items = await store.asearch(namespace, query="", limit=100)
    return {
        "items": [
            {
                "key": getattr(it, "id", getattr(it, "key", str(it))),
                "preview": str(getattr(it, "value", it))[:120],
            }
            for it in items
        ],
    }


@app.get("/api/memory/read")
async def api_memory_read(request: Request, path: str = "/memories/preferences.txt", user_id: str | None = None):
    """Прочитать файл из долговременной памяти только текущего пользователя. При X-User-Id — только его данные."""
    store = app.state.memory.store
    if not path.startswith("/memories/"):
        path = "/memories/" + path.lstrip("/")
    namespace = (_memory_user_id(request, user_id), "filesystem")
    key = path.replace("/memories/", "/").strip("/") or "."
    item = await store.aget(namespace, key)
    if item is None:
        raise HTTPException(status_code=404, detail="Файл не найден")
    val = item.value if hasattr(item, "value") else item
    if isinstance(val, dict) and "content" in val:
        return {"path": path, "content": "\n".join(val["content"])}
    return {"path": path, "content": str(val)}


@app.post("/api/memory/write")
async def api_memory_write(request: Request, body: MemoryWriteRequest):
    """Записать файл в долговременную память только для текущего пользователя. При X-User-Id запись только в его namespace."""
    from deepagents.backends.utils import create_file_data
    store = app.state.memory.store
    path = body.path if body.path.startswith("/memories/") else "/memories/" + body.path.lstrip("/")
    namespace = (_memory_user_id(request, body.user_id), "filesystem")
    key = path.replace("/memories/", "/").strip("/") or "."
    data = create_file_data(body.content)
    await store.aput(namespace, key, data)
    return {"ok": True, "path": path}


# --- Web UI ---
if WEB_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    @app.get("/")
    async def serve_index():
        index = WEB_DIR / "index.html"
        if index.exists():
            return FileResponse(index)
        return {"message": "Prod Deep Agent API", "docs": "/docs"}

    @app.get("/index.html")
    async def serve_index_html():
        return FileResponse(WEB_DIR / "index.html")
else:
    @app.get("/")
    async def root():
        return {"message": "Prod Deep Agent API", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
