"""
Консольный чат с RAG-агентом (LangChain create_agent + Qdrant tools + memory).

Что демонстрирует:
- retrieval из Qdrant через tool `retrieve_context`;
- кратковременную память (checkpointer, thread_id);
- долговременную память (Postgres store, tools remember_fact/recall_fact).

Запуск:
  python3 -m tests.embed.ex_5_rag_agent_chat
"""
from __future__ import annotations

from qdrant_client import QdrantClient

from config import settings
from ai.vector.embed_model import EmbedModel
from ai.vector.vector_store import VectorStore
from ai.llm.rag_agent import chat_once, create_rag_agent, init_agent_memory


DOCUMENTS = [
    "Python — язык программирования с динамической типизацией. Подходит для веб-разработки и машинного обучения.",
    "REST API позволяет обмениваться данными по HTTP. Методы GET, POST, PUT, DELETE описывают операции над ресурсами.",
    "Деплой приложения: соберите Docker-образ, загрузите в registry и запустите контейнер на сервере или в Kubernetes.",
    "Фреймворк FastAPI для Python даёт автоматическую документацию OpenAPI и асинхронную обработку запросов.",
    "Векторная база Qdrant хранит эмбеддинги и поддерживает гибридный поиск по dense и sparse векторам.",
    "Настройка CI/CD: GitHub Actions запускает тесты и деплой при пуше в основную ветку.",
]

COLLECTION_NAME = "rag_agent_demo_docs"
WORKSPACE_ID = "demo_workspace_1"
USER_ID = "demo_user_1"
THREAD_ID = "demo_chat_1"


def _sync_postgres_url() -> str:
    """Синхронный URL для PostgresSaver/PostgresStore."""
    return (
        f"postgresql://{settings.DATABASE_USER}:{settings.DATABASE_PASSWORD}@"
        f"{settings.DATABASE_HOST}:{settings.DATABASE_PORT}/{settings.DATABASE_NAME}"
    )


def _recreate_collection() -> None:
    client = QdrantClient(url=settings.QDRANT_URL, timeout=120.0, check_compatibility=False)
    try:
        client.delete_collection(collection_name=COLLECTION_NAME)
    except Exception:
        pass


def prepare_qdrant_docs() -> None:
    _recreate_collection()
    embed_provider = settings.DENSE_MODEL_PROVIDER if settings.DENSE_MODEL_PROVIDER in ("qwen", "openai") else "qwen"
    store = VectorStore(
        collection_name=COLLECTION_NAME,
        embed_model=EmbedModel(provider=embed_provider),  # type: ignore[arg-type]
        qdrant_url=settings.QDRANT_URL,
        use_sparse=settings.USE_SPARSE,
        sparse_model_name=settings.SPARSE_MODEL_NAME,
    )
    store.add_documents(
        texts=DOCUMENTS,
        payloads=[
            {
                "source": f"doc_{i}",
                "workspace_id": WORKSPACE_ID,
            }
            for i in range(len(DOCUMENTS))
        ],
    )


def main() -> None:
    # print("Индексирую тестовые документы в Qdrant...")
    # prepare_qdrant_docs()
    # print("Документы готовы.")

    db_url = _sync_postgres_url()
    with init_agent_memory(db_url) as memory:
        agent = create_rag_agent(
            memory=memory,
            user_id=USER_ID,
            workspace_id=WORKSPACE_ID,
            collection_name=COLLECTION_NAME,
            qdrant_url=settings.QDRANT_URL,
            use_sparse=settings.USE_SPARSE,
        )

        print("\nЧат запущен. Команды:")
        print("- exit: выйти")
        print("- reset_thread: сменить thread_id (очистить short-term контекст)")
        print("- Тест долговременной памяти: 'Запомни, что мой проект на FastAPI' и потом 'Что ты помнишь о проекте?'\n")

        thread_id = THREAD_ID
        while True:
            user_text = input("Вы: ").strip()
            if not user_text:
                continue
            if user_text.lower() in {"exit", "quit", "q", "выход"}:
                print("Завершение.")
                break
            if user_text.lower() == "reset_thread":
                thread_id = thread_id + "_new"
                print(f"Thread переключен: {thread_id}")
                continue

            answer = chat_once(agent, user_text, thread_id=thread_id, user_id=USER_ID)
            print(f"Агент: {answer}\n")


if __name__ == "__main__":
    main()
