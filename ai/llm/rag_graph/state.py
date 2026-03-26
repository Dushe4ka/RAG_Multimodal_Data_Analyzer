from __future__ import annotations

from typing import Any, Optional

from langchain_core.documents import Document
from langgraph.graph import MessagesState


class RAGState(MessagesState):
    """Состояние agentic-RAG графа."""

    question: str
    documents: list[Document]
    retrieval_needed: bool
    generation: str
    retries: int
    workspace_id: Optional[str]
    search_mode: str
    retrieval_limit: int
    raw_hits: list[dict[str, Any]]
    action: str
