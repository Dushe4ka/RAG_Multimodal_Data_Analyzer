# `ai/llm/rag_graph` — Agentic RAG на LangGraph

Документация по модулю графового RAG, который использует ваш `VectorStore` (`ai/vector/vector_store.py`) для поиска в Qdrant.

---

## 1) Назначение

Модуль `ai/llm/rag_graph` реализует управляемый RAG-цикл в стиле best practices:

- `generate_query_or_respond` — LLM решает, нужен ли retrieval;
- `retrieve` — вызов tool-узла с поиском в Qdrant;
- `grade_documents` — оценка релевантности результатов;
- `rewrite_question` — переформулировка запроса при плохом retrieval;
- `generate_answer` — финальный ответ по контексту.

Преимущества:

- предсказуемый контроль маршрутизации (в отличие от полностью свободного цикла);
- `max_retries` для ограничения rewrite-итераций;
- фильтрация по `workspace_id` для изоляции рабочих пространств.

---

## 2) Структура файлов

- `ai/llm/rag_graph/state.py` — `RAGState` (состояние графа).
- `ai/llm/rag_graph/prompts.py` — системные промпты.
- `ai/llm/rag_graph/tools.py` — retriever-tool поверх `VectorStore`.
- `ai/llm/rag_graph/nodes.py` — узлы и роутинг (`decide_after_grading`).
- `ai/llm/rag_graph/graph.py` — сборка и компиляция `StateGraph`.
- `ai/llm/rag_graph/main.py` — удобные фабрики `create_rag_agent`, `invoke_rag`.

---

## 3) Состояние графа

`RAGState` включает:

- `messages` — история сообщений графа;
- `question` — текущий вопрос;
- `documents` — извлеченные документы;
- `raw_hits` — сырые результаты поиска;
- `retries` — счетчик rewrite попыток;
- `action` — маршрут после grading (`generate` / `rewrite`);
- `workspace_id` — идентификатор рабочего пространства;
- `generation` — финальный ответ.

---

## 4) Как подключается поиск Qdrant

Поиск делается через существующий `VectorStore.search(...)`:

- режим: `hybrid` или `dense`;
- фильтр: `query_filter` по `workspace_id` (если передан);
- результат: JSON-хиты с `payload`, `score`, `id`.

Это позволяет использовать уже реализованный гибридный dense+sparse поиск с RRF.

---

## 5) Быстрый старт (код)

```python
from ai.llm.rag_graph.main import invoke_rag

result = invoke_rag(
    "Как выкатить сервис в прод?",
    workspace_id="demo_workspace_1",
    thread_id="thread-1",
    collection_name="rag_docs_graph_demo",
)

print(result["messages"][-1].content)
```

---

## 6) Тестовый скрипт

Готовый пример:

- `tests/embed/ex_4_rag_graph.py`

Что делает скрипт:

1. индексирует тестовые документы в коллекцию Qdrant;
2. добавляет `workspace_id` в payload;
3. запускает несколько вопросов;
4. дает интерактивный чат в консоли.

Запуск:

```bash
python3 -m tests.embed.ex_4_rag_graph
```

---

## 7) Переменные окружения

Используются значения из `config.py`:

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `QDRANT_URL`

Если используете локальный OpenAI-compatible endpoint, убедитесь, что URL доступен и корректен (обычно с суффиксом `/v1`).

---

## 8) Частые ошибки

### `Connection refused` / `APIConnectionError`

Причина: недоступен endpoint LLM.

Проверка:

- поднят ли сервис по `LLM_API_URL`/`OPENAI` endpoint;
- корректен ли `base_url` (`.../v1`);
- доступен ли хост из текущего окружения.

### Пустые или нерелевантные ответы

Проверить:

- документы реально проиндексированы;
- в payload есть нужный `workspace_id`;
- совпадает ли `workspace_id` в запросе и в данных.

---

## 9) Когда выбирать `rag_graph`

Берите `rag_graph`, если нужна:

- явная графовая маршрутизация;
- расширяемые ноды (фильтрация, rerank, проверка фактов);
- строгий контроль поведения RAG-пайплайна.

