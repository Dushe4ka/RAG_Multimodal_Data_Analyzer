from langchain_core.tools import tool
from typing import Optional

@tool
def get_weather(city: str, unit: Optional[str] = "celsius") -> str:
    """Получает текущую погоду для города"""
    # В реальном приложении — вызов API погоды
    return f"В {city} сейчас +22°C, солнечно"

tools = [get_weather]