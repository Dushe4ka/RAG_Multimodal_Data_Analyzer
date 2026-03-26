"""CLI: chat, history, rollback, memory."""
from __future__ import annotations

import uuid
from typing import Optional

import typer
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from rich.console import Console
from rich.table import Table

from .agent_factory import create_agent
from .memory import init_production_memory
from .settings import load_settings

console = Console()
app = typer.Typer(help="Агент с кратко- и долговременной памятью (DeepAgents + Postgres)")


def _ensure_thread_id(thread_id: Optional[str]) -> str:
    if thread_id:
        return thread_id
    tid = str(uuid.uuid4())
    console.print(f"[dim]thread_id не задан, используем: {tid}[/dim]")
    return tid


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


@app.command()
def chat(
    thread_id: Optional[str] = typer.Option(None, "--thread-id", "-t", help="ID диалога (если не задан — генерируется UUID)"),
    user_id: Optional[str] = typer.Option(None, "--user-id", "-u", help="ID пользователя (для неймспейсов долговременной памяти)"),
    from_checkpoint: Optional[str] = typer.Option(None, "--from-checkpoint", help="Продолжить с указанного checkpoint_id (откат)"),
) -> None:
    """Интерактивный чат с агентом. Кратковременная память — по thread_id, долговременная — /memories/*."""
    settings = load_settings()
    tid = _ensure_thread_id(thread_id)

    with init_production_memory(settings.database_url) as memory:
        agent = create_agent(settings, memory)
        config = _get_config(tid, checkpoint_id=from_checkpoint, user_id=user_id)

        console.print("[bold]Чат (краткосрочная память по thread_id, долгосрочная — /memories/). Выход: quit, exit[/bold]\n")
        while True:
            try:
                text = typer.prompt("Вы")
            except (EOFError, KeyboardInterrupt):
                break
            if not text or text.strip().lower() in ("quit", "exit", "q"):
                break
            config = _get_config(tid, user_id=user_id)
            if from_checkpoint:
                config["configurable"]["checkpoint_id"] = from_checkpoint
                from_checkpoint = None
            result = agent.invoke(
                {"messages": [HumanMessage(content=text.strip())]},
                config=config,
            )
            msgs = result.get("messages", [])
            if msgs:
                last = msgs[-1]
                content = getattr(last, "content", str(last))
                if content:
                    console.print(f"[green]Агент[/green]: {content}\n")

    console.print("[dim]Сессия завершена.[/dim]")


@app.command()
def history(
    thread_id: str = typer.Option(..., "--thread-id", "-t", help="ID диалога"),
    limit: int = typer.Option(20, "--limit", "-n", help="Сколько чекпоинтов показать"),
) -> None:
    """Показать историю чекпоинтов диалога (для отката)."""
    settings = load_settings()
    config = _get_config(thread_id)

    with init_production_memory(settings.database_url) as memory:
        agent = create_agent(settings, memory)
        snapshots = list(agent.get_state_history(config))
        if not snapshots:
            console.print("[yellow]Нет чекпоинтов для этого thread_id.[/yellow]")
            return
        snapshots = snapshots[:limit]
        table = Table(title=f"История thread_id={thread_id}")
        table.add_column("checkpoint_id", style="dim")
        table.add_column("step", justify="right")
        table.add_column("created_at", style="dim")
        for s in snapshots:
            cid = s.config.get("configurable", {}).get("checkpoint_id", "")
            step = s.metadata.get("step", "")
            created = getattr(s, "created_at", "") or ""
            table.add_row(str(cid)[:36], str(step), str(created))
        console.print(table)
        console.print("\n[dim]Откат: chat --thread-id %s --from-checkpoint <checkpoint_id>[/dim]" % thread_id)


@app.command()
def rollback(
    thread_id: str = typer.Option(..., "--thread-id", "-t", help="ID диалога"),
    checkpoint_id: Optional[str] = typer.Option(None, "--checkpoint-id", "-c", help="Продолжить с этого чекпоинта"),
    steps: Optional[int] = typer.Option(None, "--steps", "-n", help="Откатиться на N шагов назад (выбрать checkpoint по счёту)"),
) -> None:
    """Откат: следующий запуск chat будет с выбранного чекпоинта. Укажите --checkpoint-id или --steps."""
    if not checkpoint_id and steps is None:
        console.print("[red]Укажите --checkpoint-id или --steps.[/red]")
        raise typer.Exit(1)
    settings = load_settings()
    config = _get_config(thread_id)

    with init_production_memory(settings.database_url) as memory:
        agent = create_agent(settings, memory)
        snapshots = list(agent.get_state_history(config))
        if not snapshots:
            console.print("[yellow]Нет чекпоинтов для этого thread_id.[/yellow]")
            return
        if steps is not None:
            idx = min(steps, len(snapshots) - 1)
            chosen = snapshots[idx]
            checkpoint_id = chosen.config.get("configurable", {}).get("checkpoint_id")
        if not checkpoint_id:
            console.print("[red]Не удалось определить checkpoint_id.[/red]")
            raise typer.Exit(1)
    console.print(f"[green]Запустите чат с откатом:[/green]")
    console.print(f"  [bold]chat --thread-id {thread_id} --from-checkpoint {checkpoint_id}[/bold]")


@app.command("memory")
def memory_cmd(
    action: str = typer.Argument(..., help="ls | read | write"),
    path: str = typer.Argument("/memories/", help="Путь в store, например /memories/preferences.txt"),
    content: Optional[str] = typer.Option(None, "--content", "-c", help="Для write: содержимое (одна строка)"),
    thread_id: Optional[str] = typer.Option(None, "--thread-id", "-t", help="Namespace как у агента (по умолчанию cli)"),
) -> None:
    """Работа с долговременной памятью (файлы в /memories/*). ls — список, read — прочитать, write — записать."""
    settings = load_settings()
    if not path.startswith("/memories/"):
        path = "/memories/" + path.lstrip("/")

    with init_production_memory(settings.database_url) as memory:
        store = memory.store
        namespace = (thread_id or "cli", "filesystem")
        key = path.replace("/memories/", "/").strip("/") or "."
        if action == "ls":
            try:
                items = store.search(namespace, limit=100)
            except TypeError:
                items = store.search(namespace, query="", limit=100)
            if not items:
                console.print("[dim]Пусто или путь не найден.[/dim]")
                return
            for it in items:
                k = getattr(it, "id", getattr(it, "key", str(it)))
                v = getattr(it, "value", it)
                if hasattr(v, "get") and isinstance(v, dict) and "content" in v:
                    lines = v.get("content", [])
                    preview = (lines[0][:60] + "…") if lines else ""
                else:
                    preview = str(v)[:60]
                console.print(f"  {k}: {preview}")
        elif action == "read":
            item = store.get(namespace, key)
            if item is None:
                console.print("[yellow]Файл не найден.[/yellow]")
                return
            val = item.value if hasattr(item, "value") else item
            if isinstance(val, dict) and "content" in val:
                console.print("\n".join(val["content"]))
            else:
                console.print(val)
        elif action == "write":
            if content is None:
                console.print("[red]Для write укажите --content.[/red]")
                raise typer.Exit(1)
            from deepagents.backends.utils import create_file_data
            data = create_file_data(content)
            store.put(namespace, key, data)
            console.print(f"[green]Записано: {path}[/green]")
        else:
            console.print("[red]Действие: ls | read | write[/red]")
            raise typer.Exit(1)


@app.command()
def menu() -> None:
    """Консольное меню: список чатов, новый чат, вход в чат (последние 20 сообщений). В чате: /bye — в меню."""
    import asyncio
    from .console_app import run_console_app
    asyncio.run(run_console_app())


def main() -> None:
    app()


if __name__ == "__main__":
    main()
