from __future__ import annotations

from contextvars import ContextVar

# Активный контекст диалога, который используется tool-обёртками для изоляции задач.
active_user_id: ContextVar[str | None] = ContextVar("cron_active_user_id", default=None)
active_thread_id: ContextVar[str | None] = ContextVar("cron_active_thread_id", default=None)

# Флаг: агент сейчас выполняет cron callback (в этом режиме cron tools запрещены).
cron_execution: ContextVar[bool] = ContextVar("cron_execution", default=False)

