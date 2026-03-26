from ai.mcp.client.custom_tools import get_custom_tools
from ai.mcp.client.mcp_tools import get_mcp_tools

async def get_all_tools():
    custom_tools = await get_custom_tools()
    mcp_tools = await get_mcp_tools()
    return custom_tools + mcp_tools