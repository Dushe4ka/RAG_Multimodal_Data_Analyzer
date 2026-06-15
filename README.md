# RAG Multimodal Data Analyzer

Production-style веб-сервис для мультимодального RAG: авторизация пользователей, рабочие пространства (`workspace`), загрузка файлов, индексация в векторную БД и чат с ИИ с источниками.

## Ключевые возможности

- Cookie-based авторизация: `login/logout`, роли user/admin, профиль пользователя.
- Личный кабинет пользователя (`/profile`):
  - карточный UI с аватаром, бейджами роли и датой регистрации;
  - редактирование имени и фамилии;
  - смена пароля через проверку старого пароля и подтверждение нового.
- Админ-панель (`/admin`) для управления пользователями:
  - поиск по логину/ФИО (в блоке списка пользователей);
  - создание пользователя (включая роль и admin-флаг);
  - редактирование имени/фамилии и сброс пароля;
  - удаление пользователя.
- Работа с `workspace`:
  - вкладки **Мои** / **Добавленные** / **Каталог** публичных пространств;
  - публичные workspace остаются в каталоге после добавления (бейдж «Уже добавлено», удаление по hover);
  - создание, приватность, rename/delete (owner-only);
  - каскадное удаление: MongoDB + MinIO + Qdrant collection;
  - обогащение карточек данными автора (`owner_display_name`, `is_owner`, `is_subscribed`).
- Чаты:
  - боковая панель: история чатов, inline-переименование, удаление;
  - **название чата** формируется из первого сообщения пользователя и сохраняется в MongoDB;
  - привязка workspace к чату через picker с разделами «Мои» / «Добавленные»;
  - композер: умный поиск, выбор workspace, индикатор набора (анимация точек);
  - хранение истории в `chats.message_history`, загрузка по `chat_id`.
- Мультимодальная загрузка файлов:
  - хранение бинарных файлов в MinIO;
  - метаданные в MongoDB, скачивание по presigned URL;
  - повторная обработка файлов со статусом `error` (`POST /files/{file_id}/reprocess`);
  - публичные workspace: чтение файлов для всех, запись — только для участников.
- Полноценный multimedia-to-text:
  - image -> `ollama` или `openai` vision (`IMAGE_VISION_PROVIDER`);
  - audio -> `faster-whisper`;
  - video -> `ffmpeg` + `faster-whisper`.
- Ответы ИИ с источниками:
  - Markdown-рендеринг ответов (`react-markdown`, `remark-gfm`);
  - дедупликация источников по `file_id` (один файл — одна запись);
  - карточки источников с типом медиа и превью текста;
  - `download_url` (presigned MinIO) для скачивания исходников.
- RAG-агент с tool-based retrieval:
  - агент **обязан** вызывать `retrieve_context` / `smart_retrieve_context` перед ответом по документам;
  - изображения/аудио/видео в Qdrant хранятся как текстовые описания и транскрипции — ответ строится по ним;
  - режим **умного поиска** (`smart_search`): итеративный retrieval с уточняющими запросами.

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
- `react-markdown` + `remark-gfm`

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
  ingest/                    # multimodal pipeline + reprocess
  sources.py                 # dedupe_sources для API/UI
  chat_title.py              # название чата из первого сообщения
  workspace_cleanup.py       # каскадное удаление workspace

frontend/
  src/
    app/                     # layout + protected route + sidebar navigation
    features/
      auth/                  # login/session
      chat/                  # chat UI + smart search toggles
      workspaces/            # workspace management + library
      files/                 # workspace files list/upload
      profile/               # profile page (edit name/surname/password)
      admin/                 # admin users page
    shared/                  # api client, types, ui, store
```

## Основные API

### Auth

- `POST /login`
- `POST /logout`
- `GET /profile/`

### Profile

- `GET /profile/`
- `POST /profile/edit_name_surname?name=...&surname=...`
- `POST /profile/edit_password?old_pwd=...&new_pwd=...&confirm_pwd=...`

### Admin

- `GET /admin/get_all_users`
- `POST /admin/create_user` (JSON body)
- `POST /admin/update_user_name_surname?login=...&name=...&surname=...`
- `POST /admin/update_user_password?login=...&new_pwd=...`
- `DELETE /admin/delete_user` (JSON body: `{ "login": "..." }`)

### Chat

- `POST /chat/create`
- `GET /chat/list`
- `PATCH /chat/{chat_id}` (rename)
- `DELETE /chat/{chat_id}`
- `POST /chat/{chat_id}/attach_workspaces`
- `POST /chat/{chat_id}/message` — ответ включает `title` (актуальное название чата)
- `GET /chat/{chat_id}/history`

### Workspaces

- `POST /workspaces/`
- `GET /workspaces/my`
- `GET /workspaces/library`
- `POST /workspaces/search_public`
- `POST /workspaces/{workspace_id}/add_to_library`
- `DELETE /workspaces/{workspace_id}/library` — убрать из добавленных
- `GET /workspaces/{workspace_id}` — детали workspace с автором
- `PATCH /workspaces/{workspace_id}/visibility`
- `PATCH /workspaces/{workspace_id}` (rename)
- `DELETE /workspaces/{workspace_id}`

### Files

- `POST /files/upload/{workspace_id}` (multipart/form-data)
- `GET /files/workspace/{workspace_id}`
- `GET /files/{file_id}/download_link`
- `POST /files/{file_id}/reprocess` — повтор extract/index для файла со статусом `error`

## Как работает RAG в чате

1. К чату привязан `workspace_id` — коллекция Qdrant `workspace_<id>`.
2. Агент LangGraph получает system prompt с правилом: **сначала** вызвать tool поиска в Qdrant.
3. Обычный режим: tool `retrieve_context` — один гибридный поиск (dense + sparse).
4. Умный режим: tool `smart_retrieve_context` — итеративный поиск (см. ниже).
5. В tool возвращаются фрагменты с полем `content` (текст, описание фото, транскрипция).
6. Агент формирует ответ в Markdown; API дополнительно возвращает `sources` для UI.

При первом сообщении в чате заголовок автоматически устанавливается из текста запроса (до 80 символов) и сохраняется в MongoDB.

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

Режим включается кнопкой **«Умный поиск»** в чате или в теле запроса:

```json
{
  "message": "вопрос пользователя",
  "smart_search": true,
  "smart_iterations": 3,
  "smart_extra_queries": 2
}
```

Логика (`run_smart_search` / tool `smart_retrieve_context`):

1. Выполняется retrieval по исходному вопросу в Qdrant (hybrid).
2. Если сигнал слабый (мало документов или `top_score < 0.35`), генерируются уточняющие запросы:
   - исходный вопрос + ключевые слова из найденных фрагментов;
   - `«<вопрос> подробности»`;
   - `«уточнение: <вопрос>»`.
3. До `smart_iterations` итераций (макс. 3), до `smart_extra_queries` подзапросов за итерацию (макс. 2).
4. Результаты объединяются, дедуплицируются, сортируются по score.
5. Агент использует объединённый контекст для ответа; в UI — блок **«Источники»** (отдельный post-retrieval для отображения).

Ограничения API: `smart_iterations` 1..3, `smart_extra_queries` 0..2.

**Когда включать:** сложные или размытые вопросы, длинные документы/медиа.  
**Когда выключать:** простые точечные запросы (быстрее и дешевле).

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
- Agent LLM provider: `AGENT_LLM_PROVIDER`, `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL`, `OLLAMA_CHAT_MODEL`
- Embeddings/Qdrant: `DENSE_MODEL_PROVIDER`, `QDRANT_URL`, `SPARSE_MODEL_NAME`, `USE_SPARSE`
- MinIO: `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET_UPLOADS`
- Tika: `TIKA_URL`, `TIKA_TIMEOUT_SEC`
- Ingest: `CHUNK_SIZE`, `CHUNK_OVERLAP`, `UPLOAD_MAX_FILE_MB`
- Image vision: `IMAGE_VISION_PROVIDER` (`ollama` | `openai`), `OPENAI_VISION_MODEL`
- Ollama: `OLLAMA_BASE_URL`, `OLLAMA_VISION_MODEL`
- ASR/Video: `WHISPER_MODEL_SIZE`, `WHISPER_DEVICE`, `WHISPER_COMPUTE_TYPE`, `WHISPER_BEAM_SIZE`, `FFMPEG_BIN`

## Выбор LLM для агента

Агент выбирает чат-модель через `AGENT_LLM_PROVIDER`:

- `openai` -> `langchain_openai.ChatOpenAI`
- `deepseek` -> `langchain_deepseek.ChatDeepSeek`
- `ollama` -> `langchain_ollama.ChatOllama`

### Пример `.env` для OpenAI / OpenAI-compatible

```env
AGENT_LLM_PROVIDER=openai
OPENAI_MODEL=gpt-4o-mini
OPENAI_API_KEY=...
LLM_API_URL=https://api.openai.com/v1
```

### Пример `.env` для DeepSeek

```env
AGENT_LLM_PROVIDER=deepseek
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_API_KEY=...
```

### Пример `.env` для Ollama

```env
AGENT_LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_CHAT_MODEL=qwen2.5:7b
```

Примечание:
- если `AGENT_LLM_PROVIDER` не указан или указан некорректно, используется `openai`;
- `DENSE_MODEL_PROVIDER` управляет эмбеддингами/векторизацией и не переключает чат-модель агента.

### Пример `.env` для OpenAI vision (демо обработки фото)

```env
IMAGE_VISION_PROVIDER=openai
OPENAI_VISION_MODEL=gpt-4o-mini
OPENAI_API_KEY=...
LLM_API_URL=https://api.openai.com/v1
```

### Аудио и видео (faster-whisper)

Пакет `faster-whisper` уже в `requirements.txt`. Отдельно ставить веса не нужно — при первой транскрипции модель скачивается с Hugging Face по имени `WHISPER_MODEL_SIZE`.

```env
# tiny | base | small | medium | large-v3  (для демо на CPU обычно хватает small)
WHISPER_MODEL_SIZE=small
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
WHISPER_BEAM_SIZE=5
FFMPEG_BIN=ffmpeg
```

Для видео дополнительно нужен `ffmpeg` в PATH:

```bash
# macOS
brew install ffmpeg
```

Проверка после установки зависимостей:

```bash
python -c "from faster_whisper import WhisperModel; m=WhisperModel('tiny', device='cpu', compute_type='int8'); print('ok')"
```

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
- `smart_search` увеличивает latency ответа из-за нескольких запросов к Qdrant.
- Качество ответов по фото/видео зависит от tool-calling агента и полноты текстовой экстракции при загрузке.

## Дополнительная документация

- `docs/workspace_and_ingest.md` — поток данных workspace/ingest.
- `frontend/README.md` — краткий гайд по фронтенду.
