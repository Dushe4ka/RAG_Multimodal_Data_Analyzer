# config.py
from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://developer:12357985@localhost:5432/mydb")
    MODEL: str = os.getenv("MODEL", "gpt-4.1")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "openai:text-embedding-3-small")
    MAX_CONTEXT_TOKENS: int = 8000  # Лимит для обрезки истории