"""
Эмбеддинги: Qwen (локальный API), OpenAI (облачный), BGE-M3 (локально через FlagEmbedding).

BGE-M3: dense + лексический sparse + ColBERT (мультивектор) — см. VectorStore с sparse_backend=\"bgem3\" и use_colbert.
"""
from __future__ import annotations

import asyncio
from typing import Any, List, Literal, Optional

import httpx
import numpy as np
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from config import settings

# Дефолты для локального Qwen embedding API
DEFAULT_QWEN_EMBED_URL = "http://localhost:8082"
DEFAULT_QWEN_EMBED_MODEL = "/Qwen3-Embedding-0.6B-f16.gguf"

DEFAULT_BGE_M3_MODEL = "BAAI/bge-m3"


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


class BGEM3Embeddings(Embeddings):
    """
    Локальный BGE-M3 через FlagEmbedding: dense (LangChain), плюс encode_batch для sparse/ColBERT.
    Ленивая загрузка модели при первом вызове.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_BGE_M3_MODEL,
        *,
        use_fp16: bool = True,
        devices: Optional[List[str]] = None,
        batch_size: int = 12,
        max_length: int = 8192,
    ):
        self.model_name = model_name
        self.use_fp16 = use_fp16
        self.devices = devices
        self.batch_size = batch_size
        self.max_length = max_length
        self._model: Any = None

    def _ensure_model(self) -> Any:
        if self._model is None:
            try:
                from FlagEmbedding import BGEM3FlagModel
            except ImportError as e:
                raise ImportError(
                    "Для BGE-M3 установите FlagEmbedding (и PyTorch): pip install FlagEmbedding"
                ) from e
            kwargs: dict[str, Any] = {"use_fp16": self.use_fp16}
            if self.devices is not None:
                kwargs["devices"] = self.devices
            self._model = BGEM3FlagModel(self.model_name, **kwargs)
        return self._model

    @staticmethod
    def dense_vecs_to_lists(dense_vecs: Any) -> List[List[float]]:
        arr = np.asarray(dense_vecs, dtype=np.float64)
        if arr.ndim == 1:
            return [arr.tolist()]
        return arr.tolist()

    @staticmethod
    def colbert_to_nested_list(colbert_row: Any) -> List[List[float]]:
        """Одна последовательность токенов ColBERT → список векторов для Qdrant multivector."""
        if colbert_row is None:
            return []
        arr = np.asarray(colbert_row, dtype=np.float64)
        if arr.ndim == 1:
            return [arr.tolist()]
        if arr.ndim == 2:
            return arr.tolist()
        raise ValueError(f"Неожиданная размерность colbert_vecs: {arr.shape}")

    @staticmethod
    def colbert_token_dim(colbert_row: Any) -> int:
        arr = np.asarray(colbert_row, dtype=np.float64)
        if arr.ndim == 2:
            return int(arr.shape[1])
        if arr.ndim == 1:
            return int(arr.shape[0])
        raise ValueError(f"Неожиданная размерность colbert для измерения dim: {arr.shape}")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        model = self._ensure_model()
        out = model.encode(
            texts,
            batch_size=self.batch_size,
            max_length=self.max_length,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )
        return self.dense_vecs_to_lists(out["dense_vecs"])

    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]

    def encode_batch(
        self,
        texts: List[str],
        *,
        return_sparse: bool = False,
        return_colbert: bool = False,
    ) -> dict[str, Any]:
        """
        Один проход encode для батча: dense всегда; опционально lexical_weights и colbert_vecs.
        Ключи как у BGEM3FlagModel.encode.
        """
        if not texts:
            return {
                "dense_vecs": np.array([]),
                "lexical_weights": None,
                "colbert_vecs": None,
            }
        model = self._ensure_model()
        return model.encode(
            texts,
            batch_size=self.batch_size,
            max_length=self.max_length,
            return_dense=True,
            return_sparse=return_sparse,
            return_colbert_vecs=return_colbert,
        )

    def set_model(self, model_name: str) -> None:
        self.model_name = model_name
        self._model = None

    def get_model(self) -> str:
        return self.model_name


def lexical_weights_to_sparse_parts(
    lw: Optional[dict[Any, Any]],
) -> tuple[list[int], list[float]]:
    """Словарь id_токена → вес (BGE-M3 lexical_weights) → индексы и значения для Qdrant SparseVector."""
    if not lw:
        return [], []
    indices: list[int] = []
    values: list[float] = []
    for k, v in lw.items():
        indices.append(int(k))
        values.append(float(v))
    return indices, values


class EmbedModel(Embeddings):
    """
    Единый эмбеддер: qwen, openai или bge_m3.
    Для bge_m3 см. также BGEM3Embeddings.encode_batch (sparse/ColBERT).
    """

    def __init__(
        self,
        provider: Literal["qwen", "openai", "bge_m3"] = "qwen",
        *,
        api_url: Optional[str] = None,
        model_name: Optional[str] = None,
        openai_model: Optional[str] = None,
        use_fp16: bool = True,
        devices: Optional[List[str]] = None,
        bge_m3_batch_size: int = 12,
        bge_m3_max_length: int = 8192,
    ):
        self.provider = provider
        self._impl: Embeddings = get_embed_model(
            provider,
            api_url=api_url,
            model_name=model_name,
            openai_model=openai_model,
            use_fp16=use_fp16,
            devices=devices,
            bge_m3_batch_size=bge_m3_batch_size,
            bge_m3_max_length=bge_m3_max_length,
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

    def get_bgem3(self) -> Optional[BGEM3Embeddings]:
        """Если provider=bge_m3 — внутренняя реализация BGEM3Embeddings; иначе None."""
        return self._impl if isinstance(self._impl, BGEM3Embeddings) else None


def get_embed_model(
    provider: Literal["qwen", "openai", "bge_m3"] = "qwen",
    *,
    api_url: Optional[str] = None,
    model_name: Optional[str] = None,
    openai_model: Optional[str] = None,
    use_fp16: bool = True,
    devices: Optional[List[str]] = None,
    bge_m3_batch_size: int = 12,
    bge_m3_max_length: int = 8192,
) -> Embeddings:
    """
    Возвращает эмбеддер для выбранного провайдера.

    Args:
        provider: qwen | openai | bge_m3.
        model_name: Для qwen — имя модели на сервере; для bge_m3 — HuggingFace id (по умолчанию BAAI/bge-m3).
        openai_model: Для openai.
        use_fp16, devices, bge_m3_batch_size, bge_m3_max_length: только для bge_m3.
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
    if provider == "bge_m3":
        return BGEM3Embeddings(
            model_name=model_name or DEFAULT_BGE_M3_MODEL,
            use_fp16=use_fp16,
            devices=devices,
            batch_size=bge_m3_batch_size,
            max_length=bge_m3_max_length,
        )
    raise ValueError(f"Неизвестный provider: {provider}")
