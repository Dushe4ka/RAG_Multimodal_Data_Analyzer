from langchain_mcp_adapters.client import MultiServerMCPClient

client = MultiServerMCPClient(
    {
        "custom":{
            "url":"http://localhost:8005/mcp",
            "transport":"streamable_http",
        },
    }
)

async def get_mcp_tools():
    tools = await client.get_tools()
    return tools