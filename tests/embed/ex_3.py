"""
Dense-only проверка (только OpenAI embeddings, без SPLADE).
Запуск: python -m tests.embed.ex_2_dense_only
"""
from ai.vector.vector_store import VectorStore
from ai.vector.embed_model import EmbedModel
from config import settings

DOCUMENTS = [
    "Python — язык программирования с динамической типизацией. Подходит для веб-разработки и машинного обучения.",
    "REST API позволяет обмениваться данными по HTTP. Методы GET, POST, PUT, DELETE описывают операции над ресурсами.",
    "Деплой приложения: соберите Docker-образ, загрузите в registry и запустите контейнер на сервере или в Kubernetes.",
    "Фреймворк FastAPI для Python даёт автоматическую документацию OpenAPI и асинхронную обработку запросов.",
    "Векторная база Qdrant хранит эмбеддинги и поддерживает гибридный поиск по dense и sparse векторам.",
    "Настройка CI/CD: GitHub Actions запускает тесты и деплой при пуше в основную ветку.",
]

QUERY_KEYWORD = "Python и API"
QUERY_SEMANTIC = "как выкатить сервис в прод"

QDRANT_URL = settings.QDRANT_URL
DENSE_MODEL_PROVIDER = settings.DENSE_MODEL_PROVIDER
USE_SPARSE = settings.USE_SPARSE


def main():
    embed = EmbedModel(provider=DENSE_MODEL_PROVIDER)

    store = VectorStore(
        collection_name="rag_docs_dense",
        embed_model=embed,
        qdrant_url=QDRANT_URL,
        use_sparse=USE_SPARSE,  # ключевое: отключаем SPLADE и гибрид
    )

    print("Индексация документов (dense только)...")
    store.add_documents(
        DOCUMENTS,
        payloads=[{"source": f"doc_{i}", "index": i} for i in range(len(DOCUMENTS))],
    )

    long_doc = (
        "Python — язык программирования. "
        "REST API: методы GET, POST. Деплой через Docker и Kubernetes. "
        "FastAPI даёт OpenAPI. Qdrant — гибридный поиск. CI/CD с GitHub Actions."
    )
    store.add_documents(
        [long_doc],
        payloads=[{"filename": "intro.pdf", "file_link": "/files/intro.pdf"}],
        chunk_options={"chunk_size": 80, "chunk_overlap": 20},
    )

    print("Готово.\n")

    for query_name, query in [
        ("По ключевым словам", QUERY_KEYWORD),
        ("Семантический", QUERY_SEMANTIC),
    ]:
        print(f"--- Запрос: «{query}» ({query_name}) ---")

        dense_only = store.search(query, limit=3, mode="dense")
        print("Только dense (OpenAI embeddings):")
        for i, h in enumerate(dense_only, 1):
            text = (h["payload"].get("text") or "")[:80]
            print(f"  {i}. score={h['score']:.4f}  {text}...")

        print()

    docs = store.get_retriever_documents(
        QUERY_SEMANTIC, limit=2, mode="dense", expand_context=True
    )
    print("Топ-2 текста для RAG (dense):")
    for i, d in enumerate(docs, 1):
        print(f"  {i}. {d[:100]}...")


if __name__ == "__main__":
    main()