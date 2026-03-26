from langchain_core.messages import HumanMessage
from deepagents import create_deep_agent
from langchain.agents import create_agent
from _update.tools.mcp_tools import get_mcp_tools
from _update.llm.custom_llm import CustomLLM
from fastmcp import Client
import asyncio

# Настройка LLM через CustomLLM (Custom = локальный/OpenAI-совместимый API)
llm = CustomLLM(
    provider="Custom",
    model="/models/Qwen3-30B-A3B-Thinking-2507-Q4_K_M.gguf",
    api_key="sk-111111111111111111111111",
    temperature=0.7,
    max_tokens=2048,
    base_url="http://192.168.0.103:8000/v1",
)

async def main():
    try:
        # Сначала проверим, что LLM работает
        print("Тестируем подключение к LLM...")
        test_result = await llm.ainvoke("Привет! Тест")
        print("LLM работает:", test_result.content[:100] + "...")

        # Затем работаем с инструментами
        tools = await get_mcp_tools()
        print("Список инструментов:", tools)

        agent = create_agent(
            model=llm,
            tools=tools
        )

        message = "Сложи два числа 5 и 7"
        result = await agent.ainvoke({"messages": [message]})
        print("Результат:", result)

    except Exception as e:
        print("Ошибка:", e)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())