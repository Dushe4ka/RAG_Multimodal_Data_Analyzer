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
    "МОСКВА, 2 апр - РИА Новости. Донбасс уже никогда не будет входить в состав Украины, считает бывший премьер-министр Украины Николай Азаров. Донбасс уже никогда не будет входить в состав Украины. После 12 лет его физического уничтожения со стороны киевского режима, Донбасс никогда не станет на колени перед режимом, который уничтожает памятники советским воинам, который полностью испохабил свою историю, забрал у народа его реальную историю и реальных героев, воспитывает в ненависти и злобе свое молодое поколение, - написал Азаров в своем Telegram-канале.По мнению Азарова, разговоры о Донбассе в составе Украины являются пустыми и нацеленными на сохранение у власти Владимира Зеленского.",
    "МОСКВА, 2 апр — РИА Новости. Президент Владимир Путин и наследный принц Саудовской Аравии Мухаммед бен Сальман Аль Сауд во время телефонного разговора призвали к разрешению конфликта на Ближнем Востоке. С обеих сторон подчеркнута необходимость скорейшего прекращения боевых действий и активизации политико-дипломатических усилий в целях долгосрочного урегулирования конфликта при должном учете законных интересов всех сторон, — рассказали в пресс-службе Кремля.",
    "КАИР, 2 апр - РИА Новости. Иран пока не видит положительных результатов усилий посредников по прекращению войны на Ближнем Востоке, заявил в интервью РИА Новости глава иранской дипломатической миссии в Египте Моджтаба Фердоусипур. Ранее иранский телеканал Press TV сообщал со ссылкой на источник, что Иран отклонил предложение США по завершению конфликта и выдвинул свои пять условий для этого, включая компенсации, гарантии того, что война против Исламской республики не повторится, и международное признание за Тегераном власти над Ормузским проливом. На данный момент мы не видим в этих усилиях положительные результаты по прекращению войны. Я считаю, что США и сионистский противник (Израиль – ред.) по-прежнему не хотят прекращения огня, - сказал Фердоусипур.",
]

COLLECTION_NAME = "rag_agent_demo_docs"
WORKSPACE_ID = "demo_workspace_1"
USER_ID = "demo_user_1"
THREAD_ID = "demo_chat_2"


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
    prov = settings.DENSE_MODEL_PROVIDER
    if prov == "bge_m3":
        embed = EmbedModel(
            provider="bge_m3",
            model_name=settings.BGE_M3_MODEL,
            use_fp16=settings.BGE_M3_USE_FP16,
        )
        sparse_backend = "bgem3" if settings.USE_SPARSE else "fastembed"
        use_colbert = settings.VECTOR_USE_COLBERT
    elif prov == "openai":
        embed = EmbedModel(provider="openai")
        sparse_backend = "fastembed"
        use_colbert = False
    elif prov == "qwen":
        embed = EmbedModel(provider="qwen")
        sparse_backend = "fastembed"
        use_colbert = False
    else:
        embed = EmbedModel(provider="qwen")
        sparse_backend = "fastembed"
        use_colbert = False

    store = VectorStore(
        collection_name=COLLECTION_NAME,
        embed_model=embed,
        qdrant_url=settings.QDRANT_URL,
        use_sparse=settings.USE_SPARSE,
        sparse_model_name=settings.SPARSE_MODEL_NAME,
        sparse_backend=sparse_backend,
        use_colbert=use_colbert,
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
    print("Индексирую тестовые документы в Qdrant...")
    prepare_qdrant_docs()
    print("Документы готовы.")

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
