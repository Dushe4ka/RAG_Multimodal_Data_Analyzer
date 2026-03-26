"""
Скрипт для проверки гибридного поиска (dense + sparse, RRF) в VectorStore.
Запуск из корня проекта: python -m tests.embed.ex_2
"""
from ai.vector.vector_store import VectorStore
from ai.vector.embed_model import EmbedModel

# Документы: темы про Python, API, деплой — чтобы тестировать и семантику, и точные слова
DOCUMENTS = [
    "Python — язык программирования с динамической типизацией. Подходит для веб-разработки и машинного обучения.",
    "REST API позволяет обмениваться данными по HTTP. Методы GET, POST, PUT, DELETE описывают операции над ресурсами.",
    "Деплой приложения: соберите Docker-образ, загрузите в registry и запустите контейнер на сервере или в Kubernetes.",
    "Фреймворк FastAPI для Python даёт автоматическую документацию OpenAPI и асинхронную обработку запросов.",
    "Векторная база Qdrant хранит эмбеддинги и поддерживает гибридный поиск по dense и sparse векторам.",
    "Настройка CI/CD: GitHub Actions запускает тесты и деплой при пуше в основную ветку.",
]

# Запросы для теста: один с точными словами, один семантический
QUERY_KEYWORD = "Python и API"  # должно подтянуть чанки с словами Python, API
QUERY_SEMANTIC = "как выкатить сервис в прод"  # семантика: деплой, CI/CD


def main():
    embed = EmbedModel(provider="openai")

    store = VectorStore(
        collection_name="rag_docs",
        embed_model=embed,
        qdrant_url="http://localhost:6333",
        use_sparse=True,
        sparse_model_name="prithivida/Splade_PP_en_v1",
    )

    # print("Индексация документов (с payload: source, index)...")
    # store.add_documents(
    #     DOCUMENTS,
    #     payloads=[{"source": f"doc_{i}", "index": i} for i in range(len(DOCUMENTS))],
    # )

    # # Пример с чанкингом и метаданными файла (filename, file_link)
    # long_doc = (
    #     "Python — язык программирования. "
    #     "REST API: методы GET, POST. Деплой через Docker и Kubernetes. "
    #     "FastAPI даёт OpenAPI. Qdrant — гибридный поиск. CI/CD с GitHub Actions."
    # )
    # store.add_documents(
    #     [long_doc],
    #     payloads=[{"filename": "intro.pdf", "file_link": "/files/intro.pdf"}],
    #     chunk_options={"chunk_size": 80, "chunk_overlap": 20},
    # )
    # print("Готово.\n")

    for query_name, query in [("По ключевым словам", QUERY_KEYWORD), ("Семантический", QUERY_SEMANTIC)]:
        print(f"--- Запрос: «{query}» ({query_name}) ---")

        hybrid = store.search(query, limit=3, mode="hybrid")
        dense_only = store.search(query, limit=3, mode="dense")

        print("Гибридный поиск (dense + sparse, RRF):")
        for i, h in enumerate(hybrid, 1):
            text = (h["payload"].get("text") or "")[:80]
            print(f"  {i}. score={h['score']:.4f}  {text}...")

        print("Только dense:")
        for i, h in enumerate(dense_only, 1):
            text = (h["payload"].get("text") or "")[:80]
            print(f"  {i}. score={h['score']:.4f}  {text}...")
        print()

    # Удобный вывод для RAG
    docs = store.get_retriever_documents(QUERY_SEMANTIC, limit=2, mode="hybrid")
    print("Топ-2 текста для RAG (гибрид):")
    for i, d in enumerate(docs, 1):
        print(f"  {i}. {d[:100]}...")


if __name__ == "__main__":
    main()
