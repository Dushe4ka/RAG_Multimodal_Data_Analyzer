# `ai/llm/rag_agent` — RAG-агент на `create_agent` с памятью

Документация по модулю tool-based RAG-агента, построенного на `langchain.agents.create_agent`.

---

## 1) Назначение

`ai/llm/rag_agent` нужен для быстрого production-подхода:

- агент сам решает, когда вызывать retrieval tool;
- retrieval идет в Qdrant через ваш `VectorStore`;
- есть кратковременная и долговременная память;
- есть консольный чат для тестирования.

---

## 2) Структура файлов

- `ai/llm/rag_agent/agent.py`
  - создание агента (`create_rag_agent`);
  - один вызов чата (`chat_once`);
  - middleware суммаризации (`SummarizationMiddleware`).
- `ai/llm/rag_agent/tools.py`
  - `retrieve_context` — поиск по Qdrant;
  - `remember_fact` — запись фактов в long-term store;
  - `recall_fact` — чтение фактов из long-term store.
- `ai/llm/rag_agent/memory.py`
  - `init_agent_memory` — инициализация `PostgresSaver` + `PostgresStore`.
- `ai/llm/rag_agent/prompts.py`
  - системный промпт и guardrails.

---

## 3) Память в модуле

### Кратковременная память

Реализована через `checkpointer` (`PostgresSaver`) и `thread_id`:

- один чат = один стабильный `thread_id`;
- история этого чата сохраняется между вызовами и рестартами.

### Долговременная память

Реализована через `store` (`PostgresStore`):

- `remember_fact(key, value)` сохраняет факт;
- `recall_fact(key)` возвращает факт;
- namespace привязан к пользователю (`user_id`), чтобы память была общей между чатами пользователя.

---

## 4) Инструменты агента

### `retrieve_context(query, limit=5, mode="hybrid")`

- вызывает `VectorStore.search(...)`;
- поддерживает `hybrid` / `dense`;
- фильтрует документы по `workspace_id`;
- возвращает сериализованные результаты (контент + метаданные).

### `remember_fact(key, value)`

Сохраняет произвольный факт пользователя в Postgres Store.

### `recall_fact(key)`

Читает факт пользователя из Postgres Store.

---

## 5) Быстрый старт (код)

```python
from ai.llm.rag_agent import create_rag_agent, chat_once, init_agent_memory

DATABASE_URL = "postgresql://user:pass@localhost:5432/dbname"

with init_agent_memory(DATABASE_URL) as memory:
    agent = create_rag_agent(
        memory=memory,
        user_id="u1",
        workspace_id="ws1",
        collection_name="rag_agent_demo_docs",
        qdrant_url="http://localhost:6333",
        use_sparse=True,
    )

    print(chat_once(agent, "Привет", thread_id="t1", user_id="u1"))
```

---

## 6) Тестовый консольный чат

Готовый скрипт:

- `tests/embed/ex_5_rag_agent_chat.py`

Что делает:

1. индексирует демонстрационные документы в Qdrant;
2. создает агента с short/long memory;
3. запускает консольный диалог.

Запуск:

```bash
python3 -m tests.embed.ex_5_rag_agent_chat
```

Команды в чате:

- `exit` — выход;
- `reset_thread` — новый thread (проверка short-term memory);
- фразы вида «Запомни ...» / «Что ты помнишь ...» — проверка long-term memory.

---

## 7) Переменные окружения и конфиг

Используются поля из `config.py`:

- для Postgres:
  - `DATABASE_USER`
  - `DATABASE_PASSWORD`
  - `DATABASE_HOST`
  - `DATABASE_PORT`
  - `DATABASE_NAME`
- для Qdrant:
  - `QDRANT_URL`
  - `USE_SPARSE`
  - `SPARSE_MODEL_NAME`
  - `DENSE_MODEL_PROVIDER` (`qwen` или `openai`)
- для LLM:
  - `LLM_API_URL` (OpenAI-compatible endpoint)
  - `LLM_API_KEY`
  - `OPENAI_MODEL`
  - `OPENAI_API_KEY` (fallback)

---

## 8) Частые ошибки и диагностика

### `openai.APIConnectionError` / `Connection refused`

Причина: агент не может достучаться до LLM endpoint.

Проверить:

- запущен ли сервер по `LLM_API_URL`;
- корректный ли путь (`.../v1`);
- доступен ли endpoint из вашей среды.

### Retrieval не находит документы

Проверить:

- документы проиндексированы в нужную коллекцию;
- в payload есть `workspace_id`;
- `workspace_id` в запросе совпадает с payload.

### Нет эффекта от long-term memory

Проверить:

- доступность Postgres;
- одинаковый `user_id` при вызовах;
- агент действительно вызывает `remember_fact`.

---

## 9) Когда выбирать `rag_agent`

Выбирайте `rag_agent`, если нужно:

- быстро получить рабочий agentic-RAG без явного построения графа;
- иметь tool-calling поведение (несколько retrieval вызовов при необходимости);
- подключить short-term + long-term память с минимумом кода.

Если нужен жесткий контроль маршрутизации и сложная логика ветвления, используйте `rag_graph`.

