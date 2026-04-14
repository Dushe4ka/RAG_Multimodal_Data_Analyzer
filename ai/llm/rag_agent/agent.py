from __future__ import annotations

from typing import Any, Literal, Optional

from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain_deepseek import ChatDeepSeek
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from config import settings
from ai.vector.embed_model import EmbedModel
from ai.vector.vector_store import VectorStore

from .memory import AgentMemory
from .prompts import SYSTEM_PROMPT
from .tools import build_rag_tools


def _build_llm() -> Any:
    """
    Инициализация LLM по провайдеру из AGENT_LLM_PROVIDER:
    - openai
    - deepseek
    - ollama
    """
    provider = (settings.AGENT_LLM_PROVIDER or "openai").strip().lower()

    if provider == "deepseek":
        return ChatDeepSeek(
            model=settings.DEEPSEEK_MODEL,
            api_key=settings.DEEPSEEK_API_KEY,
            # temperature=0.2,
            # max_tokens=4096,
            max_retries=3,
        )

    if provider == "ollama":
        return ChatOllama(
            model=settings.OLLAMA_CHAT_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0.2,
            num_predict=4096,
        )

    # По умолчанию — OpenAI/OpenAI-compatible endpoint.
    return ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.LLM_API_URL,
        # temperature=0.2,
        # max_tokens=4096,
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
    smart_search: bool = False,
    smart_iterations: int = 3,
    smart_extra_queries: int = 2,
) -> Any:
    """Создает RAG-агента LangChain с tool-based retrieval + памятью."""
    prov = settings.DENSE_MODEL_PROVIDER
    if prov == "bge_m3":
        embed = EmbedModel(
            provider="bge_m3",
            model_name=settings.BGE_M3_MODEL,
            use_fp16=settings.BGE_M3_USE_FP16,
        )
        sparse_backend: Literal["fastembed", "bgem3"] = "bgem3" if use_sparse else "fastembed"
        use_colbert = settings.VECTOR_USE_COLBERT
    elif prov == "openai":
        embed = EmbedModel(provider="openai")
        sparse_backend = "fastembed"
        use_colbert = False
    elif prov == "qwen":
        embed = EmbedModel(provider="qwen")
        sparse_backend = "fastembed"
        use_colbert = False
    else:
        embed = EmbedModel(provider="qwen")
        sparse_backend = "fastembed"
        use_colbert = False

    vector_store = VectorStore(
        collection_name=collection_name,
        embed_model=embed,
        qdrant_url=qdrant_url,
        use_sparse=use_sparse,
        sparse_model_name=settings.SPARSE_MODEL_NAME,
        sparse_backend=sparse_backend,
        use_colbert=use_colbert,
    )

    llm = _build_llm()
    tools = build_rag_tools(
        vector_store=vector_store,
        store=memory.store,
        user_id=user_id,
        workspace_id=workspace_id,
        smart_search=smart_search,
        smart_iterations=smart_iterations,
        smart_extra_queries=smart_extra_queries,
    )

    middleware = [
        SummarizationMiddleware(
            model=llm,
            trigger=("tokens", 12000),
            keep=("messages", 40),
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


def chat_once_structured(
    agent: Any,
    message: str,
    *,
    thread_id: str,
    user_id: str,
    sources: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Возвращает структурированный ответ для API чата."""
    answer = chat_once(
        agent=agent,
        message=message,
        thread_id=thread_id,
        user_id=user_id,
    )
    return {
        "answer": answer,
        "sources": sources or [],
    }
