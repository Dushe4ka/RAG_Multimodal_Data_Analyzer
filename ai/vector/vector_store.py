"""
Векторное хранилище на Qdrant с гибридным поиском (dense + sparse, RRF).
Используется для RAG: индексация чанков и поиск по запросу.
Поддерживает чанкинг длинных текстов (LangChain RecursiveCharacterTextSplitter с перекрытием)
и выдачу контекста из соседних чанков (i-1, i, i+1) при поиске для LLM.
"""
from __future__ import annotations

import uuid
from typing import Any, Literal, Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models

from ai.vector.embed_model import EmbedModel

# Имена векторов в коллекции (должны совпадать с create_collection)
DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"

# Ключи в payload: текст чанка, id документа, индекс чанка (для контекста i±1)
PAYLOAD_TEXT = "text"
PAYLOAD_DOCUMENT_ID = "document_id"
PAYLOAD_CHUNK_INDEX = "chunk_index"

# Дефолтная SPLADE-модель для sparse (fastembed; имя из list_supported_models())
DEFAULT_SPARSE_MODEL = "prithivida/Splade_PP_en_v1"

# Дефолты чанкинга (LangChain RecursiveCharacterTextSplitter)
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 200


def _sparse_embedding_to_vector(embedding: Any) -> models.SparseVector:
    """Преобразует результат fastembed SparseTextEmbedding в Qdrant SparseVector."""
    indices = embedding.indices.tolist() if hasattr(embedding.indices, "tolist") else list(embedding.indices)
    values = embedding.values.tolist() if hasattr(embedding.values, "tolist") else list(embedding.values)
    return models.SparseVector(indices=indices, values=values)


def _get_text_splitter(chunk_size: int, chunk_overlap: int) -> Any:
    """Возвращает RecursiveCharacterTextSplitter из LangChain (с перекрытием чанков)."""
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
    except ImportError:
        from langchain_classic.text_splitter import RecursiveCharacterTextSplitter
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )


class VectorStore:
    """
    Векторное хранилище Qdrant с поддержкой гибридного поиска (dense + sparse, RRF).
    Dense-векторы — через переданный EmbedModel, sparse — через fastembed SPLADE.
    """

    def __init__(
        self,
        collection_name: str,
        embed_model: Optional[EmbedModel] = None,
        qdrant_url: str = "http://localhost:6333",
        dense_vector_size: Optional[int] = None,
        sparse_model_name: str = DEFAULT_SPARSE_MODEL,
        use_sparse: bool = True,
    ):
        """
        Args:
            collection_name: Имя коллекции в Qdrant.
            embed_model: Эмбеддер для dense-векторов (Qwen/OpenAI). Если None — создаётся дефолтный EmbedModel.
            qdrant_url: URL Qdrant.
            dense_vector_size: Размерность dense-вектора. Если None — определяется по первому embed.
            sparse_model_name: Модель fastembed для sparse (SPLADE).
            use_sparse: Включить sparse-векторы и гибридный поиск. Если False — только dense.
        """
        self.collection_name = collection_name
        self._embed_model = embed_model or EmbedModel()
        self._client = QdrantClient(
            url=qdrant_url,
            timeout=120.0,  # секунд; подберите под диск/нагрузку (60–300)
            check_compatibility=False,  # опционально, только чтобы убрать warning
        )
        self._dense_vector_size = dense_vector_size
        self._sparse_model_name = sparse_model_name
        self._use_sparse = use_sparse

        self._sparse_model: Any = None
        if use_sparse:
            try:
                from fastembed import SparseTextEmbedding
                self._sparse_model = SparseTextEmbedding(model_name=sparse_model_name)
            except ImportError:
                raise ImportError(
                    "Для гибридного поиска нужен fastembed: pip install fastembed"
                )

    def _get_dense_size(self) -> int:
        if self._dense_vector_size is not None:
            return self._dense_vector_size
        vec = self._embed_model.embed_query(".")
        self._dense_vector_size = len(vec)
        return self._dense_vector_size

    def _ensure_collection(self) -> None:
        """Создаёт коллекцию с named vectors dense и sparse, если её ещё нет."""
        try:
            self._client.get_collection(self.collection_name)
            return
        except Exception:
            pass

        dense_size = self._get_dense_size()
        vectors_config = {
            DENSE_VECTOR_NAME: models.VectorParams(
                size=dense_size,
                distance=models.Distance.COSINE,
            ),
        }
        sparse_vectors_config = None
        if self._use_sparse:
            sparse_vectors_config = {
                SPARSE_VECTOR_NAME: models.SparseVectorParams(),
            }

        self._client.create_collection(
            collection_name=self.collection_name,
            vectors_config=vectors_config,
            sparse_vectors_config=sparse_vectors_config,
        )

    def _embed_dense(self, texts: list[str]) -> list[list[float]]:
        return self._embed_model.embed_documents(texts)

    def _embed_sparse(self, texts: list[str]) -> list[models.SparseVector]:
        if not self._use_sparse or self._sparse_model is None:
            return []
        embeddings = list(self._sparse_model.embed(texts))
        return [_sparse_embedding_to_vector(e) for e in embeddings]

    def add_documents(
        self,
        texts: list[str],
        payloads: Optional[list[dict[str, Any]]] = None,
        ids: Optional[list[str | int]] = None,
        batch_size: int = 32,
        chunk_options: Optional[dict[str, Any]] = None,
        wait: bool = True,
    ) -> list[str | int]:
        """
        Добавляет документы в коллекцию: при необходимости чанкует длинные тексты,
        считает dense- и sparse-векторы по каждому чанку и делает upsert.

        Что происходит по шагам:
        1. Проверка коллекции (создание при отсутствии).
        2. Нормализация payloads: если не переданы — для каждого документа свой пустой dict
           (не одна ссылка на общий dict). Если переданы — проверка длины.
        3. Опциональный чанкинг: если передан chunk_options, длинные тексты режутся через
           RecursiveCharacterTextSplitter (chunk_size, chunk_overlap). У каждого чанка в payload
           сохраняются document_id (общий для документа), chunk_index (порядок 0,1,2,...) и все
           поля из payload документа (например filename, file_link). Id точки — UUID (Qdrant принимает только int или UUID).
        4. Батчами: эмбеддинг dense и sparse по текстам чанков, сборка PointStruct (vector + payload),
           upsert в Qdrant с wait=True/False.

        Args:
            texts: Список текстов документов (каждый может быть длинным).
            payloads: Метаданные по одному на документ: filename, file_link и т.д. Длина = len(texts).
            ids: Id документов (используются только без чанкинга). Если не переданы — генерируются UUID.
            batch_size: Размер батча для эмбеддинга и upsert.
            chunk_options: Включить чанкинг. None — не чанковать (один текст = одна точка).
                dict с ключами: chunk_size (int, по умолчанию 1000), chunk_overlap (int, 200).
            wait: Ждать применения upsert в Qdrant перед возвратом.

        Returns:
            Список id добавленных точек (при чанкинге — UUID каждого чанка).
        """
        self._ensure_collection()

        # Корректная инициализация payloads: отдельный dict на каждый документ
        if payloads is None:
            payloads = [{} for _ in texts]
        elif len(payloads) != len(texts):
            raise ValueError(f"len(payloads)={len(payloads)} должен равняться len(texts)={len(texts)}")

        # Строим плоский список (chunk_text, payload, point_id) — либо 1:1 с documents, либо по чанкам
        if chunk_options is not None:
            chunk_size = chunk_options.get("chunk_size", DEFAULT_CHUNK_SIZE)
            chunk_overlap = chunk_options.get("chunk_overlap", DEFAULT_CHUNK_OVERLAP)
            splitter = _get_text_splitter(chunk_size, chunk_overlap)
            flat_texts: list[str] = []
            flat_payloads: list[dict[str, Any]] = []
            flat_ids: list[str] = []
            for text, doc_payload in zip(texts, payloads):
                document_id = uuid.uuid4().hex
                chunks = splitter.split_text(text.strip()) if text.strip() else [""]
                for chunk_index, chunk_text in enumerate(chunks):
                    flat_texts.append(chunk_text)
                    flat_payloads.append({
                        PAYLOAD_TEXT: chunk_text,
                        PAYLOAD_DOCUMENT_ID: document_id,
                        PAYLOAD_CHUNK_INDEX: chunk_index,
                        **doc_payload,
                    })
                    # Qdrant принимает только int или UUID; document_id и chunk_index уже в payload
                    flat_ids.append(uuid.uuid4().hex)
        else:
            if ids is not None and len(ids) != len(texts):
                raise ValueError(f"len(ids)={len(ids)} должен равняться len(texts)={len(texts)}")
            flat_texts = list(texts)
            flat_payloads = [{"text": t, **p} for t, p in zip(texts, payloads)]
            flat_ids = list(ids) if ids is not None else [uuid.uuid4().hex for _ in texts]

        result_ids: list[str | int] = []
        for i in range(0, len(flat_texts), batch_size):
            batch_texts = flat_texts[i : i + batch_size]
            batch_payloads = flat_payloads[i : i + batch_size]
            batch_ids = flat_ids[i : i + batch_size]

            dense_vectors = self._embed_dense(batch_texts)
            sparse_vectors = self._embed_sparse(batch_texts) if self._use_sparse else []

            points = []
            for j, (tid, pl) in enumerate(zip(batch_ids, batch_payloads)):
                vector: dict[str, Any] = {DENSE_VECTOR_NAME: dense_vectors[j]}
                if sparse_vectors:
                    vector[SPARSE_VECTOR_NAME] = sparse_vectors[j]
                points.append(models.PointStruct(id=tid, vector=vector, payload=pl))
            self._client.upsert(
                collection_name=self.collection_name,
                points=points,
                wait=wait,
            )
            result_ids.extend(batch_ids)
        return result_ids

    def _get_chunk_context(self, document_id: str, chunk_index: int) -> str:
        """
        Возвращает склеенный текст чанков (chunk_index-1, chunk_index, chunk_index+1)
        для полного контекста при передаче в LLM. Границы документа учитываются.
        """
        scroll_filter = models.Filter(
            must=[
                models.FieldCondition(key=PAYLOAD_DOCUMENT_ID, match=models.MatchValue(value=document_id)),
                models.FieldCondition(
                    key=PAYLOAD_CHUNK_INDEX,
                    range=models.Range(gte=chunk_index - 1, lte=chunk_index + 1),
                ),
            ]
        )
        result, _ = self._client.scroll(
            collection_name=self.collection_name,
            scroll_filter=scroll_filter,
            limit=10,
            with_payload=True,
            with_vectors=False,
        )
        if not result:
            return ""
        # Сортируем по chunk_index и склеиваем text
        sorted_points = sorted(result, key=lambda p: (p.payload or {}).get(PAYLOAD_CHUNK_INDEX, 0))
        return "\n\n".join((p.payload or {}).get(PAYLOAD_TEXT, "") for p in sorted_points).strip()

    def _hybrid_search_prefetch(
        self,
        query: str,
        limit: int = 10,
        prefetch_limit: Optional[int] = None,
        query_filter: Optional[models.Filter] = None,
        rrf_k: Optional[int] = None,
    ) -> list[models.ScoredPoint]:
        """Гибридный поиск: два prefetch (dense + sparse) и RRF."""
        prefetch_limit = prefetch_limit or max(limit * 2, 20)

        dense_q = self._embed_model.embed_query(query)
        sparse_vectors = self._embed_sparse([query])
        sparse_q = sparse_vectors[0] if sparse_vectors else None

        prefetches = [
            models.Prefetch(
                query=dense_q,
                using=DENSE_VECTOR_NAME,
                limit=prefetch_limit,
            ),
        ]
        if sparse_q is not None:
            prefetches.append(
                models.Prefetch(
                    query=sparse_q,
                    using=SPARSE_VECTOR_NAME,
                    limit=prefetch_limit,
                ),
            )

        if rrf_k is not None:
            query_obj = models.RrfQuery(rrf=models.Rrf(k=rrf_k))
        else:
            query_obj = models.FusionQuery(fusion=models.Fusion.RRF)

        response = self._client.query_points(
            collection_name=self.collection_name,
            prefetch=prefetches,
            query=query_obj,
            limit=limit,
            query_filter=query_filter,
        )
        return response.points

    def _dense_only_search(
        self,
        query: str,
        limit: int = 10,
        query_filter: Optional[models.Filter] = None,
    ) -> list[models.ScoredPoint]:
        """Только семантический (dense) поиск."""
        q = self._embed_model.embed_query(query)
        response = self._client.query_points(
            collection_name=self.collection_name,
            query=q,
            using=DENSE_VECTOR_NAME,
            limit=limit,
            query_filter=query_filter,
        )
        return response.points

    def search(
        self,
        query: str,
        limit: int = 10,
        mode: Literal["hybrid", "dense"] = "hybrid",
        prefetch_limit: Optional[int] = None,
        query_filter: Optional[models.Filter] = None,
        rrf_k: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """
        Поиск по текстовому запросу.

        Args:
            query: Текст запроса.
            limit: Сколько документов вернуть.
            mode: "hybrid" — dense + sparse с RRF; "dense" — только dense.
            prefetch_limit: Лимит для каждого prefetch (для hybrid). Должен быть >= limit.
            query_filter: Фильтр Qdrant по payload.
            rrf_k: Константа k для RRF (по умолчанию 2). Только для mode=hybrid.

        Returns:
            Список dict с ключами payload (в т.ч. "text"), score, id.
        """
        if mode == "dense" or not self._use_sparse:
            points = self._dense_only_search(query, limit=limit, query_filter=query_filter)
        else:
            points = self._hybrid_search_prefetch(
                query,
                limit=limit,
                prefetch_limit=prefetch_limit,
                query_filter=query_filter,
                rrf_k=rrf_k,
            )

        return [
            {
                "id": p.id,
                "score": p.score,
                "payload": p.payload or {},
            }
            for p in points
        ]

    def get_retriever_documents(
        self,
        query: str,
        limit: int = 10,
        mode: Literal["hybrid", "dense"] = "hybrid",
        expand_context: bool = True,
    ) -> list[str]:
        """
        Удобный метод для RAG: возвращает список текстов для подстановки в LLM.

        Если expand_context=True и в payload точки есть document_id и chunk_index
        (значит документ был заиндексирован с чанкингом), для каждого хита подставляется
        контекст из трёх чанков (i-1, i, i+1), склеенных вместе. Иначе возвращается
        только payload["text"] найденной точки.
        """
        hits = self.search(query=query, limit=limit, mode=mode)
        out: list[str] = []
        for h in hits:
            pl = h["payload"] or {}
            doc_id = pl.get(PAYLOAD_DOCUMENT_ID)
            idx = pl.get(PAYLOAD_CHUNK_INDEX)
            if expand_context and doc_id is not None and idx is not None:
                out.append(self._get_chunk_context(doc_id, idx))
            else:
                out.append(pl.get(PAYLOAD_TEXT, pl.get("text", "")))
        return out
