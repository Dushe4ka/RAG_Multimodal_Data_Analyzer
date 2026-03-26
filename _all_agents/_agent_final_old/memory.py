# memory.py
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore
from langchain.embeddings import init_embeddings
from contextlib import contextmanager

@contextmanager
def get_production_memory(config):
    """Контекстный менеджер для production-памяти"""
    
    # Кратковременная память (checkpoint)
    with PostgresSaver.from_conn_string(config.DATABASE_URL) as checkpointer:
        checkpointer.setup()  # Создает таблицы checkpoint_*
        
        # Долговременная память (store) с семантическим поиском
        with PostgresStore.from_conn_string(config.DATABASE_URL) as store:
            store.setup()  # Создает таблицы store_*
            
            # Включаем embeddings для семантического поиска
            store.index = {
                "embed": init_embeddings(config.EMBEDDING_MODEL),
                "dims": 1536,  # Для text-embedding-3-small
            }
            
            yield checkpointer, store