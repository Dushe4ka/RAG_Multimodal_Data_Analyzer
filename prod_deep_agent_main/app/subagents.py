from .mcp import get_mcp_tools
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from deepagents import CompiledSubAgent
from .settings import load_settings

settings = load_settings()

async def create_research_subagent():
    tools = await get_mcp_tools(server_name="duckduckgo")
    return {
        "name": "research-agent",
        "description": "Используется для поиска в интернете различной информации",
        "system_prompt": "Твоя задача найти все данные которые помогут для ответа на вопрос пользователя",
        "tools": tools,
        "model": "openai:gpt-4.1",  # Optional override, defaults to main agent model
    }

# async def create_filesystem_subagent():
#     tools = await get_mcp_tools(server_name="filesystem")
#     return {
#         "name": "filesystem-agent",
#         "description": "Используется для работы с файловой системой",
#         "system_prompt": "Твоя задача работать с файловой системой",
#         "tools": tools,
#         "model": "openai:gpt-4.1",  # Optional override, defaults to main agent model
#     }

# --------------------------
# CUSTOM SUBAGENTS
model = init_chat_model(settings.chat_model)
async def create_custom_filesystem_agent():
    tools = await get_mcp_tools(server_name="filesystem")

    custom_graph =  create_agent(
        model=model,
        tools=tools,
        system_prompt="Ты специалист по работе с файловой системой и консолью можешь выполнять разные действия в консоли",
    )

    custom_subagent = CompiledSubAgent(
        name="custom-filesystem-agent",
        description="Агент специалист для комплексной работы с файловой системой и консолью",
        runnable=custom_graph
    )

    return custom_subagent



# --------------------------

async def create_subagents():
    return [
        await create_research_subagent(),
        await create_custom_filesystem_agent(),
    ]

