"""
Векторное хранилище на Qdrant с гибридным поиском (dense + sparse, RRF).
Поддержка BGE-M3: лексический sparse и ColBERT (multivector, MaxSim) из той же модели.
Используется для RAG: индексация чанков и поиск по запросу.
Поддерживает чанкинг длинных текстов (LangChain RecursiveCharacterTextSplitter с перекрытием)
и выдачу контекста из соседних чанков (i-1, i, i+1) при поиске для LLM.
"""
from __future__ import annotations

import uuid
from typing import Any, Literal, Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models

from ai.vector.embed_model import BGEM3Embeddings, EmbedModel, lexical_weights_to_sparse_parts

# Имена векторов в коллекции (должны совпадать с create_collection)
DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"
COLBERT_VECTOR_NAME = "colbert"

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
    Векторное хранилище Qdrant: dense через EmbedModel; sparse — fastembed SPLADE или BGE-M3;
    опционально ColBERT (multivector) для late interaction в одном пайплайне с RRF.
    """

    def __init__(
        self,
        collection_name: str,
        embed_model: Optional[EmbedModel] = None,
        qdrant_url: str = "http://localhost:6333",
        dense_vector_size: Optional[int] = None,
        sparse_model_name: str = DEFAULT_SPARSE_MODEL,
        use_sparse: bool = True,
        sparse_backend: Literal["fastembed", "bgem3"] = "fastembed",
        use_colbert: bool = False,
    ):
        """
        Args:
            collection_name: Имя коллекции в Qdrant.
            embed_model: Эмбеддер (Qwen / OpenAI / BGE-M3). Если None — дефолтный EmbedModel().
            qdrant_url: URL Qdrant.
            dense_vector_size: Размерность dense. Если None — по первому embed_query.
            sparse_model_name: Модель fastembed при sparse_backend=\"fastembed\".
            use_sparse: Сохранять и искать по sparse-вектору.
            sparse_backend: \"fastembed\" (SPLADE) или \"bgem3\" (лексические веса BGE-M3).
            use_colbert: Именованный multivector \"colbert\" (MaxSim); только с BGE-M3.

        Важно: при эмбеддере BGE-M3 и use_sparse=True задавайте sparse_backend=\"bgem3\".
        Схема коллекции (в т.ч. ColBERT) задаётся при создании; для другого режима используйте другое имя коллекции.
        """
        self.collection_name = collection_name
        self._embed_model = embed_model or EmbedModel()
        self._client = QdrantClient(
            url=qdrant_url,
            timeout=120.0,
            check_compatibility=False,
        )
        self._dense_vector_size = dense_vector_size
        self._sparse_model_name = sparse_model_name
        self._use_sparse = use_sparse
        self._sparse_backend = sparse_backend
        self._use_colbert = use_colbert
        self._colbert_token_dim: Optional[int] = None

        self._validate_embed_backend()

        self._sparse_model: Any = None
        if use_sparse and sparse_backend == "fastembed":
            try:
                from fastembed import SparseTextEmbedding
                self._sparse_model = SparseTextEmbedding(model_name=sparse_model_name)
            except ImportError as e:
                raise ImportError(
                    "Для sparse_backend='fastembed' нужен fastembed: pip install fastembed"
                ) from e

    def _get_bgem3(self) -> Optional[BGEM3Embeddings]:
        getter = getattr(self._embed_model, "get_bgem3", None)
        if callable(getter):
            return getter()
        return None

    def _validate_embed_backend(self) -> None:
        bg = self._get_bgem3()
        if self._use_colbert and bg is None:
            raise ValueError(
                "use_colbert=True требует EmbedModel(provider='bge_m3') (BGEM3Embeddings)."
            )
        if self._use_sparse and self._sparse_backend == "bgem3" and bg is None:
            raise ValueError(
                "sparse_backend='bgem3' требует EmbedModel(provider='bge_m3')."
            )
        if bg is not None and self._use_sparse and self._sparse_backend == "fastembed":
            raise ValueError(
                "При эмбеддере BGE-M3 и use_sparse=True укажите sparse_backend='bgem3' "
                "(лексические веса той же модели), а не fastembed SPLADE."
            )
        if self._use_colbert and self._use_sparse and self._sparse_backend != "bgem3":
            raise ValueError(
                "use_colbert=True с use_sparse=True предполагает sparse_backend='bgem3'."
            )

    def _needs_bge_m3_batch_encode(self) -> bool:
        m = self._get_bgem3()
        if m is None:
            return False
        if self._use_colbert:
            return True
        if self._use_sparse and self._sparse_backend == "bgem3":
            return True
        return False

    def _get_dense_size(self) -> int:
        if self._dense_vector_size is not None:
            return self._dense_vector_size
        vec = self._embed_model.embed_query(".")
        self._dense_vector_size = len(vec)
        return self._dense_vector_size

    def _get_colbert_token_dim(self) -> int:
        if self._colbert_token_dim is not None:
            return self._colbert_token_dim
        m = self._get_bgem3()
        if m is None:
            raise RuntimeError("ColBERT недоступен без BGE-M3.")
        out = m.encode_batch(["."], return_sparse=False, return_colbert=True)
        row = out["colbert_vecs"][0]
        self._colbert_token_dim = BGEM3Embeddings.colbert_token_dim(row)
        return self._colbert_token_dim

    def _colbert_vector_params(self, size: int) -> models.VectorParams:
        return models.VectorParams(
            size=size,
            distance=models.Distance.COSINE,
            multivector_config=models.MultiVectorConfig(
                comparator=models.MultiVectorComparator.MAX_SIM
            ),
            hnsw_config=models.HnswConfigDiff(m=0),
        )

    def _ensure_collection(self) -> None:
        """Создаёт коллекцию с dense [, sparse] [, colbert multivector], если её ещё нет."""
        try:
            self._client.get_collection(self.collection_name)
            return
        except Exception:
            pass

        dense_size = self._get_dense_size()
        vectors_config: dict[str, models.VectorParams] = {
            DENSE_VECTOR_NAME: models.VectorParams(
                size=dense_size,
                distance=models.Distance.COSINE,
            ),
        }
        if self._use_colbert:
            vectors_config[COLBERT_VECTOR_NAME] = self._colbert_vector_params(
                self._get_colbert_token_dim()
            )

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
        if not self._use_sparse:
            return []
        if self._sparse_backend == "fastembed":
            if self._sparse_model is None:
                return []
            embeddings = list(self._sparse_model.embed(texts))
            return [_sparse_embedding_to_vector(e) for e in embeddings]
        m = self._get_bgem3()
        if m is None:
            return []
        out = m.encode_batch(texts, return_sparse=True, return_colbert=False)
        result: list[models.SparseVector] = []
        for lw in out["lexical_weights"]:
            idx, vals = lexical_weights_to_sparse_parts(lw)
            result.append(models.SparseVector(indices=idx, values=vals))
        return result

    def _embed_colbert_query(self, query: str) -> list[list[float]]:
        m = self._get_bgem3()
        if m is None or not query.strip():
            return []
        out = m.encode_batch([query], return_sparse=False, return_colbert=True)
        return BGEM3Embeddings.colbert_to_nested_list(out["colbert_vecs"][0])

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
        Добавляет документы: чанкинг опционально; dense + sparse (если включено) + ColBERT (если включено).
        """
        self._ensure_collection()

        if payloads is None:
            payloads = [{} for _ in texts]
        elif len(payloads) != len(texts):
            raise ValueError(f"len(payloads)={len(payloads)} должен равняться len(texts)={len(texts)}")

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

            if self._needs_bge_m3_batch_encode():
                m = self._get_bgem3()
                assert m is not None
                out = m.encode_batch(
                    batch_texts,
                    return_sparse=self._use_sparse and self._sparse_backend == "bgem3",
                    return_colbert=self._use_colbert,
                )
                dense_vectors = BGEM3Embeddings.dense_vecs_to_lists(out["dense_vecs"])
                sparse_vectors: list[models.SparseVector] = []
                if self._use_sparse and self._sparse_backend == "bgem3":
                    for lw in out["lexical_weights"]:
                        idx, vals = lexical_weights_to_sparse_parts(lw)
                        sparse_vectors.append(models.SparseVector(indices=idx, values=vals))
                colbert_rows: list[list[list[float]]] = []
                if self._use_colbert:
                    for row in out["colbert_vecs"]:
                        colbert_rows.append(BGEM3Embeddings.colbert_to_nested_list(row))
            else:
                dense_vectors = self._embed_dense(batch_texts)
                sparse_vectors = self._embed_sparse(batch_texts) if self._use_sparse else []
                colbert_rows = []

            points = []
            for j, (tid, pl) in enumerate(zip(batch_ids, batch_payloads)):
                vector: dict[str, Any] = {DENSE_VECTOR_NAME: dense_vectors[j]}
                if sparse_vectors:
                    vector[SPARSE_VECTOR_NAME] = sparse_vectors[j]
                if self._use_colbert and colbert_rows:
                    vector[COLBERT_VECTOR_NAME] = colbert_rows[j]
                points.append(models.PointStruct(id=tid, vector=vector, payload=pl))
            self._client.upsert(
                collection_name=self.collection_name,
                points=points,
                wait=wait,
            )
            result_ids.extend(batch_ids)
        return result_ids

    def _get_chunk_context(self, document_id: str, chunk_index: int) -> str:
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
        """RRF по одному или нескольким prefetch: dense, sparse, colbert."""
        prefetch_limit = prefetch_limit or max(limit * 2, 20)

        dense_q = self._embed_model.embed_query(query)
        prefetches: list[models.Prefetch] = [
            models.Prefetch(
                query=dense_q,
                using=DENSE_VECTOR_NAME,
                limit=prefetch_limit,
            ),
        ]

        if self._use_sparse:
            sparse_vectors = self._embed_sparse([query])
            sparse_q = sparse_vectors[0] if sparse_vectors else None
            if sparse_q is not None and (sparse_q.indices or sparse_q.values):
                prefetches.append(
                    models.Prefetch(
                        query=sparse_q,
                        using=SPARSE_VECTOR_NAME,
                        limit=prefetch_limit,
                    ),
                )

        if self._use_colbert:
            colbert_q = self._embed_colbert_query(query)
            if colbert_q:
                prefetches.append(
                    models.Prefetch(
                        query=colbert_q,
                        using=COLBERT_VECTOR_NAME,
                        limit=prefetch_limit,
                    ),
                )

        if len(prefetches) == 1:
            response = self._client.query_points(
                collection_name=self.collection_name,
                query=dense_q,
                using=DENSE_VECTOR_NAME,
                limit=limit,
                query_filter=query_filter,
            )
            return response.points

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
        q = self._embed_model.embed_query(query)
        response = self._client.query_points(
            collection_name=self.collection_name,
            query=q,
            using=DENSE_VECTOR_NAME,
            limit=limit,
            query_filter=query_filter,
        )
        return response.points

    def _wants_hybrid_rrf(self) -> bool:
        if self._use_sparse:
            return True
        if self._use_colbert:
            return True
        return False

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
        mode=\"hybrid\": RRF по всем включённым веткам (dense + sparse + colbert).
        mode=\"dense\": только dense.
        """
        if mode == "dense":
            points = self._dense_only_search(query, limit=limit, query_filter=query_filter)
        elif self._wants_hybrid_rrf():
            points = self._hybrid_search_prefetch(
                query,
                limit=limit,
                prefetch_limit=prefetch_limit,
                query_filter=query_filter,
                rrf_k=rrf_k,
            )
        else:
            points = self._dense_only_search(query, limit=limit, query_filter=query_filter)

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
