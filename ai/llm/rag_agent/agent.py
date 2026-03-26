from __future__ import annotations

from typing import Any, Optional

from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from config import settings
from ai.vector.embed_model import EmbedModel
from ai.vector.vector_store import VectorStore

from .memory import AgentMemory
from .prompts import SYSTEM_PROMPT
from .tools import build_rag_tools


def _build_llm() -> ChatOpenAI:
    """Единая инициализация LLM через OpenAI-совместимый endpoint проекта."""
    return ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_API_KEY,
        # base_url=settings.LLM_API_URL,
        temperature=0.2,
        max_tokens=4096,
        max_retries=3,
    )


def create_rag_agent(
    *,
    memory: AgentMemory,
    user_id: str,
    workspace_id: Optional[str],
    collection_name: str,
    qdrant_url: str,
    use_sparse: bool = True,
) -> Any:
    """Создает RAG-агента LangChain с tool-based retrieval + памятью."""
    embed_provider = settings.DENSE_MODEL_PROVIDER if settings.DENSE_MODEL_PROVIDER in ("qwen", "openai") else "qwen"
    embed = EmbedModel(provider=embed_provider)  # type: ignore[arg-type]
    vector_store = VectorStore(
        collection_name=collection_name,
        embed_model=embed,
        qdrant_url=qdrant_url,
        use_sparse=use_sparse,
        sparse_model_name=settings.SPARSE_MODEL_NAME,
    )

    llm = _build_llm()
    tools = build_rag_tools(
        vector_store=vector_store,
        store=memory.store,
        user_id=user_id,
        workspace_id=workspace_id,
    )

    middleware = [
        SummarizationMiddleware(
            model=llm,
            trigger=("tokens", 6000),
            keep=("messages", 20),
        )
    ]

    return create_agent(
        model=llm,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        middleware=middleware,
        checkpointer=memory.checkpointer,
        store=memory.store,
    )


def chat_once(
    agent: Any,
    message: str,
    *,
    thread_id: str,
    user_id: str,
) -> str:
    """Один синхронный вызов агента."""
    config = {
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_ns": user_id,
            "user_id": user_id,
        }
    }
    result = agent.invoke(
        {"messages": [HumanMessage(content=message.strip())]},
        config=config,
        context={"user_id": user_id},
    )
    messages = result.get("messages", [])
    if not messages:
        return "Пустой ответ от агента."
    content = getattr(messages[-1], "content", None)
    return content if isinstance(content, str) else str(messages[-1])
