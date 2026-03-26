from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from typing import AsyncIterator, Iterator

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore


@dataclass(frozen=True)
class ProductionMemory:
    checkpointer: PostgresSaver
    store: PostgresStore


@contextmanager
def init_production_memory(database_url: str) -> Iterator[ProductionMemory]:
    """Инициализация продакшен-памяти (синхронная, для CLI).

    - checkpointer (short-term): PostgresSaver
    - store (long-term): PostgresStore
    """
    with PostgresSaver.from_conn_string(database_url) as checkpointer:
        checkpointer.setup()

        store_ctx = PostgresStore.from_conn_string(database_url)
        store = store_ctx.__enter__()
        try:
            store.setup()
            yield ProductionMemory(checkpointer=checkpointer, store=store)
        finally:
            store_ctx.__exit__(None, None, None)


@dataclass(frozen=True)
class AsyncProductionMemory:
    """Асинхронная память для API (ainvoke + MCP)."""

    checkpointer: object  # AsyncPostgresSaver
    store: object  # AsyncPostgresStore


@asynccontextmanager
async def init_async_production_memory(database_url: str) -> AsyncIterator[AsyncProductionMemory]:
    """Инициализация продакшен-памяти (асинхронная, для FastAPI + ainvoke + MCP)."""
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from langgraph.store.postgres import AsyncPostgresStore

    async with AsyncPostgresSaver.from_conn_string(database_url) as checkpointer:
        await checkpointer.setup()
        async with AsyncPostgresStore.from_conn_string(database_url) as store:
            await store.setup()
            yield AsyncProductionMemory(checkpointer=checkpointer, store=store)
