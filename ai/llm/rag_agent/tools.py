from __future__ import annotations

import json
from typing import Optional

from langchain_core.tools import tool
from qdrant_client.http import models

from ai.vector.vector_store import VectorStore


def _workspace_filter(workspace_id: Optional[str]) -> Optional[models.Filter]:
    if not workspace_id:
        return None
    return models.Filter(
        must=[
            models.FieldCondition(
                key="workspace_id",
                match=models.MatchValue(value=workspace_id),
            )
        ]
    )


def build_rag_tools(
    *,
    vector_store: VectorStore,
    store: object,
    user_id: str,
    workspace_id: Optional[str],
):
    """Фабрика инструментов: retrieve + long-term memory."""
    memory_namespace = (user_id, "rag_agent_memory")

    @tool
    def retrieve_context(query: str, limit: int = 5, mode: str = "hybrid") -> str:
        """Ищет релевантный контекст в Qdrant (hybrid/dense)."""
        safe_mode = mode if mode in ("hybrid", "dense") else "hybrid"
        hits = vector_store.search(
            query=query,
            limit=limit,
            mode=safe_mode,  # type: ignore[arg-type]
            query_filter=_workspace_filter(workspace_id),
        )
        serialized = []
        for hit in hits:
            payload = hit.get("payload", {})
            serialized.append(
                {
                    "score": hit.get("score"),
                    "source": payload.get("source"),
                    "workspace_id": payload.get("workspace_id"),
                    "file_id": payload.get("file_id"),
                    "object_key": payload.get("object_key"),
                    "content": payload.get("text", ""),
                }
            )
        return json.dumps(serialized, ensure_ascii=False)

    @tool
    def remember_fact(key: str, value: str) -> str:
        """Сохраняет факт в долговременную память пользователя."""
        store.put(memory_namespace, key, {"value": value})
        return f"Сохранено: {key}"

    @tool
    def recall_fact(key: str) -> str:
        """Читает факт из долговременной памяти пользователя."""
        item = store.get(memory_namespace, key)
        if item is None:
            return "Факт не найден."
        val = item.value if hasattr(item, "value") else item
        if isinstance(val, dict):
            return str(val.get("value", ""))
        return str(val)

    return [retrieve_context, remember_fact, recall_fact]
