# RAG Multimodal Data Analyzer

Production-style веб-сервис для мультимодального RAG: авторизация пользователей, рабочие пространства (`workspace`), загрузка файлов, индексация в векторную БД и чат с ИИ с источниками.

## Ключевые возможности

- Cookie-based авторизация: `login/logout`, роли user/admin, профиль пользователя.
- Работа с `workspace`:
  - создание, приватность, список своих и библиотечных workspace;
  - поиск публичных workspace и добавление в библиотеку;
  - rename/delete workspace (owner-only).
- Чаты:
  - создание, список, удаление, переименование;
  - привязка/отвязка workspace к чату;
  - хранение истории сообщений в `chats.message_history`;
  - загрузка истории по chat_id.
- Мультимодальная загрузка файлов:
  - хранение бинарных файлов в MinIO;
  - сохранение метаданных в MongoDB;
  - текстовая экстракция/предобработка/чанкинг/векторизация в Qdrant.
- Полноценный multimedia-to-text:
  - image -> `langchain_ollama` (`ChatOllama`) для извлечения текста/описания;
  - audio -> `faster-whisper`;
  - video -> `ffmpeg` (extract audio) + `faster-whisper`.
- Ответы ИИ с источниками:
  - `sources` в ответе,
  - `download_url` (presigned MinIO link) для скачивания исходников.
- Режим умного поиска (`smart_search`) в чате:
  - итеративный retrieval по векторному хранилищу;
  - автоматическая генерация уточняющих запросов;
  - ограничение итераций и количества уточнений.

## Технологический стек

### Backend

- `Python`, `FastAPI`, `Uvicorn`
- `MongoDB` (`motor`)
- `PostgreSQL` (`langgraph checkpoint/store`)
- `Qdrant` (vector store)
- `MinIO` (S3-compatible object storage)
- `Apache Tika` (text extraction)
- `LangChain/LangGraph`

### Frontend

- `React + TypeScript + Vite`
- `React Router`
- `TanStack Query`
- `Zustand`
- `CSS Modules`
- `lucide-react`

### Infra / Local services

- `docker compose` в `docker_local/docker-compose.yml`
- сервисы: `tika_service`, `qdrant`, `redis`, `minio`, `ollama`

## Архитектура данных

- `MongoDB`
  - `users` — пользователи и роли
  - `chats` — метаданные чатов, `thread_id`, `workspace_ids`, `message_history`
  - `workspaces` — рабочие пространства
  - `workspace_files` — метаданные загруженных файлов
- `PostgreSQL`
  - кратковременная и долговременная память агента (LangGraph checkpointer/store)
- `Qdrant`
  - коллекции вида `workspace_<workspace_id>`
- `MinIO`
  - исходные файлы, доступ через presigned links

## Структура проекта

```text
app/
  main.py                    # FastAPI entrypoint, routers, CORS, lifespan
  routes/
    auth.py                  # /login /logout /protected
    profile.py               # /profile/*
    admin.py                 # /admin/*
    chat.py                  # /chat/*
    workspaces.py            # /workspaces/*
    files.py                 # /files/*
  schemas.py                 # Pydantic модели API
  serializers.py             # ObjectId/datetime -> JSON-safe

database/
  mongodb/
    async_db.py              # users
    chats_db.py              # chats + history
    workspaces_db.py         # workspaces
    files_db.py              # workspace_files
    main.py                  # singleton instances

ai/
  llm/rag_agent/             # агент, prompts, memory, tools
  vector/                    # embed_model + qdrant vector_store

services/
  storage/minio_service.py   # upload/presigned/delete
  extract/tika_service.py    # text extraction client
  ingest/                    # multimodal pipeline

frontend/
  src/
    app/                     # layout + protected route
    features/                # auth/chat/workspaces/files
    shared/                  # api client, types, ui, store
```

## Основные API

### Auth

- `POST /login`
- `POST /logout`
- `GET /profile/`

### Chat

- `POST /chat/create`
- `GET /chat/list`
- `PATCH /chat/{chat_id}` (rename)
- `DELETE /chat/{chat_id}`
- `POST /chat/{chat_id}/attach_workspaces`
- `POST /chat/{chat_id}/message`
- `GET /chat/{chat_id}/history`

### Workspaces

- `POST /workspaces/`
- `GET /workspaces/my`
- `GET /workspaces/library`
- `POST /workspaces/search_public`
- `POST /workspaces/{workspace_id}/add_to_library`
- `PATCH /workspaces/{workspace_id}/visibility`
- `PATCH /workspaces/{workspace_id}` (rename)
- `DELETE /workspaces/{workspace_id}`

### Files

- `POST /files/upload/{workspace_id}` (multipart/form-data)
- `GET /files/workspace/{workspace_id}`
- `GET /files/{file_id}/download_link`

## Как работает ingestion

1. Пользователь загружает файл в `workspace`.
2. API сохраняет исходный бинарный файл в MinIO и метаданные в MongoDB (`workspace_files`).
3. Pipeline определяет модальность:
   - `text/doc` -> Apache Tika;
   - `image` -> `ChatOllama` (vision);
   - `audio` -> `faster-whisper`;
   - `video` -> `ffmpeg` извлекает аудио, затем `faster-whisper`.
4. Полученный текст очищается (`clean_for_embedding`), чанкуется и индексируется в Qdrant.
5. В payload каждого чанка пишутся `workspace_id`, `file_id`, `object_key`, чтобы потом отдавать источники и ссылки на скачивание.

## Как работает smart search

Режим включается прямо в `POST /chat/{chat_id}/message`:

```json
{
  "message": "вопрос пользователя",
  "smart_search": true,
  "smart_iterations": 3,
  "smart_extra_queries": 2
}
```

Логика:

1. Сначала выполняется обычный retrieval по исходному вопросу.
2. Если сигнал релевантности слабый (мало документов/низкий score), строятся уточняющие запросы.
3. Выполняются дополнительные итерации retrieval (до `smart_iterations`).
4. Результаты объединяются и дедуплицируются по `file_id/object_key/text`.
5. Агент формирует ответ из объединенного контекста.
6. В ответ добавляется `retrieval_trace` (для отладки итераций).

Ограничения на стороне API:
- `smart_iterations`: `1..3`
- `smart_extra_queries`: `0..2`

## Локальный запуск (dev)

### 1) Инфраструктура

```bash
docker compose -f docker_local/docker-compose.yml up -d
```

### 2) Backend

```bash
python -m venv myvenv
source myvenv/bin/activate
pip install -r requirements.txt
python -m app.main
```

Backend: [http://127.0.0.1:8000](http://127.0.0.1:8000)

### 3) Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend: [http://127.0.0.1:5173](http://127.0.0.1:5173)

## Конфигурация (`.env`)

Ключевые группы переменных:

- PostgreSQL: `DATABASE_USER`, `DATABASE_PASSWORD`, `DATABASE_NAME`, `DATABASE_HOST`, `DATABASE_PORT`
- MongoDB: `MONGODB_URL_DEV`, `MONGODB_URL_PROD`
- JWT: `SECRET_KEY`, `ALGORITHM`
- LLM: `OPENAI_API_KEY`, `OPENAI_MODEL`, `LLM_API_URL`, `LLM_API_KEY`
- Embeddings/Qdrant: `DENSE_MODEL_PROVIDER`, `QDRANT_URL`, `SPARSE_MODEL_NAME`, `USE_SPARSE`
- MinIO: `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET_UPLOADS`
- Tika: `TIKA_URL`, `TIKA_TIMEOUT_SEC`
- Ingest: `CHUNK_SIZE`, `CHUNK_OVERLAP`, `UPLOAD_MAX_FILE_MB`
- Ollama: `OLLAMA_BASE_URL`, `OLLAMA_VISION_MODEL`
- ASR/Video: `WHISPER_MODEL_SIZE`, `WHISPER_DEVICE`, `WHISPER_COMPUTE_TYPE`, `WHISPER_BEAM_SIZE`, `FFMPEG_BIN`

## Тестирование

```bash
pytest
```

Рекомендуемое покрытие:
- unit: text preprocess / type detector / api utils
- api: auth/chat/workspaces/files
- integration: upload -> ingest -> qdrant -> chat with sources

## Production-ready рекомендации

### Безопасность

- Никогда не хранить реальные ключи в git-репозитории.
- Включить HTTPS и `secure=True` для cookie.
- Ограничить `allow_origins` в CORS до доменов фронта.
- Добавить rate limiting на login/chat endpoints.
- Добавить audit/logging для действий admin и удаления сущностей.

### Надежность

- Перевести ingest в background jobs (Celery/RQ), не в request-thread.
- Добавить retries/circuit breaker для внешних сервисов (LLM/Tika/MinIO).
- Добавить healthcheck endpoints для Mongo/Postgres/Qdrant/MinIO/Tika.
- Настроить centralized logs + metrics + tracing.

### Производительность

- Кэшировать частые запросы (`/chat/list`, `/workspaces/my`).
- Батчить индексацию и ставить очередь на heavy embeddings.
- Ограничить максимальный размер/типы файлов.

### CI/CD

- CI pipeline: lint + typecheck + tests + build.
- Отдельные окружения: `dev/stage/prod`.
- Миграции/инициализация индексов как отдельный startup job.

## Ограничения текущей версии

- Для `openai` embeddings и части токенизации нужен внешний интернет-доступ.
- Для audio/video ingestion необходим установленный `ffmpeg` и доступный runtime `faster-whisper`.
- `smart_search` увеличивает latency ответа, так как выполняет итеративный retrieval.

## Дополнительная документация

- `docs/workspace_and_ingest.md` — поток данных workspace/ingest.
- `frontend/README.md` — краткий гайд по фронтенду.
