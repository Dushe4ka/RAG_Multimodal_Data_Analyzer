from langgraph.checkpoint.mongodb import MongoDBSaver
from langgraph.store.mongodb import MongoDBStore  # или из langgraph_store_mongodb
from config import settings
from pymongo import MongoClient
from langchain_core.tools import tool
from langgraph.config import get_config, get_store

_client = MongoClient(settings.MONGODB_URL_DEV)

# Краткосрочная память: состояние графа по thread_id (диалог)
checkpointer = MongoDBSaver(
    client=_client,
    db_name="chat_history",
    checkpoint_collection_name="checkpoints",
    writes_collection_name="checkpoint_writes",
)

# Коллекция для долгосрочной памяти (Store ожидает объект Collection)
_long_term_collection = _client["chat_history"]["long_term_memory"]

long_term_store = MongoDBStore(
    collection=_long_term_collection,
)

def get_current_user_id() -> str:
    """Возвращает user_id из config. Вызывать из инструментов, которым нужен текущий пользователь."""
    config = get_config()
    user_id = config.get("configurable", {}).get("user_id")
    if not user_id:
        raise ValueError("user_id не передан в config.")
    return str(user_id)

@tool
def save_user_info(name: str, note: str = "") -> str:
    """Сохрани информацию о текущем пользователе (имя и заметку) в долгосрочную память.
    Вызывай, когда пользователь представился или сказал что-то важное о себе.
    Параметры: name — имя, note — заметка о пользователе."""
    user_id = get_current_user_id()
    store = get_store()
    store.put(("users",), str(user_id), {"name": name, "note": note})
    return f"Запомнил: {name}, {note or '(без заметки)'}"


@tool
def get_user_info() -> str:
    """Достань из долгосрочной памяти сохранённую информацию о текущем пользователе."""
    user_id = get_current_user_id()
    store = get_store()
    value = store.get(("users",), str(user_id))
    if value is None or value.value is None:
        return "Ничего не найдено."
    v = value.value
    return f"Имя: {v.get('name', '?')}, Заметка: {v.get('note', '—')}"