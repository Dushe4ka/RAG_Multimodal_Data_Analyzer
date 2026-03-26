# Создание глобального объекта класса БД (с пуллом соединений)

from database.mongodb.async_db import AsyncUserDatabase
from database.mongodb.chats_db import AsyncChatsDatabase

db = AsyncUserDatabase()
chats_db = AsyncChatsDatabase()