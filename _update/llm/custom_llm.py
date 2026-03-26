"""
Фабрика LLM с поддержкой провайдеров DeepSeek, OpenAI и Custom (OpenAI-совместимый API).
Использует langchain-openai и langchain-deepseek.
Экземпляр можно использовать напрямую как LLM (invoke, ainvoke и т.д.).
"""

from typing import Literal

from langchain_core.language_models import BaseChatModel

# Предустановленные имена моделей по провайдерам
PRESET_MODELS = {
    "DeepSeek": ("deepseek-chat", "deepseek-reasoner"),
    "OpenAI": ("gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"),
    "Custom": ("qwen3",),  # пример; для Custom можно передать любое имя модели
}


def _create_llm(
    provider: str,
    model: str,
    api_key: str,
    temperature: float,
    max_tokens: int,
    base_url: str | None,
) -> BaseChatModel:
    if provider == "DeepSeek":
        from langchain_deepseek import ChatDeepSeek

        return ChatDeepSeek(
            model=model,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    if provider == "OpenAI":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            openai_api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    if provider == "Custom":
        from langchain_openai import ChatOpenAI

        if not base_url:
            raise ValueError("Для провайдера Custom необходимо указать base_url.")

        return ChatOpenAI(
            model=model,
            openai_api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    raise ValueError(f"Неизвестный провайдер: {provider}")


class CustomLLM:
    """
    Универсальный LLM с разными провайдерами.
    Экземпляр ведёт себя как LangChain LLM: можно вызывать .invoke(), .ainvoke() и т.д.
    """

    def __init__(
        self,
        provider: Literal["DeepSeek", "OpenAI", "Custom"],
        model: str,
        api_key: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        *,
        base_url: str | None = None,
    ):
        """
        Args:
            provider: Провайдер — DeepSeek, OpenAI или Custom (OpenAI-совместимый API).
            model: Имя модели (например deepseek-chat, gpt-4, qwen3 или путь к модели для Custom).
            api_key: API-ключ провайдера.
            temperature: Температура генерации (0.0–1.0).
            max_tokens: Максимальное число токенов в ответе.
            base_url: Базовый URL API (обязателен для Custom, например http://host:8000/v1).
        """
        self._llm = _create_llm(
            provider=provider,
            model=model,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            base_url=base_url,
        )

    def __getattr__(self, name: str):
        """Делегирование вызовов внутреннему LLM (invoke, ainvoke, bind_tools и т.д.)."""
        return getattr(self._llm, name)
