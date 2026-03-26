from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

import psycopg
from psycopg.rows import dict_row

ScheduleKind = Literal["at", "every", "cron"]


@dataclass(frozen=True)
class CronSchedule:
    kind: ScheduleKind
    # "at"
    at_time: datetime | None = None
    # "every"
    every_seconds: int | None = None
    # "cron"
    cron_expr: str | None = None
    tz: str | None = None  # IANA timezone


@dataclass(frozen=True)
class CronTask:
    id: str
    name: str

    user_id: str
    thread_id: str

    # "what to do"
    message: str
    deliver: bool
    enabled: bool
    delete_after_run: bool

    schedule: CronSchedule

    # runtime audit
    last_status: str | None = None  # ok|error|running|skipped|...
    last_error: str | None = None
    last_run_at: datetime | None = None
    last_run_bucket: str | None = None

    created_at: datetime | None = None
    updated_at: datetime | None = None


class PostgresCronStore:
    def __init__(self, db_dsn: str):
        self.db_dsn = db_dsn

    async def ensure_schema(self) -> None:
        ddl = """
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

        CREATE INDEX IF NOT EXISTS cron_tasks_user_thread_enabled_idx
          ON cron_tasks (user_id, thread_id, enabled);

        CREATE INDEX IF NOT EXISTS cron_tasks_enabled_idx
          ON cron_tasks (enabled);
        """

        async with await psycopg.AsyncConnection.connect(self.db_dsn) as conn:
            async with conn.cursor() as cur:
                await cur.execute(ddl)
            await conn.commit()

    async def upsert_task(
        self,
        *,
        task_id: str | None,
        name: str,
        user_id: str,
        thread_id: str,
        message: str,
        deliver: bool,
        enabled: bool,
        delete_after_run: bool,
        schedule: CronSchedule,
    ) -> CronTask:
        task_id = task_id or str(uuid.uuid4())

        async with await psycopg.AsyncConnection.connect(self.db_dsn) as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    INSERT INTO cron_tasks (
                      id, name, user_id, thread_id,
                      message, deliver, enabled, delete_after_run,
                      schedule_kind, at_time, every_seconds, cron_expr, tz,
                      last_status, last_error, last_run_at, last_run_bucket,
                      created_at, updated_at
                    )
                    VALUES (
                      %(id)s, %(name)s, %(user_id)s, %(thread_id)s,
                      %(message)s, %(deliver)s, %(enabled)s, %(delete_after_run)s,
                      %(schedule_kind)s, %(at_time)s, %(every_seconds)s, %(cron_expr)s, %(tz)s,
                      NULL, NULL, NULL, NULL,
                      now(), now()
                    )
                    ON CONFLICT (id) DO UPDATE SET
                      name = EXCLUDED.name,
                      user_id = EXCLUDED.user_id,
                      thread_id = EXCLUDED.thread_id,
                      message = EXCLUDED.message,
                      deliver = EXCLUDED.deliver,
                      enabled = EXCLUDED.enabled,
                      delete_after_run = EXCLUDED.delete_after_run,
                      schedule_kind = EXCLUDED.schedule_kind,
                      at_time = EXCLUDED.at_time,
                      every_seconds = EXCLUDED.every_seconds,
                      cron_expr = EXCLUDED.cron_expr,
                      tz = EXCLUDED.tz,
                      last_status = NULL,
                      last_error = NULL,
                      last_run_at = NULL,
                      last_run_bucket = NULL,
                      updated_at = now()
                    RETURNING
                      id, name, user_id, thread_id,
                      message, deliver, enabled, delete_after_run,
                      schedule_kind, at_time, every_seconds, cron_expr, tz,
                      last_status, last_error, last_run_at, last_run_bucket,
                      created_at, updated_at
                    """,
                    {
                        "id": task_id,
                        "name": name,
                        "user_id": user_id,
                        "thread_id": thread_id,
                        "message": message,
                        "deliver": deliver,
                        "enabled": enabled,
                        "delete_after_run": delete_after_run,
                        "schedule_kind": schedule.kind,
                        "at_time": schedule.at_time,
                        "every_seconds": schedule.every_seconds,
                        "cron_expr": schedule.cron_expr,
                        "tz": schedule.tz,
                    },
                )
                row = await cur.fetchone()

        return self._row_to_task(row)

    async def get_task(self, task_id: str) -> CronTask | None:
        async with await psycopg.AsyncConnection.connect(self.db_dsn) as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT
                      id, name, user_id, thread_id,
                      message, deliver, enabled, delete_after_run,
                      schedule_kind, at_time, every_seconds, cron_expr, tz,
                      last_status, last_error, last_run_at, last_run_bucket,
                      created_at, updated_at
                    FROM cron_tasks
                    WHERE id = %(id)s
                    """,
                    {"id": task_id},
                )
                row = await cur.fetchone()

        return self._row_to_task(row) if row else None

    async def list_tasks(
        self,
        *,
        user_id: str,
        thread_id: str,
        include_disabled: bool = False,
    ) -> list[CronTask]:
        where = "enabled = TRUE" if not include_disabled else "TRUE"
        params = {"user_id": user_id, "thread_id": thread_id}

        async with await psycopg.AsyncConnection.connect(self.db_dsn) as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    f"""
                    SELECT
                      id, name, user_id, thread_id,
                      message, deliver, enabled, delete_after_run,
                      schedule_kind, at_time, every_seconds, cron_expr, tz,
                      last_status, last_error, last_run_at, last_run_bucket,
                      created_at, updated_at
                    FROM cron_tasks
                    WHERE user_id = %(user_id)s
                      AND thread_id = %(thread_id)s
                      AND {where}
                    ORDER BY updated_at DESC
                    """,
                    params,
                )
                rows = await cur.fetchall()

        return [self._row_to_task(r) for r in rows]

    async def remove_task(self, *, task_id: str, user_id: str, thread_id: str) -> bool:
        async with await psycopg.AsyncConnection.connect(self.db_dsn) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    DELETE FROM cron_tasks
                    WHERE id = %(id)s
                      AND user_id = %(user_id)s
                      AND thread_id = %(thread_id)s
                    """,
                    {"id": task_id, "user_id": user_id, "thread_id": thread_id},
                )
                deleted = cur.rowcount == 1
            await conn.commit()
        return deleted

    async def claim_run(self, *, task_id: str, bucket: str) -> bool:
        """
        Атомарно забрать выполнение.
        Если last_run_bucket == bucket, значит это дубль и выполнять нельзя.
        """
        now = datetime.now(timezone.utc)
        async with await psycopg.AsyncConnection.connect(self.db_dsn) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE cron_tasks
                    SET
                      last_status = 'running',
                      last_run_at = %(now)s,
                      last_run_bucket = %(bucket)s,
                      updated_at = now()
                    WHERE
                      id = %(id)s
                      AND enabled = TRUE
                      AND (last_run_bucket IS NULL OR last_run_bucket <> %(bucket)s)
                    """,
                    {"id": task_id, "bucket": bucket, "now": now},
                )
                claimed = cur.rowcount == 1
            await conn.commit()
        return claimed

    async def mark_ok(self, *, task_id: str) -> None:
        async with await psycopg.AsyncConnection.connect(self.db_dsn) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE cron_tasks
                    SET last_status = 'ok',
                        last_error = NULL,
                        updated_at = now()
                    WHERE id = %(id)s
                    """,
                    {"id": task_id},
                )
            await conn.commit()

    async def mark_error(self, *, task_id: str, error: str) -> None:
        async with await psycopg.AsyncConnection.connect(self.db_dsn) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE cron_tasks
                    SET last_status = 'error',
                        last_error = %(error)s,
                        updated_at = now()
                    WHERE id = %(id)s
                    """,
                    {"id": task_id, "error": error},
                )
            await conn.commit()

    async def finalize_after_run(self, *, task: CronTask) -> None:
        """
        Для one-shot tasks выключаем/удаляем таск после выполнения.
        """
        if task.delete_after_run:
            async with await psycopg.AsyncConnection.connect(self.db_dsn) as conn:
                async with conn.cursor() as cur:
                    await cur.execute("DELETE FROM cron_tasks WHERE id = %(id)s", {"id": task.id})
                await conn.commit()
            return

        if task.schedule.kind == "at":
            async with await psycopg.AsyncConnection.connect(self.db_dsn) as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        UPDATE cron_tasks
                        SET enabled = FALSE,
                            updated_at = now()
                        WHERE id = %(id)s
                        """,
                        {"id": task.id},
                    )
                await conn.commit()

    async def load_enabled_tasks(self) -> list[CronTask]:
        async with await psycopg.AsyncConnection.connect(self.db_dsn) as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT
                      id, name, user_id, thread_id,
                      message, deliver, enabled, delete_after_run,
                      schedule_kind, at_time, every_seconds, cron_expr, tz,
                      last_status, last_error, last_run_at, last_run_bucket,
                      created_at, updated_at
                    FROM cron_tasks
                    WHERE enabled = TRUE
                    """
                )
                rows = await cur.fetchall()
        return [self._row_to_task(r) for r in rows]

    @staticmethod
    def _row_to_task(row: dict) -> CronTask:
        schedule_kind = row["schedule_kind"]
        schedule = CronSchedule(
            kind=schedule_kind,  # type: ignore[arg-type]
            at_time=row["at_time"],
            every_seconds=row["every_seconds"],
            cron_expr=row["cron_expr"],
            tz=row["tz"],
        )
        return CronTask(
            id=row["id"],
            name=row["name"],
            user_id=row["user_id"],
            thread_id=row["thread_id"],
            message=row["message"],
            deliver=row["deliver"],
            enabled=row["enabled"],
            delete_after_run=row["delete_after_run"],
            schedule=schedule,
            last_status=row["last_status"],
            last_error=row["last_error"],
            last_run_at=row["last_run_at"],
            last_run_bucket=row["last_run_bucket"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

