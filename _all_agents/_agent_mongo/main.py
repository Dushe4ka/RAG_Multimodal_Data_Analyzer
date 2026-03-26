from deepagents import create_deep_agent
from langchain.agents.middleware import SummarizationMiddleware
from _agent_mongo.mcp import get_mcp_tools
from _agent_mongo.llm_chat import llm
from _agent_mongo.memory_mongo import checkpointer, long_term_store, save_user_info, get_user_info
import asyncio
import uuid

SYSTEM_PROMPT = """Ты дружелюбный ассистент.
                    У тебя есть файловая система с долговременной памятью по путям /memories/.
                    Правила:
                    - Сохраняй длительные предпочтения и настройки пользователя в /memories/user_preferences.txt.
                    - Если пользователь даёт обратную связь "я предпочитаю X" или "всегда делай Y",
                    обновляй /memories/instructions.txt (используя инструменты файловой системы).
                    - В начале новых разговоров, если возможно, читай /memories/instructions.txt и
                    учитывай эти инструкции."""

config = {
    "configurable": {
        "thread_id": "2",
        "user_id": "1",
    }
}

async def main():
    mcp_tools = await get_mcp_tools()
    all_tools = mcp_tools + [save_user_info, get_user_info]

    agent = create_deep_agent(
        model=llm,
        tools=all_tools,    
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

    message = input("Введите сообщение: ")
    while message.lower() != "exit":
        response = await agent.ainvoke(
            {"messages": [{"role": "user", "content": message}]}, 
            config=config
        )
        print(response["messages"][-1].content)
        message = input("Введите сообщение: ")

if __name__ == "__main__":
    asyncio.run(main())