"""
Эмбеддинги: единый интерфейс для Qwen (локальный API) и OpenAI (облачный).
"""
import asyncio
from typing import List, Literal, Optional

import httpx
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from config import settings

# Дефолты для локального Qwen embedding API
DEFAULT_QWEN_EMBED_URL = "http://localhost:8082"
DEFAULT_QWEN_EMBED_MODEL = "/Qwen3-Embedding-0.6B-f16.gguf"


class QwenEmbeddings(Embeddings):
    """Локальный эмбеддер через OpenAI-совместимый API (Qwen и др.)."""

    def __init__(
        self,
        api_url: str = DEFAULT_QWEN_EMBED_URL,
        model_name: str = DEFAULT_QWEN_EMBED_MODEL,
    ):
        self.api_url = api_url.rstrip("/")
        self.model_name = model_name

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return asyncio.run(self._embed_async(texts))

    async def _embed_async(self, texts: List[str]) -> List[List[float]]:
        async with httpx.AsyncClient() as client:
            tasks = [
                client.post(
                    f"{self.api_url}/v1/embeddings",
                    json={"input": text, "model": self.model_name},
                )
                for text in texts
            ]
            responses = await asyncio.gather(*tasks)
            return [r.json()["data"][0]["embedding"] for r in responses]

    def embed_query(self, text: str) -> List[float]:
        return asyncio.run(self._embed_single(text))

    async def _embed_single(self, text: str) -> List[float]:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/v1/embeddings",
                json={"input": text, "model": self.model_name},
            )
            return response.json()["data"][0]["embedding"]

    def set_model(self, model_name: str) -> None:
        self.model_name = model_name

    def get_model(self) -> str:
        return self.model_name


class EmbedModel(Embeddings):
    """
    Единый эмбеддер с выбором провайдера: qwen (локальный) или openai (облачный).
    Интерфейс как у UniversalEmbeddings: embed_documents, embed_query, set_model/get_model (для qwen).
    """

    def __init__(
        self,
        provider: Literal["qwen", "openai"] = "qwen",
        *,
        api_url: Optional[str] = None,
        model_name: Optional[str] = None,
        openai_model: Optional[str] = None,
    ):
        self.provider = provider
        self._impl: Embeddings = get_embed_model(
            provider,
            api_url=api_url,
            model_name=model_name,
            openai_model=openai_model,
        )

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._impl.embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        return self._impl.embed_query(text)

    def set_model(self, model_name: str) -> None:
        if hasattr(self._impl, "set_model"):
            self._impl.set_model(model_name)

    def get_model(self) -> str:
        if hasattr(self._impl, "get_model"):
            return self._impl.get_model()
        return getattr(self._impl, "model", "openai")


def get_embed_model(
    provider: Literal["qwen", "openai"] = "qwen",
    *,
    api_url: Optional[str] = None,
    model_name: Optional[str] = None,
    openai_model: Optional[str] = None,
) -> Embeddings:
    """
    Возвращает эмбеддер для выбранного провайдера.

    Args:
        provider: "qwen" — локальный API (OpenAI-совместимый), "openai" — облачный OpenAI.
        api_url: Для qwen — URL сервера эмбеддингов (по умолчанию http://localhost:8082).
        model_name: Для qwen — имя модели (по умолчанию Qwen3-Embedding-0.6B).
        openai_model: Для openai — имя модели (по умолчанию text-embedding-3-small).

    Returns:
        Реализация Embeddings (embed_documents, embed_query).
    """
    if provider == "qwen":
        return QwenEmbeddings(
            api_url=api_url or DEFAULT_QWEN_EMBED_URL,
            model_name=model_name or DEFAULT_QWEN_EMBED_MODEL,
        )
    if provider == "openai":
        return OpenAIEmbeddings(
            api_key=settings.OPENAI_API_KEY,
            model=openai_model or "text-embedding-3-small",
        )
