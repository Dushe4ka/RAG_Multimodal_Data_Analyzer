## Cron в `prod_deep_agent` (APScheduler + Postgres)

Ниже описание того, **как работает cron-менеджер**, **какие tool’ы доступны агенту**, **как задачи сохраняются в БД** и **как срабатывания доставляются в консоль**.

---

## 1) Архитектура (в двух словах)

Cron в твоём `prod_deep_agent` состоит из 4 частей:

- `CronManager` на `APScheduler` — отвечает за “когда выполнить”
- `PostgresCronStore` — отвечает за “что именно хранить и как фиксировать статус/аудит”
- `cron tools` — вызываются LLM для `add/list/remove`
- `delivery` в консоль — по срабатыванию cron задача вызывает агента и печатает результат

Ключевые файлы:
- `[prod_deep_agent/app/cron/store.py]` — Postgres store + схема `cron_tasks`
- `[prod_deep_agent/app/cron/manager.py]` — `CronManager` + APScheduler callbacks
- `[prod_deep_agent/app/cron/tools.py]` — инструменты `cron_add/cron_list/cron_remove`
- `[prod_deep_agent/app/cron/context.py]` — `ContextVar` для `user_id/thread_id` + запрет tools в cron execution
- `[prod_deep_agent/app/agent_factory.py]` — прокидывает tool’ы агенту + добавляет инструкции в system prompt
- `[prod_deep_agent/app/console_app.py]` — связывает cron с консольным чатом

---

## 2) Схема БД (Postgres)

Таблица создаётся/инициализируется в `PostgresCronStore.ensure_schema()` в:
`[prod_deep_agent/app/cron/store.py]`.

```sql
CREATE TABLE IF NOT EXISTS cron_tasks (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,

  user_id TEXT NOT NULL,
  thread_id TEXT NOT NULL,

  message TEXT NOT NULL,
  deliver BOOLEAN NOT NULL DEFAULT TRUE,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  delete_after_run BOOLEAN NOT NULL DEFAULT FALSE,

  schedule_kind TEXT NOT NULL CHECK (schedule_kind IN ('at','every','cron')),
  at_time TIMESTAMPTZ,
  every_seconds INTEGER,
  cron_expr TEXT,
  tz TEXT,

  last_status TEXT,
  last_error TEXT,
  last_run_at TIMESTAMPTZ,
  last_run_bucket TEXT,

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Индексы:
- `cron_tasks (user_id, thread_id, enabled)`
- `cron_tasks (enabled)`

Как хранятся расписания:
- `schedule_kind='at'` → `at_time`
- `schedule_kind='every'` → `every_seconds`
- `schedule_kind='cron'` → `cron_expr`, `tz` (IANA timezone)

Аудит выполнения:
- `last_status`, `last_error`
- `last_run_at`
- `last_run_bucket` (см. idempotency ниже)

---

## 3) Tool’ы для агента (что LLM вызывает)

Инструменты создаются в:
`[prod_deep_agent/app/cron/tools.py]` через `make_cron_tools(cron_manager)`.

LLM получает доступ к **callable tool’ам** (в терминах deepagents), которые выглядят концептуально так:

### 3.1 `cron_add(...)`
Создаёт/обновляет задачу в БД.

Параметры (в коде):
- `message: str` — текст-инструкция, что сделать/что сформировать в напоминании
- ровно **одно** из:
  - `every_seconds: int` (интервал)
  - `cron_expr: str` + `tz: str` (cron-план + timezone)
  - `at_iso: str` (одноразовое напоминание)
- `delete_after_run: bool` — для one-shot сценария

Сначала tool читает `user_id/thread_id` из контекста (см. `ContextVar`), затем вызывает:
- `CronManager.upsert_task(...)`
- внутри этого — `PostgresCronStore.upsert_task(...)` + `APScheduler` job (через reschedule)

### 3.2 `cron_list()`
Возвращает список активных cron задач пользователя/диалога (`user_id + thread_id`).

### 3.3 `cron_remove(job_id)`
Удаляет задачу из БД и убирает job из APScheduler по `task.id`.

---

## 4) ContextVar и “нельзя планировать внутри cron execution”

Файл: `[prod_deep_agent/app/cron/context.py]`

Там есть:
- `active_user_id: ContextVar[str|None]`
- `active_thread_id: ContextVar[str|None]`
- `cron_execution: ContextVar[bool]`

Логика такая:
- Пока пользователь пишет в чат (обычный режим), `run_chat_loop()` задаёт `active_user_id/thread_id` и `cron_execution=False`.
- Когда APScheduler срабатывает и cron callback вызывает агента, `CronManager._run_task_entry()` ставит:
  - `active_user_id = task.user_id`
  - `active_thread_id = task.thread_id`
  - `cron_execution=True`
- В `cron tools` есть `_require_context()` — при `cron_execution=True` tool возвращает ошибку:
  - “cron tools disabled during cron execution”

Это защищает от рекурсивного поведения (“агент в ответе cron пытается снова создавать cron-задачи”).

---

## 5) CronManager: “по времени запускается и вызывает агента”

Файл: `[prod_deep_agent/app/cron/manager.py]`

### 5.1 Start
`CronManager.start()`:
- создаёт схему в Postgres (`ensure_schema`)
- грузит все `enabled` задачи из БД (`load_enabled_tasks`)
- регистрирует каждую задачу в `APScheduler`:
  - `id=<task.id>` (важно для remove/replace)
  - триггер строится из `schedule_kind`

### 5.2 Срабатывание (callback)
Когда наступает время:
1) `CronManager` грузит задачу из БД
2) делает **idempotency claim**:
   - `PostgresCronStore.claim_run(task_id, bucket)`
   - если `last_run_bucket == bucket`, выполнение пропускается (защита от дублей/misfire)
3) ставит `ContextVar` для cron execution
4) вызывает callback `on_execute(task)` (у тебя он создаётся в `console_app.py`)
5) если callback дал текст и `deliver=True` → кладёт событие в `asyncio.Queue`
6) пишет статус в БД (`mark_ok` / `mark_error`)
7) если one-shot (`delete_after_run` или `schedule_kind='at'`) → выключает/удаляет и убирает job из APScheduler

---

## 6) Как агент формирует сообщение и “отправляет пользователю” (консоль)

Файл: `[prod_deep_agent/app/console_app.py]`

### 6.1 Где создаётся `on_execute`
Внутри `run_console_app()` задаётся:

- `cron_queue: asyncio.Queue[CronDeliveryEvent]`
- `on_execute(task) -> str|None`:
  - вызывает `agent_obj.ainvoke(...)` с инструкцией вида:
    - `[Cron Execution] ... Instruction: {task.message} ...`
  - использует config с `thread_id = f"cron:{task.id}"` и `user_id=task.user_id`
  - возвращает текст последнего сообщения агента

То есть cron job **вызвал агента**, и агент **сгенерировал текст напоминания**, который дальше нужно “доставить”.

### 6.2 Delivery в консоль
`CronManager` кладёт `CronDeliveryEvent` в `cron_queue`.

`run_chat_loop()` должен перед вводом пользователя печатать очередь.

В твоём коде это сделано через параметр `cron_queue` в `run_chat_loop(...)`, но важно: сейчас вызовы `run_chat_loop(...)` из меню выглядят так, что `cron_queue` может не передаваться (поэтому печать может не происходить, даже если cron сработал и событие добавилось в очередь).

---

## 7) Инструкция LLM: где сказано “когда вызывать cron tools”

Файл: `[prod_deep_agent/app/agent_factory.py]`

В `_SYSTEM_PROMPT` добавлен блок:
- использовать `cron_add/cron_list/cron_remove` для напоминаний/периодических задач
- формат расписаний: `every_seconds / cron_expr+tz / at_iso`
- при `[Cron Execution]` tool’ы не вызывать

И фабрика передаёт tool’ы в deep agent:
- `create_agent_with_mcp_async(... extra_tools=...)` → `create_deep_agent(tools=extra_tools)`

---

## 8) Как это будет выглядеть для запроса “напомни через 30 секунд выключить чайник”

1) Пользователь пишет текст в чате консоли
2) LLM вызывает `cron_add(...)`
3) задача сохраняется в `cron_tasks` в Postgres (`schedule_kind='at'` или период по твоему промпту/пониманию модели)
4) `APScheduler` ждёт
5) в момент срабатывания вызывает `on_execute(task)`:
   - агент формирует текст напоминания
6) текст попадает в `cron_queue` и печатается при следующем цикле консольного ввода (если delivery печать включена корректно)

---

Если хочешь, я в следующем сообщении набросаю **короткий MD “для README”** (ещё более краткий), и отдельно отмечу **где именно в `console_app.py` лучше гарантировать прокидывание `cron_queue`**, чтобы уведомления гарантированно печатались сразу после срабатывания.