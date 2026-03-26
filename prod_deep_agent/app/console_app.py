"""Консольное приложение с меню: список чатов, новый чат, вход в чат (последние 20 сообщений). В чате: /bye — выход в меню."""
from __future__ import annotations

import sys
import uuid
from typing import Optional

import psycopg
import asyncio
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .agent_factory import create_langchain_agent_with_mcp_filesystem_async
from .agent_factory import create_agent_with_mcp_async
from .memory import AsyncProductionMemory, init_async_production_memory
from .settings import load_settings
from .cron.context import active_thread_id, active_user_id, cron_execution
from .cron.manager import CronDeliveryEvent, CronManager
from .cron.tools import make_cron_tools

console = Console()

# checkpoint_ns в БД: в текущем CLI user_id не передаётся, поэтому используется пустая строка
CHECKPOINT_NS = ""


def _get_config(
    thread_id: str,
    checkpoint_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> RunnableConfig:
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    if checkpoint_id:
        config["configurable"]["checkpoint_id"] = checkpoint_id
    if user_id:
        config["configurable"]["user_id"] = user_id
    return config


def list_thread_ids(database_url: str) -> list[str]:
    """Список thread_id из таблицы checkpoints (checkpoint_ns = '' как в CLI)."""
    try:
        with psycopg.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT DISTINCT thread_id FROM checkpoints WHERE checkpoint_ns = %s ORDER BY thread_id",
                    (CHECKPOINT_NS,),
                )
                return [row[0] for row in cur.fetchall()]
    except Exception as e:
        console.print(f"[red]Ошибка при загрузке списка чатов: {e}[/red]")
        return []


async def get_last_messages(
    agent,
    config: RunnableConfig,
    limit: int = 20,
) -> list:
    """Последние limit сообщений из состояния диалога."""
    try:
        state = await agent.aget_state(config)
        messages = state.values.get("messages", [])[-limit:]
        return list(messages)
    except Exception:
        return []


def _message_content(msg) -> str:
    """Извлечь текст из сообщения (HumanMessage / AIMessage или иное)."""
    content = getattr(msg, "content", str(msg))
    if isinstance(content, list):
        parts = []
        for block in content:
            if hasattr(block, "get") and isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
                else:
                    parts.append(str(block))
            else:
                parts.append(str(block))
        return "\n".join(parts)
    return content if isinstance(content, str) else str(content)


def print_messages(messages: list) -> None:
    """Вывести сообщения в консоль: Вы: / Агент:."""
    if not messages:
        console.print("[dim]Нет сообщений.[/dim]\n")
        return
    for msg in messages:
        content = _message_content(msg)
        if not content:
            continue
        if isinstance(msg, HumanMessage):
            console.print(f"[bold blue]Вы[/bold blue]: {content}\n")
        elif isinstance(msg, AIMessage):
            console.print(f"[green]Агент[/green]: {content}\n")
        else:
            console.print(f"[dim]{type(msg).__name__}[/dim]: {content}\n")


def _print_cron_events(
    cron_queue: asyncio.Queue[CronDeliveryEvent] | None,
    *,
    current_thread_id: str | None = None,
) -> None:
    if cron_queue is None:
        return
    pending: list[CronDeliveryEvent] = []
    while True:
        try:
            ev = cron_queue.get_nowait()
        except asyncio.QueueEmpty:
            break
        if current_thread_id is None or ev.thread_id == current_thread_id:
            console.print(
                f"[magenta][Cron][/magenta] thread_id={ev.thread_id} user_id={ev.user_id}\n{ev.text}\n"
            )
        else:
            pending.append(ev)
    for ev in pending:
        # Put back so other chat sessions can see their own cron events.
        cron_queue.put_nowait(ev)


async def _read_user_input(
    prompt: str,
    cron_queue: asyncio.Queue[CronDeliveryEvent] | None = None,
    *,
    current_thread_id: str | None = None,
) -> str:
    # Read input in a worker thread so AsyncIOScheduler can keep running.
    input_task = asyncio.create_task(asyncio.to_thread(console.input, prompt))
    while True:
        _print_cron_events(cron_queue, current_thread_id=current_thread_id)
        done, _pending = await asyncio.wait({input_task}, timeout=0.5)
        if input_task in done:
            return input_task.result().strip()


async def run_chat_loop(
    agent,
    thread_id: str,
    memory: AsyncProductionMemory,
    user_id: Optional[str] = None,
    cron_queue: asyncio.Queue[CronDeliveryEvent] | None = None,
) -> None:
    """
    Цикл чата для thread_id. /bye — выход в главное меню, quit/exit — выход из приложения.
    """
    config = _get_config(thread_id, user_id=user_id)
    last_20 = await get_last_messages(agent, config, limit=20)
    console.print(Panel(f"Чат [bold]{thread_id[:8]}…[/bold]", title="История (последние 20)"))
    print_messages(last_20)
    console.print("[dim]Введите сообщение. /bye — в главное меню, quit или exit — выход из приложения.[/dim]\n")

    while True:
        try:
            text = await _read_user_input(
                "[bold blue]Вы[/bold blue]: ",
                cron_queue=cron_queue,
                current_thread_id=thread_id,
            )
        except (EOFError, KeyboardInterrupt):
            break
        if not text:
            continue
        if text.lower() in ("/bye",):
            console.print("[dim]Возврат в главное меню.[/dim]\n")
            return
        if text.lower() in ("quit", "exit", "q"):
            console.print("[dim]Выход из приложения.[/dim]")
            sys.exit(0)
        tokens = []
        uid = user_id or "anonymous"
        tokens.append(active_user_id.set(uid))
        tokens.append(active_thread_id.set(thread_id))
        tokens.append(cron_execution.set(False))
        try:
            result = await agent.ainvoke(
                {"messages": [HumanMessage(content=text)]},
                config=_get_config(thread_id, user_id=user_id),
            )
        finally:
            cron_execution.reset(tokens.pop())
            active_thread_id.reset(tokens.pop())
            active_user_id.reset(tokens.pop())
        msgs = result.get("messages", [])
        if msgs:
            last = msgs[-1]
            content = _message_content(last)
            if content:
                console.print(f"[green]Агент[/green]: {content}\n")


def show_threads(thread_ids: list[str]) -> None:
    """Нумерованный список чатов."""
    if not thread_ids:
        console.print("[yellow]Нет сохранённых чатов. Создайте новый чат.[/yellow]\n")
        return
    table = Table(title="Чаты")
    table.add_column("№", justify="right", style="dim")
    table.add_column("thread_id", style="cyan")
    for i, tid in enumerate(thread_ids, 1):
        table.add_row(str(i), tid)
    console.print(table)
    console.print()


async def run_console_app() -> None:
    """Главный цикл: меню → список чатов / новый чат / войти в чат / выход."""
    settings = load_settings()
    user_id: Optional[str] = None  # при необходимости можно брать из env
    cron_queue: asyncio.Queue[CronDeliveryEvent] = asyncio.Queue()

    async with init_async_production_memory(settings.database_url) as memory:
        agent_ref: dict[str, object] = {"agent": None}

        async def on_execute(task) -> str | None:
            agent_obj = agent_ref.get("agent")
            if agent_obj is None:
                return None
            # Отдельный thread для cron execution, чтобы не портить пользовательскую историю.
            exec_thread_id = f"cron:{task.id}"
            instruction = (
                "[Cron Execution]\n"
                f"Task '{task.name}' has been triggered.\n"
                f"Instruction: {task.message}\n\n"
                "Rule: НЕ вызывай cron tools и вообще любые инструменты. "
                "Просто сформируй сообщение пользователю."
            )
            result = await agent_obj.ainvoke(
                {"messages": [HumanMessage(content=instruction)]},
                config=_get_config(exec_thread_id, user_id=task.user_id),
            )
            msgs = result.get("messages", [])
            if not msgs:
                return None
            last = msgs[-1]
            content = _message_content(last)
            return content if content else None

        cron_manager = CronManager(
            db_dsn=settings.database_url,
            on_execute=on_execute,
            delivery_queue=cron_queue,
        )
        cron_tools = make_cron_tools(cron_manager)

        agent = await create_agent_with_mcp_async(settings, memory, extra_tools=cron_tools)
        agent_ref["agent"] = agent
        await cron_manager.start()

        while True:
            console.print(Panel(
                "1 — Список чатов\n2 — Новый чат\n3 — Войти в чат\n4 — Выход",
                title="Главное меню",
            ))
            try:
                choice = console.input("Выбор: ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not choice:
                continue
            if choice == "4":
                console.print("[dim]До свидания.[/dim]")
                break
            if choice == "1":
                thread_ids = list_thread_ids(settings.database_url)
                show_threads(thread_ids)
                continue
            if choice == "2":
                thread_id = str(uuid.uuid4())
                console.print(f"[green]Новый чат: {thread_id}[/green]\n")
                await run_chat_loop(agent, thread_id, memory, user_id, cron_queue=cron_queue)
                continue
            if choice == "3":
                thread_ids = list_thread_ids(settings.database_url)
                if not thread_ids:
                    console.print("[yellow]Нет чатов. Сначала создайте новый (п. 2).[/yellow]\n")
                    continue
                show_threads(thread_ids)
                raw = console.input("Введите номер чата или thread_id: ").strip()
                if not raw:
                    continue
                if raw.isdigit():
                    idx = int(raw)
                    if idx < 1 or idx > len(thread_ids):
                        console.print("[red]Неверный номер.[/red]\n")
                        continue
                    thread_id = thread_ids[idx - 1]
                else:
                    thread_id = raw
                await run_chat_loop(agent, thread_id, memory, user_id, cron_queue=cron_queue)
                continue
            console.print("[yellow]Введите 1, 2, 3 или 4.[/yellow]\n")

        await cron_manager.stop()


if __name__ == "__main__":
    asyncio.run(run_console_app())
