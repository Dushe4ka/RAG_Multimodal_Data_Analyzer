# memory_management.py
from langchain.agents.middleware import before_model, SummarizationMiddleware
from langchain_core.messages.utils import trim_messages, count_tokens_approximately
from langgraph.runtime import Runtime
from typing import Any

from _agent_final.config import Config


def get_trim_context_middleware(config: Config):
    """Возвращает middleware для обрезки истории сообщений до лимита токенов из конфига."""
    max_tokens = config.MAX_CONTEXT_TOKENS

    @before_model
    def trim_context_middleware(state: dict, runtime: Runtime) -> dict[str, Any] | None:
        messages = state.get("messages", [])
        if len(messages) <= 2:
            return None

        trimmed = trim_messages(
            messages,
            strategy="last",
            token_counter=count_tokens_approximately,
            max_tokens=max_tokens,
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

    return trim_context_middleware


def get_summarization_middleware(config: Config):
    """Возвращает middleware для автоматической суммаризации (параметры из конфига)."""
    return SummarizationMiddleware(
        model=config.MODEL,
        trigger=("tokens", config.SUMMARIZATION_TRIGGER_TOKENS),
        keep=("messages", config.SUMMARIZATION_KEEP_MESSAGES),
    )
