# memory_management.py
from langchain.agents.middleware import before_model, SummarizationMiddleware
from langchain_core.messages.utils import trim_messages, count_tokens_approximately
from langgraph.runtime import Runtime
from typing import Any

@before_model
def trim_context_middleware(state: dict, runtime: Runtime) -> dict[str, Any] | None:
    """Обрезает историю сообщений до лимита токенов"""
    messages = state.get("messages", [])
    if len(messages) <= 2:
        return None
    
    trimmed = trim_messages(
        messages,
        strategy="last",
        token_counter=count_tokens_approximately,
        max_tokens=8000,  # Настройте под вашу модель
        start_on="human",
        end_on=("human", "tool"),
    )
    
    if len(trimmed) == len(messages):
        return None
    
    from langchain.messages import RemoveMessage
    from langgraph.graph.message import REMOVE_ALL_MESSAGES
    
    return {
        "messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *trimmed]
    }

def get_summarization_middleware(model: str):
    """Возвращает middleware для автоматической суммаризации"""
    return SummarizationMiddleware(
        model=model,
        trigger=("tokens", 6000),  # Начинаем суммаризировать при 6000 токенах
        keep=("messages", 10)       # Всегда держим последние 10 сообщений
    )