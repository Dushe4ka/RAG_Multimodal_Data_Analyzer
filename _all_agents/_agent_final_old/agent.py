# agent.py
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from config import Config
from memory import get_production_memory
from mcp_integration import create_mcp_client, memory_interceptor, AgentContext
from memory_management import trim_context_middleware, get_summarization_middleware
import os

async def create_production_agent():
    config = Config()
    
    # MCP конфигурация (пример)
    mcp_configs = {
        "filesystem": {
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "/workspace"]
        },
        "database": {
            "transport": "http", 
            "url": "http://localhost:8001/mcp",
            "headers": {"Authorization": f"Bearer {os.getenv('DB_TOKEN')}"}
        }
    }
    
    mcp_client = await create_mcp_client(mcp_configs)
    tools = await mcp_client.get_tools()
    
    with get_production_memory(config) as (checkpointer, store):
        agent = create_agent(
            model=init_chat_model(config.MODEL),
            tools=tools,
            checkpointer=checkpointer,
            store=store,
            context_schema=AgentContext,
            middleware=[
                trim_context_middleware,
                get_summarization_middleware(config.MODEL),
                memory_interceptor,  # Наш кастомный интерцептор
            ],
        )
        return agent