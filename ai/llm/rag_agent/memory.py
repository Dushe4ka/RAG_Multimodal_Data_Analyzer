from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore


@dataclass(frozen=True)
class AgentMemory:
    """Кратковременная и долговременная память агента."""

    checkpointer: PostgresSaver
    store: PostgresStore


@contextmanager
def init_agent_memory(database_url: str) -> Iterator[AgentMemory]:
    """
    Инициализирует память для LangChain create_agent:
    - checkpointer: short-term memory (по thread_id)
    - store: long-term memory (факты между сессиями)
    """
    with PostgresSaver.from_conn_string(database_url) as checkpointer:
        checkpointer.setup()
        store_ctx = PostgresStore.from_conn_string(database_url)
        store = store_ctx.__enter__()
        try:
            store.setup()
            yield AgentMemory(checkpointer=checkpointer, store=store)
        finally:
            store_ctx.__exit__(None, None, None)
