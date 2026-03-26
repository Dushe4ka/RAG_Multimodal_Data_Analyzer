"""
Демо agentic-RAG графа на LangGraph + Qdrant.
Запуск из корня проекта:
  python3 -m tests.embed.ex_4_rag_graph
"""
from __future__ import annotations

from qdrant_client import QdrantClient

from ai.llm.rag_graph.main import invoke_rag
from ai.vector.embed_model import EmbedModel
from ai.vector.vector_store import VectorStore

# Тестовые документы (те же, что в ex_2, чтобы сравнивать поведение)
DOCUMENTS = [
    "Python — язык программирования с динамической типизацией. Подходит для веб-разработки и машинного обучения.",
    "REST API позволяет обмениваться данными по HTTP. Методы GET, POST, PUT, DELETE описывают операции над ресурсами.",
    "Деплой приложения: соберите Docker-образ, загрузите в registry и запустите контейнер на сервере или в Kubernetes.",
    "Фреймворк FastAPI для Python даёт автоматическую документацию OpenAPI и асинхронную обработку запросов.",
    "Векторная база Qdrant хранит эмбеддинги и поддерживает гибридный поиск по dense и sparse векторам.",
    "Настройка CI/CD: GitHub Actions запускает тесты и деплой при пуше в основную ветку.",
]

COLLECTION_NAME = "rag_docs_graph_demo"
QDRANT_URL = "http://localhost:6333"
WORKSPACE_ID = "demo_workspace_1"
THREAD_ID = "demo_thread_1"


def _recreate_collection(collection_name: str, qdrant_url: str) -> None:
    """Пересоздаём коллекцию для чистого прогона демо."""
    client = QdrantClient(url=qdrant_url, timeout=120.0, check_compatibility=False)
    try:
        client.delete_collection(collection_name=collection_name)
    except Exception:
        pass


def prepare_documents() -> None:
    """Индексирует документы в Qdrant с привязкой к workspace_id."""
    _recreate_collection(COLLECTION_NAME, QDRANT_URL)

    embed = EmbedModel(provider="openai")
    store = VectorStore(
        collection_name=COLLECTION_NAME,
        embed_model=embed,
        qdrant_url=QDRANT_URL,
        use_sparse=True,
        sparse_model_name="prithivida/Splade_PP_en_v1",
    )
    store.add_documents(
        texts=DOCUMENTS,
        payloads=[
            {
                "source": f"doc_{i}",
                "workspace_id": WORKSPACE_ID,  # важно: граф фильтрует именно по workspace_id
            }
            for i in range(len(DOCUMENTS))
        ],
    )


def ask_llm(question: str) -> str:
    """Запрашивает ответ у нового agentic-RAG графа."""
    result = invoke_rag(
        question,
        workspace_id=WORKSPACE_ID,
        thread_id=THREAD_ID,
        collection_name=COLLECTION_NAME,
    )
    messages = result.get("messages", [])
    if not messages:
        return "Пустой ответ от графа."
    last = messages[-1]
    content = getattr(last, "content", None)
    return content if isinstance(content, str) else str(last)


def main() -> None:
    print("Подготавливаю документы для RAG-графа...")
    prepare_documents()
    print("Готово. Задавайте вопросы по документам (exit для выхода).\n")

    # Небольшой авто-тест перед интерактивом
    bootstrap_questions = [
        "Как выкатить сервис в прод?",
        "Для чего нужен Qdrant в этой базе знаний?",
    ]
    for q in bootstrap_questions:
        print(f"Вопрос: {q}")
        print(f"Ответ: {ask_llm(q)}\n")

    while True:
        user_q = input("Ваш вопрос: ").strip()
        if not user_q:
            continue
        if user_q.lower() in {"exit", "quit", "q", "выход"}:
            print("Завершение демо.")
            break
        print(f"Ответ: {ask_llm(user_q)}\n")


if __name__ == "__main__":
    main()
