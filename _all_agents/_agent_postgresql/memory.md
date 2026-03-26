Кратко: в memory.py нужно завести фабрики store, checkpointer и backend по доке DeepAgents, с продакшен-вариантом на PostgreSQL.

---

## 1. Роль memory.py

- Краткосрочная память — файлы без префикса /memories/ → StateBackend(runtime): живут только в состоянии графа в рамках одного thread_id, после завершения диалога пропадают.
- Долговременная память — файлы с префиксом /memories/ → StoreBackend(runtime): хранятся в LangGraph Store (у вас — PostgreSQL), общие для всех потоков и переживают перезапуск.

Маршрутизация задаётся через CompositeBackend: по умолчанию — StateBackend, для путей /memories/ — StoreBackend.

---

## 2. Зависимости для продакшена (PostgreSQL)

- Чекпоинты (история диалога, состояние графа):  
  langgraph-checkpoint-postgres → PostgresSaver / AsyncPostgresSaver.
- Store (долговременные файлы `/memories/*`):  
  В доке DeepAgents указан langgraph.store.postgres.PostgresStore. Сейчас он может быть в отдельном пакете (например langgraph-store-postgres`) или в составе `langgraph-checkpoint-postgres. Если при импорте будет ошибка, в коде ниже предусмотрен fallback на InMemoryStore.

Установка:


pip install langgraph-checkpoint-postgres
# при необходимости (если PostgresStore не из checkpoint-postgres):
# pip install langgraph-store-postgres


В .env добавьте (если ещё нет):


DATABASE_URL=postgresql://user:password@localhost:5432/dbname


---

## 3. Содержимое memory.py

Ниже — полный вариант модуля: фабрики для продакшена (PostgreSQL) и fallback для разработки.

```python
"""
Краткосрочная и долговременная память для DeepAgents.

- Краткосрочная: StateBackend — файлы без префикса /memories/ (в состоянии графа, только текущий thread).
- Долговременная: StoreBackend — файлы /memories/* в Store (PostgreSQL в продакшене), между потоками и перезапусками.
"""

import os
from typing import Any

from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

# ---------------------------------------------------------------------------
# Store (долговременная память: /memories/*)
# ---------------------------------------------------------------------------

def get_store():
    """
    Store для долговременной памяти (StoreBackend).
    Продакшен: PostgreSQL. Разработка: InMemoryStore.
    """
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if database_url and database_url.startswith(("postgresql", "postgres/")):
        try:
            from langgraph.store.postgres import PostgresStore
            store_ctx = PostgresStore.from_conn_string(database_url)
            store = store_ctx.__enter__()
            store.setup()
            return store
        except ImportError:
            try:
                from langgraph_checkpoint_postgres.store import PostgresStore
            except ImportError:
                pass
            # Если отдельного пакета нет — используем InMemoryStore
            return InMemoryStore()
    return InMemoryStore()


# ---------------------------------------------------------------------------
# Checkpointer (история сообщений и состояние графа по thread_id)
# ---------------------------------------------------------------------------

def get_checkpointer():
    """
    Чекпоинтер для сохранения состояния диалога.
    Продакшен: PostgresSaver. Разработка: MemorySaver.
    """
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if database_url and database_url.startswith(("postgresql", "postgres/")):
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
            # Важно: использовать from_conn_string и вызвать .setup() при первом запуске
            checkpointer_ctx = PostgresSaver.from_conn_string(database_url)
            checkpointer = checkpointer_ctx.__enter__()
            checkpointer.setup()
            return checkpointer
        except Exception:
            return MemorySaver()
    return MemorySaver()
[16.03.2026 20:56] Павел Голубинец: # ---------------------------------------------------------------------------
# Backend (гибрид краткосрочная + долговременная файловая система)
# ---------------------------------------------------------------------------

def make_memory_backend(runtime: Any):
    """
    Фабрика backend для create_deep_agent.
    - Пути без префикса (/notes.txt, /workspace/draft.md) → StateBackend (краткосрочная).
    - Пути /memories/* → StoreBackend (долговременная, в store).
    """
    return CompositeBackend(
        default=StateBackend(runtime),
        routes={"/memories/": StoreBackend(runtime)},
    )


Важно по PostgreSQL:

- **PostgresSaver**: при ручном создании соединения нужны `autocommit=True` и `row_factory=dict_row` (см. доки langgraph-checkpoint-postgres). При использовании `PostgresSaver.from_conn_string()` это обычно уже учтено внутри.
- **PostgresStore**: если модуль `langgraph.store.postgres` недоступен, замените блок `get_store()` на использование только `InMemoryStore()` до установки нужного пакета.

---

## 4. Использование в `main.py`

Создание агента с памятью и чекпоинтером:

```python
from _deep_agent.memory import get_store, get_checkpointer, make_memory_backend

# ...

store = get_store()
checkpointer = get_checkpointer()

agent = create_deep_agent(
    model=llm,
    system_prompt=SYSTEM_PROMPT,
    tools=tools,
    store=store,
    checkpointer=checkpointer,
    backend=make_memory_backend,
)


Чтобы агент реально пользовался долговременной памятью, в системный промпт имеет смысл добавить, например:


SYSTEM_PROMPT = """...
У тебя есть долговременная память в каталоге /memories/:
- /memories/preferences.txt — предпочтения пользователя
- /memories/context/ — контекст о пользователе и проектах
При указании пользователя сохраняй важное в /memories/. В начале диалога при необходимости читай эти файлы.
"""


---

## 5. Схема работы

- Краткосрочная: всё, что агент пишет в /draft.txt, /notes.txt и т.п., хранится в состоянии графа (checkpointer) и привязано к thread_id; после окончания сессии это можно не переносить.
- Долговременная: всё в /memories/* (например /memories/preferences.txt`) уходит в Store (PostgreSQL), доступно из любого `thread_id и после рестарта приложения.

Итог: в memory.py вы добавляете долговременную и кратковременную память по доке DeepAgents; для продакшена — PostgreSQL через get_store() и get_checkpointer(), в main.py передаёте store, checkpointer и backend=make_memory_backend. Если нужно, могу в Agent mode сам подставить этот код в memory.py и обновить main.py.