"""
Рабочий скрипт для работы с LLM в режиме chat с использованием MongoDB 
для хранения истории чата (история чата сохраняется вне скрипта)
"""
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.runnables import RunnableConfig
from config import settings
from ai.llm.llm_model import get_llm_model
from ai.llm.llm_chat.memory_mongo import checkpointer, long_term_store
from ai.llm.llm_chat.memory_mongo import save_user_info, get_user_info

# checkpointer = InMemorySaver()

tools = [save_user_info, get_user_info]

llm = get_llm_model(provider="openai")
agent = create_agent(
    model=llm,
    tools=tools,
    middleware=[
        SummarizationMiddleware(
            model=llm,
            trigger=("tokens", 8196),
            keep=("messages", 20)
        )
    ],
    checkpointer=checkpointer,
    store=long_term_store,
)

config: RunnableConfig = {
    "configurable": {
        "thread_id": "1",
        "user_id": "1",
    }
}
# agent.invoke({"messages": "hi, my name is bob"}, config)
# agent.invoke({"messages": "write a short poem about cats"}, config)
# agent.invoke({"messages": "now do the same but for dogs"}, config)
final_response = agent.invoke({"messages": "Как мне зовут? Чем я занимаюсь?"}, config)

final_response["messages"][-1].pretty_print()