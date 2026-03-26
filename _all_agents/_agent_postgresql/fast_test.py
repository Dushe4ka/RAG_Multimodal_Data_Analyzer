from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
from langgraph.store.memory import InMemoryStore
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver  
from langchain.agents.middleware import SummarizationMiddleware
from langchain_core.runnables import RunnableConfig
from langgraph.store.postgres import PostgresStore
from _agent_postgresql.llm_chat import llm
import uuid
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://developer:12357985@localhost:5432/mydb")

SYSTEM_PROMPT = "Для запоминания информации важной о пользователя сохраняй в store"

with PostgresSaver.from_conn_string(DATABASE_URL) as checkpointer_prod:
    checkpointer_prod.setup()  # создание таблиц при первом запуске
    store_ctx = PostgresStore.from_conn_string(DATABASE_URL)
    store_prod = store_ctx.__enter__()
    store_prod.setup()

    agent = create_deep_agent(
        store=store_prod,
        model=llm,
        backend=lambda rt: CompositeBackend(
            default=StateBackend(rt),
            routes={"/memories/": StoreBackend(rt)}
        ),
        checkpointer=checkpointer_prod,
        middleware=[
            SummarizationMiddleware(
                model="gpt-4.1-mini",
                api_key=os.getenv("OPENAI_API_KEY"),
                trigger=("tokens", 4000),
                keep=("messages", 20)
            )
        ],
    )

    config: RunnableConfig = {"configurable": {"thread_id": "1", "user_id":"1"}}
    final_response = agent.invoke({"messages": "hi, my name is bob"}, config)
    final_response["messages"][-1].pretty_print()