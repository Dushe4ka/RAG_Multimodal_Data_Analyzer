from typing import Literal

from langchain_openai import ChatOpenAI

from config import settings, settings_llm

DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 8196


def get_llm_model(
    provider: Literal["local", "openai"] = "local",
    model: Literal["thinking", "chat"] = "thinking",
) -> ChatOpenAI:
    """
    Возвращает экземпляр ChatOpenAI для выбранного провайдера и модели.

    Для provider="openai" аргумент model не используется — всегда берётся settings.OPENAI_MODEL.
    """
    common = {
        "temperature": DEFAULT_TEMPERATURE,
        "max_tokens": DEFAULT_MAX_TOKENS,
    }
    if provider == "local" and model == "thinking":
        return ChatOpenAI(
            model=settings_llm.QWEN_THINK,
            api_key=settings.LLM_API_KEY,
            base_url=settings_llm.QWEN_THINK_URL,
            **common,
        )
    if provider == "local" and model == "chat":
        return ChatOpenAI(
            model=settings_llm.QWEN_INSTRUCT,
            api_key=settings.LLM_API_KEY,
            base_url=settings_llm.QWEN_INSTRUCT_URL,
            **common,
        )
    if provider == "openai":
        return ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            **common,
        )
    raise ValueError(
        f"Неподдерживаемая комбинация: provider={provider!r}, model={model!r}. "
        "Допустимы provider in ('local', 'openai'), для local — model in ('thinking', 'chat')."
    )
