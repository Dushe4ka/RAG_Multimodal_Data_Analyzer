# agent.py
import os
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model

from _agent_final.config import Config
from _agent_final.memory import ProductionMemory
from _agent_final.mcp_integration import create_mcp_client, memory_interceptor, AgentContext
from _agent_final.memory_management import get_trim_context_middleware, get_summarization_middleware


async def create_production_agent(config: Config, memory: ProductionMemory):
    """Создаёт агента с переданными checkpointer и store.
    memory должен быть получен через init_production_memory(config) при старте приложения."""
    mcp_configs = {
        # "filesystem": {
        #     "transport": "stdio",
        #     "command": "npx",
        #     "args": ["-y", "@modelcontextprotocol/server-filesystem", "/workspace"],
        # },
        "context7": {
            "transport": "streamable_http",
            "url": "https://mcp.context7.com/mcp",
        },
        # "database": {
        #     "transport": "http",
        #     "url": "http://localhost:8001/mcp",
        #     "headers": {"Authorization": f"Bearer {os.getenv('DB_TOKEN')}"},
        # },
    }

    mcp_client = await create_mcp_client(mcp_configs)
    tools = await mcp_client.get_tools()

    agent = create_agent(
        model=init_chat_model(config.MODEL),
        tools=tools,
        checkpointer=memory.checkpointer,
        store=memory.store,
        context_schema=AgentContext,
        middleware=[
            get_trim_context_middleware(config),
            get_summarization_middleware(config),
            memory_interceptor,
        ],
    )
    return agent
