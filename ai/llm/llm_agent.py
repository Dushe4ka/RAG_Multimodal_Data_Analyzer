from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from ai.mcp.client.all_tools import get_all_tools
import asyncio

llm = ChatOpenAI(
    model="Qwen3-30B-A3B-Thinking-2507-Q4_K_M.gguf",
    openai_api_key="sk-111111111111111111111111",
    base_url="http://192.168.0.103:8000/v1",
    temperature=0.7,
    max_tokens=2048,
)

async def main():
    tools = await get_all_tools()
    agent = create_agent(
    model=llm,
    tools=tools,
    system_prompt="Ты полезный ИИ ассистент, твоя задача помогать пользователю. RULES: 1) Ответ давай не в MARKDOWN"
    )
    return agent

async def get_response(message):
    agent = await main()
    response = await agent.ainvoke({"messages": [{"role": "user", "content": message}]})
    return response.content

if __name__ == "__main__":
    asyncio.run(get_response("Какая погода в Темрюке?"))