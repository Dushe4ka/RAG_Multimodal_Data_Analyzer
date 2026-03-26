from __future__ import annotations

from typing import Any, Optional

from ai.vector.embed_model import EmbedModel
from ai.vector.vector_store import VectorStore

from .graph import build_rag_graph


def create_rag_agent(
    *,
    collection_name: str = "rag_docs",
    workspace_id: Optional[str] = None,
    qdrant_url: str = "http://localhost:6333",
    use_sparse: bool = True,
    max_retries: int = 2,
) -> Any:
    """
    Фабрика agentic-RAG графа с Qdrant retriever.
    """
    embed = EmbedModel(provider="openai")
    vector_store = VectorStore(
        collection_name=collection_name,
        embed_model=embed,
        qdrant_url=qdrant_url,
        use_sparse=use_sparse,
    )
    return build_rag_graph(
        vector_store=vector_store,
        workspace_id=workspace_id,
        max_retries=max_retries,
    )


def invoke_rag(
    query: str,
    *,
    workspace_id: Optional[str] = None,
    thread_id: str = "default",
    collection_name: str = "rag_docs",
) -> dict[str, Any]:
    """
    Удобный синхронный вызов графа.
    """
    graph = create_rag_agent(collection_name=collection_name, workspace_id=workspace_id)
    state = {
        "messages": [("user", query)],
        "question": query,
        "documents": [],
        "retrieval_needed": True,
        "generation": "",
        "retries": 0,
        "workspace_id": workspace_id,
        "search_mode": "hybrid",
        "retrieval_limit": 5,
        "raw_hits": [],
        "action": "",
    }
    config = {"configurable": {"thread_id": thread_id}}
    return graph.invoke(state, config=config)
