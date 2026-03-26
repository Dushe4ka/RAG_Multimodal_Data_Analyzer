from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Загружаем .env из директории prod_deep_agent (родитель app/)
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


@dataclass(frozen=True)
class Settings:
    database_url: str
    openai_api_key: str | None
    chat_model: str
    summary_model: str
    summary_trigger_tokens: int
    summary_keep_messages: int


def load_settings() -> Settings:
    load_dotenv(_ENV_PATH)

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "Переменная окружения DATABASE_URL не задана. "
            "Смотрите пример в prod_deep_agent/.env.example"
        )

    openai_api_key = os.getenv("OPENAI_API_KEY")
    chat_model = os.getenv("CHAT_MODEL", "gpt-4.1-mini")
    summary_model = os.getenv("SUMMARY_MODEL", chat_model)
    summary_trigger_tokens = int(os.getenv("SUMMARY_TRIGGER_TOKENS", "4000"))
    summary_keep_messages = int(os.getenv("SUMMARY_KEEP_MESSAGES", "20"))

    return Settings(
        database_url=database_url,
        openai_api_key=openai_api_key,
        chat_model=chat_model,
        summary_model=summary_model,
        summary_trigger_tokens=summary_trigger_tokens,
        summary_keep_messages=summary_keep_messages,
    )
