from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
from langgraph.store.memory import InMemoryStore
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver  
from langchain.agents.middleware import SummarizationMiddleware
from langchain_core.runnables import RunnableConfig
import uuid
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://developer:12357985@localhost:5432/mydb")

config1 = {"configurable": {"thread_id": str(uuid.uuid4())}}
config2 = {"configurable": {"thread_id": str(uuid.uuid4())}}

checkpointer = MemorySaver()

def make_backend(runtime):
    return CompositeBackend(
        default=StateBackend(runtime),  # Ephemeral storage
        routes={
            "/memories/": StoreBackend(runtime)  # Persistent storage
        }
    )

agent = create_deep_agent(
    store=InMemoryStore(),  # Good for local dev; omit for LangSmith Deployment
    backend=make_backend,
    checkpointer=checkpointer
)

agent.invoke({
    "messages": [{"role": "user", "content": "Save my preferences to /memories/preferences.txt"}]
}, config=config1)

agent.invoke({
    "messages": [{"role": "user", "content": "What are my preferences?"}]
}, config=config2)

# ----------------
# Пользовательские настройки
# Сохранить пользовательские настройки, которые 
# будут действовать в течение всего сеанса:
# ----------------

agent = create_deep_agent(
    store=InMemoryStore(),
    backend=lambda rt: CompositeBackend(
        default=StateBackend(rt),
        routes={"/memories/": StoreBackend(rt)}
    ),
    system_prompt="""When users tell you their preferences, save them to
    /memories/user_preferences.txt so you remember them in future conversations."""
)

# ----------------
# Инструкции по самосовершенствованию
# Агент может обновлять свои инструкции на основе полученных отзывов:
# ----------------

agent = create_deep_agent(
    store=InMemoryStore(),
    backend=lambda rt: CompositeBackend(
        default=StateBackend(rt),
        routes={"/memories/": StoreBackend(rt)}
    ),
    system_prompt="""You have a file at /memories/instructions.txt with additional
    instructions and preferences.

    Read this file at the start of conversations to understand user preferences.

    When users provide feedback like "please always do X" or "I prefer Y",
    update /memories/instructions.txt using the edit_file tool."""
)

# ----------------
# Исследовательские проекты
# Сохраняйте состояние исследования между сессиями:
# ----------------

research_agent = create_deep_agent(
    store=InMemoryStore(),
    backend=lambda rt: CompositeBackend(
        default=StateBackend(rt),
        routes={"/memories/": StoreBackend(rt)}
    ),
    system_prompt="""You are a research assistant.

    Save your research progress to /memories/research/:
    - /memories/research/sources.txt - List of sources found
    - /memories/research/notes.txt - Key findings and notes
    - /memories/research/report.md - Final report draft

    This allows research to continue across multiple sessions."""
)

# ----------------
# InMemoryStore (разработка)
# Подходит для тестирования и разработки, но при перезапуске данные теряются:
# ----------------

from langgraph.store.memory import InMemoryStore

store = InMemoryStore()
agent = create_deep_agent(
    store=store,
    backend=lambda rt: CompositeBackend(
        default=StateBackend(rt),
        routes={"/memories/": StoreBackend(rt)}
    )
)

# ----------------
# PostgresStore (для продакшена)
# Для продакшена используйте постоянное хранилище:
# ----------------

from langgraph.store.postgres import PostgresStore
import os

# Use PostgresStore.from_conn_string as a context manager
store_ctx = PostgresStore.from_conn_string(os.environ["DATABASE_URL"])
store = store_ctx.__enter__()
store.setup()

agent = create_deep_agent(
    store=store,
    backend=lambda rt: CompositeBackend(
        default=StateBackend(rt),
        routes={"/memories/": StoreBackend(rt)}
    )
)

# ----------------
# PostgresStore & PostgresSaver (для продакшена)
# ----------------

checkpointer_prod = PostgresSaver.from_conn_string(DATABASE_URL)
store_ctx = PostgresStore.from_conn_string(os.environ["DATABASE_URL"])
store_prod = store_ctx.__enter__()
store_prod.setup()

agent = create_deep_agent(
    store=store,
    backend=lambda rt: CompositeBackend(
        default=StateBackend(rt),
        routes={"/memories/": StoreBackend(rt)}
    ),
    checkpointer=checkpointer_prod,
    middleware=[
        SummarizationMiddleware(
            model="gpt-4.1-mini",
            trigger=("tokens", 4000),
            keep=("messages", 20)
        )
    ],
)

config: RunnableConfig = {"configurable": {"thread_id": "1", "user_id":"1"}}
final_response = agent.invoke({"messages": "hi, my name is bob"}, config)
final_response["messages"][-1].pretty_print()