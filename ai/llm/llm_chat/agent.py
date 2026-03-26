"""
Рабочий скрипт для работы с LLM в режиме chat с использованием MongoDB 
для хранения истории чата (история чата сохраняется вне скрипта)
"""
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain_core.runnables import RunnableConfig
from ai.llm.llm_model import get_llm_model
from ai.llm.llm_chat.memory_mongo import checkpointer, long_term_store
from ai.llm.llm_chat.memory_mongo import save_user_info, get_user_info

def get_agent(tools: list = None, system_prompt: str = None):
    """Возвращает экземпляр agent для работы с LLM в режиме chat с использованием 
    MongoDB для хранения истории чата (история чата сохраняется вне скрипта).
    Аргументы:
    - tools: list - список инструментов
    - system_prompt: str - системное сообщение для agent
    """
    llm = get_llm_model(provider="openai")
    tools = tools or []
    tools = tools + [save_user_info, get_user_info]

    system_prompt = system_prompt or "Ты полезный ИИ ассистент, твоя задача помогать пользователю. RULES: 1) Ответ давай не в MARKDOWN"
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt,
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
    return agent

def sync_response_agent(agent, message: str, user_id: str, thread_id: str):
    """Возвращает ответ от agent на заданное сообщение.
    Аргументы:
    - agent: экземпляр agent
    - message: str - сообщение для agent
    - user_id: str - id пользователя
    - thread_id: str - id потока (конверсации)
    """
    config: RunnableConfig = {
        "configurable": {
            "thread_id": thread_id,
            "user_id": user_id,
        }
    }
    final_response = agent.invoke({"messages": message}, config)
    return final_response["messages"][-1].content

# if __name__ == "__main__":
#     agent = get_agent()
#     response = sync_response_agent(agent, "Как мне зовут? Чем я занимаюсь?", "228", "6")
#     print(response)