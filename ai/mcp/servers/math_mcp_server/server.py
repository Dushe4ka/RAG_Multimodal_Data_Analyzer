# server.py
from datetime import datetime
from fastmcp import FastMCP
from ai.mcp.servers.math_mcp_server.routes.basic_math import setup_basic_math_routes
from ai.mcp.servers.math_mcp_server.routes.prompts import setup_math_prompts
from ai.mcp.servers.math_mcp_server.routes.resources import setup_math_resources
from ai.mcp.servers.math_mcp_server.routes.statistics import setup_statistics_routes
from ai.mcp.servers.math_mcp_server.routes.geometry import setup_geometry_routes


def create_math_server() -> FastMCP:
    """Создать и настроить математический MCP-сервер."""

    server = FastMCP("Mathematical Calculator")

    # Подключаем все модули
    setup_basic_math_routes(server)
    setup_statistics_routes(server)
    setup_geometry_routes(server)
    setup_math_resources(server)
    setup_math_prompts(server)

    # Дополнительные общие инструменты
    @server.tool
    def server_info() -> dict:
        """Информация о математическом сервере."""
        return {
            "name": "Mathematical Calculator &amp; Tutor",
            "version": "1.0.0",
            "description": "Полнофункциональный математический MCP-сервер",
            "capabilities": {
                "tools": [
                    "Базовые вычисления",
                    "Решение квадратных уравнений",
                    "Статистический анализ",
                    "Геометрические вычисления",
                    "Факториалы"
                ],
                "resources": [
                    "Математические формулы",
                    "Константы",
                    "Справка по статистике",
                    "Примеры решений"
                ],
                "prompts": [
                    "Объяснение решений",
                    "Создание задач",
                    "Репетиторство",
                    "Анализ ошибок"
                ]
            },
            "created_at": datetime.now().isoformat()
        }

    return server

# ================================
# ЗАПУСК СЕРВЕРА
# ================================


if __name__ == "__main__":
    math_server = create_math_server()
    math_server.run(transport="http", port=8001, host="0.0.0.0")
