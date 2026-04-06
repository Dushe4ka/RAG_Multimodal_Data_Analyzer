# Workspace and Ingest Flow

## Data flow

1. Пользователь создает workspace (`/workspaces/`), приватный или публичный.
2. Пользователь загружает файл (`/files/upload/{workspace_id}`).
3. Файл сохраняется в MinIO (`object_key`), запись о файле создается в `workspace_files`.
4. Pipeline определяет тип данных:
   - text/doc -> Tika extraction;
   - image -> Ollama vision img2txt;
   - audio -> ASR stub;
   - video -> stub.
5. Текст очищается (`clean_for_embedding`) и индексируется в Qdrant коллекцию `workspace_{workspace_id}`.
6. В чате (`/chat/{chat_id}/message`) при подключенном workspace агент делает retrieval в соответствующей коллекции.
7. API возвращает ответ и `sources` с presigned ссылками MinIO.

## Связность сущностей

- `users.user_id` -> владелец workspace и чатов.
- `workspaces.workspace_id` -> пространство данных и коллекция Qdrant.
- `workspace_files.file_id` + `object_key` -> метаданные файла и ссылка на MinIO объект.
- `chats.chat_id` + `thread_id` -> пользовательский чат и восстановление памяти LangGraph.

## Основные эндпоинты

- `POST /workspaces/`
- `GET /workspaces/my`
- `GET /workspaces/library`
- `POST /workspaces/search_public`
- `POST /workspaces/{workspace_id}/add_to_library`
- `PATCH /workspaces/{workspace_id}/visibility`
- `POST /files/upload/{workspace_id}`
- `GET /files/workspace/{workspace_id}`
- `GET /files/{file_id}/download_link`
- `POST /chat/create`
- `GET /chat/list`
- `DELETE /chat/{chat_id}`
- `POST /chat/{chat_id}/attach_workspaces`
- `POST /chat/{chat_id}/message`
