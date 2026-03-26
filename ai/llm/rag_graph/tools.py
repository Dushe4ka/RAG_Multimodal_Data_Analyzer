from __future__ import annotations

import json
from typing import Any, Optional

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


def build_retriever_tool(vector_store: VectorStore, workspace_id: Optional[str] = None):
    """Создает retriever tool для ToolNode."""

    @tool
    def retriever_tool(query: str, limit: int = 5, mode: str = "hybrid") -> str:
        """Ищет релевантные фрагменты в Qdrant (гибридный/semantic поиск)."""
        hits = vector_store.search(
            query=query,
            limit=limit,
            mode="hybrid" if mode not in ("hybrid", "dense") else mode,  # type: ignore[arg-type]
            query_filter=_workspace_filter(workspace_id),
        )
        return json.dumps(hits, ensure_ascii=False)

    return retriever_tool


def parse_hits(raw_tool_content: str) -> list[dict[str, Any]]:
    """Парсит JSON-ответ retriever_tool."""
    try:
        data = json.loads(raw_tool_content)
        return data if isinstance(data, list) else []
    except Exception:
        return []
