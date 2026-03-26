# usage.py
from langchain_core.messages import HumanMessage

from _agent_final.mcp_integration import AgentContext


async def run_with_rollback_support(
    agent, user_input: str, thread_id: str, context: AgentContext
):
    """Запуск агента с возможностью отката к предыдущим состояниям."""
    config = {"configurable": {"thread_id": thread_id}}

    result = await agent.ainvoke(
        {"messages": [HumanMessage(content=user_input)]},
        config=config,
        context=context,
    )
    return result


async def get_conversation_history(agent, thread_id: str, limit: int = 10):
    """Получение истории чекпоинтов для отката."""
    config = {"configurable": {"thread_id": thread_id}}

    history = []
    async for snap in agent.aget_state_history(config, limit=limit):
        history.append(
            {
                "checkpoint_id": snap.config.get("configurable", {}).get("checkpoint_id"),
                "step": snap.metadata.get("step") if snap.metadata else None,
                "messages_count": len(snap.values.get("messages", [])),
                "created_at": snap.created_at,
            }
        )
    return history


async def rollback_to_checkpoint(
    agent, thread_id: str, checkpoint_id: str
):
    """Возвращает состояние графа на момент указанного чекпоинта.

    Не меняет «текущий» чекпоинт диалога: при следующем ainvoke граф
    продолжит с последнего чекпоинта. Чтобы продолжить диалог с этой точки,
    передайте в config при следующем вызове тот же checkpoint_id:
    config = {"configurable": {"thread_id": thread_id, "checkpoint_id": checkpoint_id}}
    """
    config = {
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_id": checkpoint_id,
        }
    }
    state = await agent.aget_state(config)
    return state.values
