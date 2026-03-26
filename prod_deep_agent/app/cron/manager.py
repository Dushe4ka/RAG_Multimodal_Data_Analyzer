from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .context import active_thread_id, active_user_id, cron_execution
from .store import CronSchedule, CronTask, PostgresCronStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CronDeliveryEvent:
    user_id: str
    thread_id: str
    text: str


class CronManager:
    def __init__(
        self,
        *,
        db_dsn: str,
        on_execute: Callable[[CronTask], Awaitable[str | None]],
        delivery_queue: asyncio.Queue[CronDeliveryEvent] | None = None,
        scheduler_timezone: str = "UTC",
    ):
        self.store = PostgresCronStore(db_dsn)
        self.on_execute = on_execute
        self.delivery_queue = delivery_queue

        self.scheduler = AsyncIOScheduler(timezone=scheduler_timezone)
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        self._started = True

        await self.store.ensure_schema()

        tasks = await self.store.load_enabled_tasks()
        for task in tasks:
            self._schedule_job(task)

        self.scheduler.start()

    async def stop(self) -> None:
        if not self._started:
            return
        self._started = False
        self.scheduler.shutdown(wait=False)

    # ============ Public API for tools ============
    async def upsert_task(
        self,
        *,
        user_id: str,
        thread_id: str,
        name: str,
        message: str,
        schedule: CronSchedule,
        deliver: bool,
        enabled: bool = True,
        delete_after_run: bool = False,
        task_id: str | None = None,
    ) -> CronTask:
        task = await self.store.upsert_task(
            task_id=task_id,
            name=name,
            user_id=user_id,
            thread_id=thread_id,
            message=message,
            deliver=deliver,
            enabled=enabled,
            delete_after_run=delete_after_run,
            schedule=schedule,
        )
        if enabled:
            self._schedule_job(task)
        return task

    async def list_tasks(self, *, user_id: str, thread_id: str) -> list[CronTask]:
        return await self.store.list_tasks(user_id=user_id, thread_id=thread_id, include_disabled=False)

    async def remove_task(self, *, task_id: str, user_id: str, thread_id: str) -> bool:
        removed = await self.store.remove_task(task_id=task_id, user_id=user_id, thread_id=thread_id)
        if removed:
            self._unschedule_job(task_id)
        return removed

    # ============ Scheduler internals ============
    def _schedule_job(self, task: CronTask) -> None:
        trigger = self._build_trigger(task.schedule)
        # Используем id = task.id, чтобы tools могли remove_job(task_id) без дополнительных маппингов.
        self.scheduler.add_job(
            self._run_task_entry,
            trigger=trigger,
            args=[task.id],
            id=task.id,
            replace_existing=True,
            coalesce=True,
            max_instances=1,
            misfire_grace_time=120,
        )

    def _unschedule_job(self, task_id: str) -> None:
        try:
            self.scheduler.remove_job(task_id)
        except Exception:
            # job может не существовать (например, до первого запуска или уже удален)
            pass

    def _build_trigger(self, schedule: CronSchedule):
        if schedule.kind == "at":
            if not schedule.at_time:
                raise ValueError("at_time is required for schedule.kind='at'")
            return DateTrigger(run_date=schedule.at_time)

        if schedule.kind == "every":
            if not schedule.every_seconds or schedule.every_seconds <= 0:
                raise ValueError("every_seconds must be > 0 for schedule.kind='every'")
            return IntervalTrigger(seconds=schedule.every_seconds)

        if schedule.kind == "cron":
            if not schedule.cron_expr:
                raise ValueError("cron_expr is required for schedule.kind='cron'")
            tz = schedule.tz or "UTC"
            # CronTrigger умеет timezone.
            return CronTrigger.from_crontab(schedule.cron_expr, timezone=tz)

        raise ValueError(f"Unknown schedule kind: {schedule.kind}")

    @staticmethod
    def _run_bucket(task: CronTask, now_utc: datetime) -> str:
        """
        Для идемпотентности считаем bucket по “интервалу выполнения”.
        Важно, чтобы для schedule.kind='every' bucket учитывал every_seconds,
        иначе для частых интервалов мы начнем “склеивать” разные срабатывания.
        """
        now_epoch = int(now_utc.timestamp())

        if task.schedule.kind == "every":
            secs = task.schedule.every_seconds or 1
            return str(now_epoch // max(1, secs))

        if task.schedule.kind == "cron":
            # В cron обычно минимум минутная точность.
            return str(now_epoch // 60)

        if task.schedule.kind == "at":
            if not task.schedule.at_time:
                return str(now_epoch // 60)
            at_dt = task.schedule.at_time
            if at_dt.tzinfo is None:
                at_dt = at_dt.replace(tzinfo=timezone.utc)
            else:
                at_dt = at_dt.astimezone(timezone.utc)
            return f"at:{int(at_dt.timestamp())}"

        return str(now_epoch // 60)

    async def _run_task_entry(self, task_id: str) -> None:
        """
        Entry point для APScheduler (из job queue).
        Делаем:
        - load task from DB
        - claim execution (idempotency)
        - call agent (on_execute)
        - deliver + update status
        - finalize (disable/delete for one-shot)
        """
        now_utc = datetime.now(timezone.utc)
        task = await self.store.get_task(task_id)
        if not task or not task.enabled:
            return

        bucket = self._run_bucket(task, now_utc)
        claimed = await self.store.claim_run(task_id=task_id, bucket=bucket)
        if not claimed:
            return

        token_user = active_user_id.set(task.user_id)
        token_thread = active_thread_id.set(task.thread_id)
        token_cron = cron_execution.set(True)
        try:
            response_text: str | None = None
            try:
                response_text = await self.on_execute(task)
            except Exception as e:
                logger.exception("Cron on_execute failed for task_id=%s", task_id)
                await self.store.mark_error(task_id=task_id, error=str(e))
                return

            if response_text and task.deliver and self.delivery_queue is not None:
                await self.delivery_queue.put(
                    CronDeliveryEvent(user_id=task.user_id, thread_id=task.thread_id, text=response_text)
                )

            await self.store.mark_ok(task_id=task_id)

            # One-shot cleanup
            if task.schedule.kind == "at" or task.delete_after_run:
                await self.store.finalize_after_run(task=task)
                self._unschedule_job(task_id)
        finally:
            cron_execution.reset(token_cron)
            active_thread_id.reset(token_thread)
            active_user_id.reset(token_user)

