
Кратко: что уже есть и как добавить эндпоинты и коллекцию чатов.

---

## Что уже есть

1. **`main.py`** — агент на `create_agent` с `MongoDBSaver` (checkpoints) и `MongoDBStore` (долгая память). В конфиге задаётся `thread_id` и `user_id`.
2. **`memory_mongo.py`** — чекпоинты в БД `chat_history`, коллекции `checkpoints` и `checkpoint_writes`; store — коллекция `long_term_memory`.
3. **`_docs/checkpoint_store_llm.md`** — описание: один чат = один `thread_id`, история диалога в checkpoint, общие данные пользователя в store.
4. **FastAPI** в `app/main.py` с роутерами auth, admin, profile; БД пользователей — `Diplom.users` (Motor).

Идея из доки: **один чат = один `thread_id`**. Для «списка чатов» и «продолжить с той же точки» нужна отдельная коллекция **метаданных чатов** и эндпоинты, которые с ней работают и вызывают агента с нужным `thread_id`.

---

## 1. Коллекция «чаты» (метаданные)

Сообщения уже хранятся в чекпоинтере по `thread_id`. Отдельная коллекция нужна только для:

- списка чатов пользователя;
- отображения названия/превью и дат.

**Коллекция:** в той же БД, что и пользователи (например `Diplom`), или в `chat_history`. Пример документа:

```python
# Коллекция: chats (в Diplom или chat_history)
{
    "chat_id": "uuid",           # уникальный ID чата = часть thread_id
    "user_id": "user_uuid",      # владелец (из users)
    "title": "Новый чат",        # опционально: первая фраза или сгенерированное название
    "created_at": "datetime",
    "updated_at": "datetime"
}
```

Связь с агентом:

- **`thread_id`** = `str(chat_id)` или `f"{user_id}:{chat_id}"` — один и тот же для всех запросов в этот чат.
- При создании чата: создаёте документ в `chats` и возвращаете `chat_id`. Дальше все запросы в этот чат идут с `config["configurable"]["thread_id"] = thread_id`, `user_id` — из авторизации.

Так пользователи смогут видеть список чатов и заходить в любой, продолжая общение с той же точки (история подтягивается из checkpoint по `thread_id`).

---

## 2. Эндпоинты чата

Имеет смысл завести отдельный роутер, например `app/routes/chat.py`, и подключить его в `app/main.py`.

### 2.1 Создание чата

- **POST** `/chats` (или `/users/me/chats`)  
  - Из токена/сессии берёте `user_id`.  
  - Генерируете `chat_id` (uuid).  
  - Вставляете в коллекцию `chats`: `chat_id`, `user_id`, `title="Новый чат"`, `created_at`, `updated_at`.  
  - Ответ: `{"chat_id": "...", "title": "...", "created_at": "..."}`.

### 2.2 Список чатов пользователя

- **GET** `/chats` (или `/users/me/chats`)  
  - По `user_id` из авторизации делаете `find` по `user_id`, сортировка по `updated_at` (или `created_at`) desc.  
  - Ответ: список `{ "chat_id", "title", "created_at", "updated_at" }`.

### 2.3 История сообщений чата (для входа в чат и продолжения)

- **GET** `/chats/{chat_id}/messages`  
  - Проверка: чат из коллекции `chats` принадлежит текущему `user_id`.  
  - `thread_id = f"{user_id}:{chat_id}"` (или как вы договорились).  
  - Вызвать у графа **`agent.get_state(config)`** с `config = {"configurable": {"thread_id": thread_id, "user_id": user_id}}`.  
  - В состоянии графа (часто ключ `"messages"`) лежат сообщения; отдать их клиенту в нужном формате (например список `{ "role", "content" }`).  
  - Если состояния ещё нет (чат только создан), вернуть пустой список.

Так пользователь «заходит в чат» и видит старую переписку, затем может отправить новое сообщение.

### 2.4 Отправка сообщения (продолжение диалога)

- **POST** `/chats/{chat_id}/messages`  
  - Тело: `{"content": "текст сообщения"}` (или массив сообщений, если нужно).  
  - Проверка: чат принадлежит текущему `user_id`.  
  - Тот же `thread_id` (и `user_id` в `configurable`).  
  - Вызов:  
    - `agent.invoke({"messages": [HumanMessage(content=...)])}, config)`  
    - или потоковый вариант через `agent.astream_events` / `astream`, если нужен стриминг.  
  - Ответ: последнее сообщение ассистента (и при желании обновление `updated_at` и `title` в коллекции `chats` — например по первому сообщению пользователя или по первому ответу ИИ).

Опционально: **PATCH** `/chats/{chat_id}` для смены `title` или **DELETE** `/chats/{chat_id}` (удалить документ из `chats`; чекпоинты можно оставить или чистить отдельно).

---

## 3. Связка с вашим агентом

В `main.py` у вас:

```33:38:ai/llm/llm_chat/main.py
config: RunnableConfig = {
    "configurable": {
        "thread_id": "5",
        "user_id": "228",
    }
}
```

В API вместо жёстких значений:

- **thread_id** = `str(chat_id)` или `f"{user_id}:{chat_id}"` для выбранного чата.
- **user_id** = идентификатор залогиненного пользователя (из JWT/сессии).

Агент один (тот же `create_agent` с теми же tools/middleware/checkpointer/store); для каждого запроса вы просто подставляете разный `config`. История и состояние диалога хранятся в MongoDBSaver по `thread_id`, долгосрочная память по пользователю — в store по `user_id`.

---

## 4. Где что хранить

| Что | Где |
|-----|-----|
| Список чатов пользователя, title, даты | Новая коллекция **chats** (в `Diplom` или `chat_history`) |
| История сообщений и состояние диалога | Уже есть — **checkpointer** (MongoDBSaver) по `thread_id` |
| Данные о пользователе между чатами | Уже есть — **Store** (long_term_memory) по `user_id` |

---

## 5. Порядок реализации

1. **Модель/слой для чатов**  
   - Подключение к MongoDB (тот же `AsyncIOMotorClient` или общий клиент), коллекция `chats`.  
   - Функции: `create_chat(user_id, title=...)`, `get_user_chats(user_id)`, `get_chat(chat_id, user_id)`, `update_chat(chat_id, user_id, updates)` (например `title`, `updated_at`).

2. **Роутер чатов**  
   - Зависимость «текущий user_id» из auth (как в `profile`).  
   - Эндпоинты: POST/GET `/chats`, GET/POST `/chats/{chat_id}/messages`.  
   - В хендлерах — вызовы слоя чатов и вызовы агента с `config["configurable"] = {"thread_id": ..., "user_id": ...}`.

3. **Получение истории**  
   - Импорт агента из `ai.llm.llm_chat.main` (или вынос создания агента в отдельный модуль).  
   - В GET `/chats/{chat_id}/messages`: `state = agent.get_state(config)`, из `state.values.get("messages", [])` сформировать ответ.

4. **Отправка сообщения**  
   - В POST `/chats/{chat_id}/messages`: формировать `HumanMessage`, вызывать `agent.invoke(..., config)`, обновлять `updated_at` (и при желании `title`) в коллекции `chats`.

5. **Подключение роутера** в `app/main.py`:  
   `app.include_router(chat.router, prefix="/api")` (или без префикса, как у вас принято).

Так вы получите эндпоинты чата и отдельную коллекцию чатов, а продолжение общения «с той же точки» обеспечивается за счёт одного и того же `thread_id` для данного `chat_id` и хранения состояния в чекпоинтере. Если нужно, могу в режиме агента набросать конкретные сигнатуры и пример кода для `app/routes/chat.py` и слоя работы с коллекцией `chats`.