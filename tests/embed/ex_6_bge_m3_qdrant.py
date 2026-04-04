"""
Пример: BGE-M3 (dense + лексический sparse + опционально ColBERT) в VectorStore + Qdrant.

Требования: Qdrant, FlagEmbedding, PyTorch, достаточно RAM/VRAM для BAAI/bge-m3.

Запуск:
  python3 -m tests.embed.ex_6_bge_m3_qdrant

Перед запуском задайте QDRANT_URL в .env (или по умолчанию localhost:6333).
"""
from __future__ import annotations

import sys

from config import settings
from ai.vector.embed_model import EmbedModel
from ai.vector.vector_store import VectorStore


COLLECTION = "bge_m3_demo_collection"


def main() -> None:
    try:
        __import__("FlagEmbedding")
    except ImportError:
        print("Установите FlagEmbedding: pip install FlagEmbedding", file=sys.stderr)
        sys.exit(1)

    texts = [
        "BGE-M3 поддерживает плотный, разреженный и ColBERT поиск.",
        "Qdrant объединяет ветки поиска через RRF.",
    ]

    # dense + sparse (лексика BGE-M3); ColBERT: use_colbert=True (отдельная схема коллекции)
    use_colbert = False
    store = VectorStore(
        collection_name=COLLECTION,
        embed_model=EmbedModel(provider="bge_m3", use_fp16=True),
        qdrant_url=settings.QDRANT_URL,
        use_sparse=True,
        sparse_backend="bgem3",
        use_colbert=use_colbert,
    )

    from qdrant_client import QdrantClient

    client = QdrantClient(url=settings.QDRANT_URL, timeout=120.0, check_compatibility=False)
    try:
        client.delete_collection(collection_name=COLLECTION)
    except Exception:
        pass

    ids = store.add_documents(texts=texts, payloads=[{"i": i} for i in range(len(texts))])
    print("Добавлены точки:", ids)

    hits = store.search("плотный разреженный поиск", limit=2, mode="hybrid")
    for h in hits:
        print("score:", h["score"], "text:", (h["payload"] or {}).get("text", "")[:80])


if __name__ == "__main__":
    main()
