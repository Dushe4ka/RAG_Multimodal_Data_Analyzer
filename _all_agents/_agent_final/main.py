# main.py
"""Пример точки входа: checkpointer и store создаются один раз при старте
и закрываются при завершении работы приложения.
Интерактивный чат в консоли: введите сообщение и нажмите Enter.
Команды выхода: выход, exit, quit.

Запуск из корня проекта: python -m _agent_final.main
Из каталога _agent_final: python main.py"""
import asyncio
import sys

from _agent_final.config import Config
from _agent_final.memory import init_production_memory
from _agent_final.agent import create_production_agent
from _agent_final.usage import run_with_rollback_support
from _agent_final.mcp_integration import AgentContext


def read_user_input(prompt: str = "Вы: ") -> str:
    """Синхронный ввод в консоли (вызывается из executor)."""
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


async def read_async(prompt: str = "Вы: ") -> str:
    """Асинхронный ввод, не блокирует event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, read_user_input, prompt)


def last_agent_message_content(result) -> str:
    """Извлекает текст последнего ответа агента из результата ainvoke."""
    messages = result.get("messages") if isinstance(result, dict) else []
    if not messages:
        return str(result)
    for msg in reversed(messages):
        if hasattr(msg, "content") and msg.content:
            # Пропускаем сообщения пользователя
            if getattr(msg, "type", "") == "human":
                continue
            return msg.content if isinstance(msg.content, str) else str(msg.content)
    return str(result)


async def chat_loop(agent, thread_id: str, context: AgentContext):
    """Цикл интерактивного чата в консоли."""
    print("Чат запущен. Введите сообщение и нажмите Enter. Для выхода: выход / exit / quit.\n")
    while True:
        user_text = await read_async("Вы: ")
        if not user_text:
            continue
        if user_text.lower() in ("выход", "exit", "quit"):
            print("До свидания.")
            break
        try:
            result = await run_with_rollback_support(
                agent, user_text, thread_id=thread_id, context=context
            )
            reply = last_agent_message_content(result)
            print(f"Агент: {reply}\n")
        except Exception as e:
            print(f"Ошибка: {e}\n", file=sys.stderr)


async def main():
    config = Config()
    memory = init_production_memory(config)
    try:
        agent = await create_production_agent(config, memory)
        context = AgentContext(user_id="user-1", session_id="session-1")
        thread_id = "thread-1"
        await chat_loop(agent, thread_id, context)
    finally:
        memory.close()


if __name__ == "__main__":
    asyncio.run(main())
