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


def run_smart_search(
    *,
    vector_store: VectorStore,
    query: str,
    workspace_id: Optional[str],
    limit: int = 5,
    mode: str = "hybrid",
    iterations: int = 3,
    extra_queries: int = 2,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Итеративный retrieval с уточняющими запросами."""
    safe_mode = mode if mode in ("hybrid", "dense") else "hybrid"
    max_iterations = min(max(iterations, 1), 3)
    max_extra_queries = min(max(extra_queries, 0), 2)
    queue = [query.strip()]
    seen_queries = set()
    all_hits: list[dict[str, Any]] = []
    trace: list[dict[str, Any]] = []

    for i in range(max_iterations):
        next_queue: list[str] = []
        for q in queue[: max_extra_queries + 1]:
            qn = q.strip()
            if not qn or qn in seen_queries:
                continue
            seen_queries.add(qn)
            hits = vector_store.search(
                query=qn,
                limit=limit,
                mode=safe_mode,  # type: ignore[arg-type]
                query_filter=_workspace_filter(workspace_id),
            )
            all_hits.extend(hits)
            top_score = hits[0].get("score", 0.0) if hits else 0.0
            trace.append({"iteration": i + 1, "query": qn, "hits": len(hits), "top_score": top_score})

            # Если сигнал релевантности слабый — генерируем уточняющие подзапросы.
            if (len(hits) < max(2, limit // 2) or top_score < 0.35) and max_extra_queries > 0:
                payload_texts = []
                for hit in hits[:2]:
                    payload = hit.get("payload", {})
                    text = str(payload.get("text", "")).strip()
                    if text:
                        payload_texts.append(" ".join(text.split()[:10]))
                for text in payload_texts:
                    next_queue.append(f"{query} {text}")
                next_queue.append(f"{query} подробности")
                next_queue.append(f"уточнение: {query}")
        queue = next_queue[: max_extra_queries + 1]
        if not queue:
            break

    dedup: dict[str, dict[str, Any]] = {}
    for hit in all_hits:
        payload = hit.get("payload", {})
        key = f"{payload.get('file_id')}|{payload.get('object_key')}|{payload.get('text', '')[:120]}"
        prev = dedup.get(key)
        if prev is None or (hit.get("score") or 0.0) > (prev.get("score") or 0.0):
            dedup[key] = hit
    sorted_hits = sorted(dedup.values(), key=lambda x: x.get("score") or 0.0, reverse=True)[: limit * 2]
    return sorted_hits, trace


def build_rag_tools(
    *,
    vector_store: VectorStore,
    store: object,
    user_id: str,
    workspace_id: Optional[str],
    smart_search: bool = False,
    smart_iterations: int = 3,
    smart_extra_queries: int = 2,
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
    def smart_retrieve_context(query: str, limit: int = 5, mode: str = "hybrid") -> str:
        """Итеративный retrieval с уточняющими запросами для сложных случаев."""
        hits, trace = run_smart_search(
            vector_store=vector_store,
            query=query,
            workspace_id=workspace_id,
            limit=limit,
            mode=mode,
            iterations=smart_iterations,
            extra_queries=smart_extra_queries,
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
        return json.dumps({"hits": serialized, "trace": trace}, ensure_ascii=False)

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

    if smart_search:
        return [smart_retrieve_context, remember_fact, recall_fact]
    return [retrieve_context, remember_fact, recall_fact]
