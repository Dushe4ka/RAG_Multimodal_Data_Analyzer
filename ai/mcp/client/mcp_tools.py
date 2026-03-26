# Важные моменты установки
# Важный момент по поводу локальных MCP (транспорт stdio). Для того чтобы
# они работали, часто требуется локальная установка. В случае с
# server-filesystem MCP установка будет иметь следующий вид:
#
# npm install -g @modelcontextprotocol/server-filesystem
# Также, в зависимости от команды, возможно, вам необходимо будет
# установить дополнительный софт. Например, Python с библиотекой uv,
# Node.js последней версии, npm и так далее.


from langchain_mcp_adapters.client import MultiServerMCPClient


async def get_mcp_tools():
    """Получение всех инструментов: ваших + MCP"""
    # Настройка MCP клиента
    mcp_client = MultiServerMCPClient(
        {
            # "filesystem": {
            #     "command": "npx",
            #     "args": ["-y", "@modelcontextprotocol/server-filesystem", "."],
            #     "transport": "stdio",
            # },
            # "context7": {
            #     "transport": "streamable_http",
            #     "url": "https://mcp.context7.com/mcp",
            # },
            "math_calc": {  # 👈 твой локальный MCP-сервер
                "transport": "streamable_http",
                "url": "http://127.0.0.1:8000/mcp",  # лучше использовать 127.0.0.1
            },
        }
    )

    # Получаем MCP инструменты
    mcp_tools = await mcp_client.get_tools()

    # Объединяем ваши инструменты с MCP инструментами
    return mcp_tools
