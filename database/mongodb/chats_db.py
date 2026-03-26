"""
Асинхронная база данных пользователей для работы с MongoDB.
- create_user(login, password, name, surname, role, admin=False): Создает нового пользователя
- get_all_users(): Получает список всех пользователей
- get_user_by_login(login): Находит пользователя по логину
- delete_user(login): Удаляет пользователя по логину
- update_password(login, new_password): Обновляет пароль пользователя
- update_name_surname(login, name=None, surname=None): Обновляет имя и/или отчество
- set_admin_role(login, is_admin): Назначает или снимает статус администратора
- update_user_role(login, role): Изменяет роль пользователя
- ensure_admin_exists(): Проверяет и создает администратора при необходимости
- authenticate_user(self, login: str, password: str): аутентифифкация пользователя
- drop_collection(): Сброс коллекции в БД
- close_connection(): Закрывает соединение с базой данных

Пример использования:
    from database.mongodb.async_db import AsyncUserDatabase
    import asyncio

    async def example():
        db = AsyncUserDatabase()
        user = await db.create_user("test", "password", "Имя", "Фамилия", "user")
        users = await db.get_all_users()
        await db.close_connection()
"""

import asyncio
import uuid
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError
from datetime import datetime, timezone
from setup_logger import setup_logger
from config import settings
from app.security import get_password_hash, verify_password

logger = setup_logger("database_m", log_file="database.log")

class AsyncChatsDatabase:
    _instance: Optional['AsyncChatsDatabase'] = None
    _client: Optional[AsyncIOMotorClient] = None
    _db = None
    _collection = None
    _is_connected = False
    _lock = asyncio.Lock()  # Для синхронизации доступа

    def __new__(cls, connection_string=None, db_name='Diplom'):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, connection_string=None, db_name='Diplom'):
        # Инициализация только один раз
        if not hasattr(self, '_initialized'):
            self.connection_string = connection_string or settings.MONGODB_URL_DEV
            self.db_name = db_name
            self._initialized = True

    async def connect(self):
        """Безопасное подключение к БД"""
        async with self._lock:
            if not self._is_connected:
                try:
                    self._client = AsyncIOMotorClient(
                        self.connection_string,
                        maxPoolSize=50,  # Ограничение пула соединений
                        minPoolSize=10,
                        serverSelectionTimeoutMS=5000,
                        socketTimeoutMS=30000
                    )
                    self._db = self._client[self.db_name]
                    self._collection = self._db['chats']
                    await self._create_indexes()
                    self._is_connected = True
                    logger.info("✅ Подключение к MongoDB установлено")
                except Exception as e:
                    logger.error(f"❌ Ошибка подключения к MongoDB: {e}")
                    raise

    async def disconnect(self):
        """Безопасное отключение от БД"""
        async with self._lock:
            if self._is_connected and self._client:
                try:
                    self._client.close()
                    self._is_connected = False
                    logger.info("✅ Подключение к MongoDB закрыто")
                except Exception as e:
                    logger.error(f"❌ Ошибка при закрытии подключения: {e}")

    async def _create_indexes(self):
        """Создание индексов"""
        try:
            indexes = await self._collection.index_information()
            if "chat_id_1" not in indexes:
                await self._collection.create_index("chat_id", unique=True)
                await self._collection.create_index("user_id", unique=True)
                logger.info("✅ Индексы созданы")
            else:
                logger.info("✅ Индексы уже существуют")
        except Exception as e:
            logger.error(f"❌ Ошибка при создании индексов: {e}")
            raise

    async def ensure_connection(self):
        """Гарантирует подключение к БД"""
        if not self._is_connected:
            await self.connect()

    async def create_chats_table(self):
        """Создание коллекции chats (в MongoDB это происходит автоматически при первой вставке)"""
        logger.info("✅ Коллекция 'chats' создана или уже существует.")

    async def create_chat(self, chat_id: str, user_id: str, title: str):
        """
        Добавляет новый чат в коллекцию chats.

        :param chat_id: ID чата (обязательный, уникальный)
        :param user_id: ID пользователя (обязательный)
        :param title: Заголовок чата
        :return: Словарь с данными чата
        """
        try:
            # Проверка на существование чата
            existing = await self._collection.find_one({"chat_id": chat_id})
            if existing:
                logger.info(f"Чат с ID '{chat_id}' уже существует.")
                raise ValueError(f"Чат с ID '{chat_id}' уже существует.")
            
            date = datetime.now(timezone.utc)

            chat_data = {
                "chat_id": chat_id,
                "user_id": user_id,
                "title": title,
                "created_at": date,
                "updated_at": date
            }

            result = await self._collection.insert_one(chat_data)
            logger.info(f"👤 Чат создан: {chat_id}")

            # Получаем вставленный документ
            inserted_chat = await self._collection.find_one({"_id": result.inserted_id})
            return inserted_chat

        except DuplicateKeyError:
            logger.info(f"Чат с ID '{chat_id}' уже существует.")
            raise ValueError(f"Чат с ID '{chat_id}' уже существует.")
        except Exception as e:
            logger.error(f"❌ Ошибка при создании чата: {e}")
            raise

    async def get_chat_by_user_id(self, user_id: str):
        """
        Получает чат по user_id.
        """
        try:
            await self.ensure_connection()
            chat = await self._collection.find_one({"user_id": user_id})
            return chat
        except Exception as e:
            logger.error(f"❌ Ошибка при получении чата по user_id - {user_id}: {e}")
            raise

    async def get_chat_by_chat_id(self, chat_id: str):
        """
        Получает чат по chat_id.
        """
        try:
            await self.ensure_connection()
            chat = await self._collection.find_one({"chat_id": chat_id})
            return chat
        except Exception as e:
            logger.error(f"❌ Ошибка при получении чата по chat_id - {chat_id}: {e}")
            raise

    async def get_chat_id_by_user_id(self, user_id: str):
        """
        Получает chat_id по user_id.
        """
        try:
            await self.ensure_connection()
            chat = await self._collection.find_one({"user_id": user_id})
            return chat["chat_id"]
        except Exception as e:
            logger.error(f"❌ Ошибка при получении chat_id по user_id - {user_id}: {e}")
            raise

    async def get_all_chats_by_user_id(self, user_id: str):
        """
        Получает все чаты по user_id.
        """
        try:
            await self.ensure_connection()
            chats = await self._collection.find({"user_id": user_id}).sort("created_at", -1)
            return chats
        except Exception as e:
            logger.error(f"❌ Ошибка при получении всех чатов по user_id - {user_id}: {e}")
            raise

    async def get_all_chats_id_by_user_id(self, user_id: str):
        """
        Получает все chat_id по user_id.
        """
        try:
            await self.ensure_connection()
            chats = await self._collection.find({"user_id": user_id}).sort("created_at", -1)
            return [chat["chat_id"] for chat in chats]
        except Exception as e:
            logger.error(f"❌ Ошибка при получении всех chat_id по user_id - {user_id}: {e}")
            raise

    async def get_all_chats(self):
        """
        Получает все чаты.
        """
        try:
            await self.ensure_connection()
            chats = await self._collection.find().sort("created_at", -1)
            logger.info(f"👥 Получено {len(chats)} чатов.")
            return chats
        except Exception as e:
            logger.error(f"❌ Ошибка при получении всех чатов: {e}")
            raise

    async def delete_chat_by_chat_id(self, chat_id: str):
        """
        Удаляет чат по chat_id.
        """
        try:
            await self.ensure_connection()
            result = await self._collection.delete_one({"chat_id": chat_id})
            if result.deleted_count == 0:
                logger.warning(f"Чат с ID '{chat_id}' не был удалён (возможно, не найден).")
                raise RuntimeError("Ошибка при удалении чата.")
            else:
                logger.info(f"🗑️ Чат с ID '{chat_id}' успешно удалён.")
                return True
        except Exception as e:
            logger.error(f"❌ Ошибка при удалении чата по chat_id - {chat_id}: {e}")
            raise

    async def convert_chat_for_api_response(self, chat: dict | list):
        """
        Конвертирует чаты из базы данных в формат для API ответа.
        Поддерживает как один чат, так и список чатов.

        Args:
            chat (dict | list): Данные чата(ов) из MongoDB

        Returns:
            dict | list: Отформатированные данные чата(ов) для API ответа
        """
        # Если передана одна запись
        if isinstance(chat, dict):

            return {
                "chat_id": chat['chat_id'],
                "user_id": chat['user_id'],
                "title": chat['title'],
                "created_at": chat['created_at'].strftime("%d.%m.%Y %H:%M:%S"), # формат дата и время
                "updated_at": chat['updated_at'].strftime("%d.%m.%Y %H:%M:%S")
            }

        # Если передан список пользователей
        elif isinstance(chat, list):
            result_list = []
            for chat_item in chat:

                result_list.append({
                    "chat_id": chat_item['chat_id'],
                    "user_id": chat_item['user_id'],
                    "title": chat_item['title'],
                    "created_at": chat_item['created_at'].strftime("%d.%m.%Y %H:%M:%S"),
                    "updated_at": chat_item['updated_at'].strftime("%d.%m.%Y %H:%M:%S")
                })

            return result_list

        # Если передан неподдерживаемый тип
        else:
            raise TypeError("Параметр 'user' должен быть словарем или списком")

    async def drop_collection(self):
        try:
            await self.ensure_connection()
            result = self._collection.drop()
            if result == 0:
                logger.error(f"Не удалось удалить коллекцию {self._collection.name}")
                return False
            else:
                logger.info(f"Коллекция {self._collection.name} удалена успешно")
        except Exception as e:
            logger.error(f"Непредвиденная ошибка: {e}")

    async def close_connection(self):
        """Закрытие соединения с базой данных"""
        await self.disconnect()
        