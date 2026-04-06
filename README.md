# RAG Multimodal Data Analyzer

Веб-сервис с авторизацией, workspace-моделью, мультимодальной загрузкой файлов и чатом с RAG.

## Что реализовано

- JWT авторизация через cookie (`/login`, `/logout`, `/protected`).
- Админ и профиль API.
- Workspace API:
  - создание, список, видимость, публичный поиск, добавление в библиотеку.
- Files API:
  - загрузка в MinIO, метаданные в MongoDB, индексация в Qdrant.
- Multimodal ingest:
  - text/doc: через Tika -> clean -> chunk -> embed -> Qdrant,
  - image: Ollama vision -> text pipeline,
  - audio: ASR-заглушка,
  - video: заглушка в pipeline.
- Chat API:
  - create/list/delete чатов,
  - attach workspace к чату,
  - сообщение в чат (LLM-only или RAG),
  - источники (`sources`) с `download_url`.
- React фронтенд (`frontend/`) для login/home/workspace/chat.

## Архитектура хранилищ

- `MongoDB`: users/chats/workspaces/workspace_files.
- `PostgreSQL`: кратковременная и долговременная память агента (`LangGraph`).
- `Qdrant`: векторная база для RAG по workspace-коллекциям.
- `MinIO`: объектное хранилище исходных файлов.

## Быстрый запуск

1. Поднять инфраструктуру:
   - `docker compose -f docker_local/docker-compose.yml up -d`
2. Установить python-зависимости:
   - `pip install -r requirements.txt`
3. Запустить API:
   - `python -m app.main`
4. Запустить фронтенд:
   - `cd frontend && npm install && npm run dev`

## Тесты

- `pytest`

## Важные ограничения

- Видео пока в статусе заглушки (`stub`/`501` логика на уровне pipeline API-ответа).
- ASR для аудио пока заглушка (точка расширения под локальный Whisper).
- Для продакшена обязательно вынести секреты из `.env`, включить HTTPS и `secure=True` у cookie.
