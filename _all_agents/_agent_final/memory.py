# memory.py
from dataclasses import dataclass
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore
from langchain.embeddings import init_embeddings
from contextlib import contextmanager
from typing import Callable

from _agent_final.config import Config


@dataclass
class ProductionMemory:
    """Долгоживущие checkpointer и store для production.
    Вызови .close() при завершении работы приложения."""
    checkpointer: PostgresSaver
    store: PostgresStore
    close: Callable[[], None]


def init_production_memory(config: Config) -> ProductionMemory:
    """Создаёт и возвращает долгоживущие checkpointer и store.
    Соединения остаются открытыми до вызова .close().
    Вызывать один раз при старте приложения."""
    checkpointer_cm = PostgresSaver.from_conn_string(config.DATABASE_URL)
    checkpointer = checkpointer_cm.__enter__()
    checkpointer.setup()

    store_cm = PostgresStore.from_conn_string(
        config.DATABASE_URL,
        index={
            "embed": init_embeddings(config.EMBEDDING_MODEL),
            "dims": 1536,  # Для text-embedding-3-small
        },
    )
    store = store_cm.__enter__()
    store.setup()

    def close() -> None:
        store_cm.__exit__(None, None, None)
        checkpointer_cm.__exit__(None, None, None)

    return ProductionMemory(checkpointer=checkpointer, store=store, close=close)


@contextmanager
def get_production_memory(config: Config):
    """Контекстный менеджер для production-памяти.
    Использовать, когда весь цикл (создание агента и вызовы invoke) выполняется внутри одного блока with."""
    checkpointer_cm = PostgresSaver.from_conn_string(config.DATABASE_URL)
    checkpointer = checkpointer_cm.__enter__()
    try:
        checkpointer.setup()
        store_cm = PostgresStore.from_conn_string(
            config.DATABASE_URL,
            index={
                "embed": init_embeddings(config.EMBEDDING_MODEL),
                "dims": 1536,
            },
        )
        store = store_cm.__enter__()
        try:
            store.setup()
            yield checkpointer, store
        finally:
            store_cm.__exit__(None, None, None)
    finally:
        checkpointer_cm.__exit__(None, None, None)
