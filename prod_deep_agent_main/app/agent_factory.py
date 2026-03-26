from __future__ import annotations

from deepagents import create_deep_agent
from langchain.agents import create_agent as create_lc_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain.chat_models import init_chat_model

from .backend import make_backend
from .memory import AsyncProductionMemory, ProductionMemory
from .settings import Settings
from .subagents import create_subagents

_SYSTEM_PROMPT = """Ты полезный ассистент и главный оркестратор.
                    Если пользователь сообщает устойчивые предпочтения или важные факты о себе/проекте — сохраняй их в долговременную 
                    память как файлы в /memories/ (например /memories/preferences.txt).
                    Для всех остальных запросов используй субагентов которые тебе доступны. 
                    Доступные агенты:
                    - research-agent - для поиска в интернете и сбор информации
                    - custom-filesystem-agent - для всех работ с файловой системой и консолью
                """

_SYSTEM_PROMPT_LANGCHAIN = """Ты полезный ассистент.

Контекст:
- Этот агент создан через langchain.agents.create_agent (не DeepAgents).
- У тебя нет "внутренней" файловой системы DeepAgents. Для работы с реальной файловой системой и консолью используй MCP-инструменты filesystem.

Правила:
- Если пользователь просит показать/прочитать/изменить файлы проекта или выполнить команды — используй MCP filesystem tools.
- Если пользователь сообщает устойчивые предпочтения или важные факты о себе/проекте — сохраняй их в долговременную память как файлы в /memories/ (например /memories/preferences.txt), используя доступные инструменты.
"""

def create_agent(settings: Settings, memory: ProductionMemory, tools=None):
    model = init_chat_model(settings.chat_model)
    middleware = [
        SummarizationMiddleware(
            model=settings.summary_model,
            api_key=settings.openai_api_key,
            trigger=("tokens", settings.summary_trigger_tokens),
            keep=("messages", settings.summary_keep_messages),
        )
    ]
    agent = create_deep_agent(
        model=model,
        store=memory.store,
        backend=make_backend,
        checkpointer=memory.checkpointer,
        middleware=middleware,
        system_prompt=_SYSTEM_PROMPT,
        tools=tools or [],
    )
    return agent


async def create_agent_with_mcp(settings: Settings, memory: ProductionMemory):
    """Создаёт агента с MCP-инструментами (context7, duckduckgo и др.). Синхронная память — для CLI."""
    from .mcp import get_mcp_tools
    mcp_tools = await get_mcp_tools()
    return create_agent(settings, memory, tools=mcp_tools)


async def create_agent_with_mcp_async(settings: Settings, memory: AsyncProductionMemory):
    """Создаёт агента с MCP и асинхронной памятью (для API: ainvoke + async checkpointer/store)."""
    from .mcp import get_mcp_tools
    mcp_tools = await get_mcp_tools()
    model = init_chat_model(settings.chat_model)
    subagents = await create_subagents()
    middleware = [
        SummarizationMiddleware(
            model=settings.summary_model,
            api_key=settings.openai_api_key,
            trigger=("tokens", settings.summary_trigger_tokens),
            keep=("messages", settings.summary_keep_messages),
        )
    ]
    return create_deep_agent(
        model=model,
        store=memory.store,
        backend=make_backend,
        checkpointer=memory.checkpointer,
        middleware=middleware,
        system_prompt=_SYSTEM_PROMPT,
        # tools=mcp_tools,
        subagents=subagents,
    )


async def create_langchain_agent_with_mcp_filesystem_async(settings: Settings, memory: AsyncProductionMemory):
    """LangChain create_agent + async Postgres checkpointer/store + MCP filesystem tools.

    В отличие от create_deep_agent, тут нет встроенной DeepAgents "внутренней ФС":
    операции с реальной файловой системой выполняются MCP-инструментами.
    """
    from .mcp import get_mcp_tools

    filesystem_tools = await get_mcp_tools(server_name="filesystem")
    model = init_chat_model(settings.chat_model)
    middleware = [
        SummarizationMiddleware(
            model=settings.summary_model,
            api_key=settings.openai_api_key,
            trigger=("tokens", settings.summary_trigger_tokens),
            keep=("messages", settings.summary_keep_messages),
        )
    ]
    return create_lc_agent(
        model,
        tools=filesystem_tools,
        system_prompt=_SYSTEM_PROMPT_LANGCHAIN,
        middleware=middleware,
        checkpointer=memory.checkpointer,
        store=memory.store,
    )

