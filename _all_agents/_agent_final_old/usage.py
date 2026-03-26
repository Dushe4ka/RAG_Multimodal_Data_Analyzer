# usage.py
import uuid
from mcp_integration import AgentContext

async def run_with_rollback_support(agent, user_input: str, thread_id: str, context: AgentContext):
    """Запуск агента с возможностью отката к предыдущим состояниям"""
    
    config = {"configurable": {"thread_id": thread_id}}
    
    # Выполнение
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": user_input}]},
        config=config,
        context=context
    )
    
    return result

async def get_conversation_history(agent, thread_id: str, limit: int = 10):
    """Получение истории чекпоинтов для отката"""
    config = {"configurable": {"thread_id": thread_id}}
    
    # Получаем историю состояний
    history = list(agent.get_state_history(config, limit=limit))
    
    return [
        {
            "checkpoint_id": snap.config["configurable"]["checkpoint_id"],
            "step": snap.metadata.get("step"),
            "messages_count": len(snap.values.get("messages", [])),
            "created_at": snap.created_at,
        }
        for snap in history
    ]

async def rollback_to_checkpoint(agent, thread_id: str, checkpoint_id: str):
    """Возврат к конкретному чекпоинту"""
    config = {
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_id": checkpoint_id  # Указываем конкретный чекпоинт
        }
    }
    
    # Получаем состояние из чекпоинта
    state = agent.get_state(config)
    return state.values