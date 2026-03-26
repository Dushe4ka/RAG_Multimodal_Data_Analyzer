"""MCP-инструменты для агента (по образцу _agent_mongo/mcp.py)."""
from __future__ import annotations

from langchain_mcp_adapters.client import MultiServerMCPClient


async def get_mcp_tools(server_name: str | None = None):
    """Получение всех MCP-инструментов для агента."""
    mcp_client = MultiServerMCPClient(
        {
            # "context7": {
            #     "transport": "streamable_http",
            #     "url": "https://mcp.context7.com/mcp",
            # },
            "duckduckgo": {
                "command": "npx",
                "args": ["-y", "duckduckgo-mcp-server"],
                "transport": "stdio",
            },
            "filesystem": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "."],
                "transport": "stdio",
            },
        }
    )
    return await mcp_client.get_tools(server_name=server_name)
