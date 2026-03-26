from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from .context import active_thread_id, active_user_id, cron_execution
from .manager import CronManager
from .store import CronSchedule


def _parse_at_iso(at_iso: str) -> datetime:
    # datetime.fromisoformat doesn't parse trailing 'Z' prior to strict tz handling.
    iso = at_iso.strip()
    if iso.endswith("Z"):
        iso = iso[:-1] + "+00:00"
    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None:
        # For one-time reminders we assume UTC when timezone is missing.
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _require_context() -> tuple[str, str] | str:
    if cron_execution.get():
        return "Error: cron tools are disabled during cron execution"
    uid = active_user_id.get()
    tid = active_thread_id.get()
    if not uid or not tid:
        return "Error: no active context (user_id/thread_id)."
    return uid, tid


def make_cron_tools(cron_manager: CronManager) -> list[Callable[..., Any]]:
    async def cron_add(
        message: str,
        every_seconds: int | None = None,
        cron_expr: str | None = None,
        tz: str | None = None,
        at_iso: str | None = None,
        delete_after_run: bool = False,
    ) -> str:
        """
        Create or update a cron task.

        You must pass exactly one schedule type:
        - every_seconds: recurring interval in seconds
        - cron_expr + optional tz: cron expression like "0 10 * * 1" (Mon 10:00)
        - at_iso: ISO datetime string for one-time execution, e.g. "2026-02-12T10:30:00+00:00"
        """
        ctx = _require_context()
        if isinstance(ctx, str):
            return ctx
        user_id, thread_id = ctx

        msg = (message or "").strip()
        if not msg:
            return "Error: message is required"

        name = msg[:50]

        schedule_kind_count = sum(1 for x in (every_seconds, cron_expr, at_iso) if x)
        if schedule_kind_count != 1:
            return "Error: provide exactly one of every_seconds, cron_expr, or at_iso"

        schedule_repr: str
        if every_seconds:
            if every_seconds <= 0:
                return "Error: every_seconds must be > 0"
            schedule = CronSchedule(kind="every", every_seconds=int(every_seconds))
            schedule_repr = f"every:{int(every_seconds)}"

        elif cron_expr:
            schedule = CronSchedule(kind="cron", cron_expr=cron_expr.strip(), tz=(tz.strip() if tz else None))
            schedule_repr = f"cron:{schedule.cron_expr}:{schedule.tz or 'UTC'}"

            # Validate cron_expr early by asking APScheduler trigger to build.
            try:
                # Lazy import: keeps module import light.
                from apscheduler.triggers.cron import CronTrigger

                CronTrigger.from_crontab(schedule.cron_expr, timezone=schedule.tz or "UTC")
            except Exception as e:
                return f"Error: invalid cron_expr/tz: {e}"

        else:
            if not at_iso:
                return "Error: at_iso is required for one-time tasks"
            try:
                at_time = _parse_at_iso(at_iso)
            except ValueError:
                return f"Error: invalid ISO datetime '{at_iso}'"
            schedule = CronSchedule(kind="at", at_time=at_time)
            schedule_repr = f"at:{int(at_time.timestamp())}"

        # Make cron_add idempotent for the same schedule within a (user, thread).
        # This prevents duplicate cron tasks if the LLM calls cron_add multiple times.
        schedule_hash = hashlib.sha256(
            f"{user_id}|{thread_id}|{schedule.kind}|{schedule_repr}".encode("utf-8")
        ).hexdigest()[:32]
        task_id = f"cron:{schedule_hash}"

        try:
            task = await cron_manager.upsert_task(
                user_id=user_id,
                thread_id=thread_id,
                task_id=task_id,
                name=name,
                message=msg,
                deliver=True,
                enabled=True,
                delete_after_run=bool(delete_after_run),
                schedule=schedule,
            )
        except Exception as e:
            return f"Error: failed to create task: {e}"

        return f"Created cron task id={task.id}"

    async def cron_list() -> str:
        """
        List active cron tasks for current user/thread context.
        """
        ctx = _require_context()
        if isinstance(ctx, str):
            return ctx
        user_id, thread_id = ctx

        tasks = await cron_manager.list_tasks(user_id=user_id, thread_id=thread_id)
        if not tasks:
            return "No cron tasks."

        lines: list[str] = []
        lines.append(f"Cron tasks for thread_id={thread_id}:")
        for t in tasks:
            if t.schedule.kind == "every":
                timing = f"every {t.schedule.every_seconds}s"
            elif t.schedule.kind == "cron":
                timing = f"cron '{t.schedule.cron_expr}' tz={t.schedule.tz or 'UTC'}"
            else:
                timing = f"at {t.schedule.at_time.isoformat() if t.schedule.at_time else '?'}"

            lines.append(f"- {t.id}: {t.name} ({timing})")
        return "\n".join(lines)

    async def cron_remove(job_id: str) -> str:
        """
        Remove a cron task by its id.
        """
        ctx = _require_context()
        if isinstance(ctx, str):
            return ctx
        user_id, thread_id = ctx

        raw_id = (job_id or "").strip()
        if not raw_id:
            return "Error: job_id is required"

        removed = await cron_manager.remove_task(task_id=raw_id, user_id=user_id, thread_id=thread_id)
        if removed:
            return f"Removed cron task {raw_id}"
        return f"Job {raw_id} not found"

    # DeepAgents принимает список callables.
    return [cron_add, cron_list, cron_remove]

