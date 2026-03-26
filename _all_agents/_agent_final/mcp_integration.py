# mcp_integration.py
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.interceptors import MCPToolCallRequest
from langchain.messages import ToolMessage
from langgraph.types import Command
from dataclasses import dataclass

@dataclass
class AgentContext:
    user_id: str
    session_id: str

async def create_mcp_client(mcp_configs: dict) -> MultiServerMCPClient:
    """Создание клиента для нескольких MCP-серверов"""
    return MultiServerMCPClient(mcp_configs)

async def memory_interceptor(request: MCPToolCallRequest, handler):
    """Интерцептор для сохранения результатов в долговременную память"""
    runtime = request.runtime
    result = await handler(request)
    
    # Сохраняем важные результаты в долговременную память
    if request.name in ["save_note", "update_preference"]:
        user_id = runtime.context.user_id
        await runtime.store.aput(
            namespace=("users", user_id, "memories"),
            key=f"{request.name}_{runtime.tool_call_id}",
            value={"tool": request.name, "result": str(result), "timestamp": "now"}
        )
    
    return result