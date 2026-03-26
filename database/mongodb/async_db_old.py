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
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError
from datetime import datetime, timezone
from setup_logger import setup_logger
from config import settings

MONGODB_URL = settings.MONGODB_URL

logger = setup_logger("database_m", log_file="database.log")

class AsyncUserDatabase:
    def __init__(self, connection_string=MONGODB_URL, db_name='Diplom'):
        self.client = AsyncIOMotorClient(connection_string)
        self.db = self.client[db_name]
        self.collection = self.db['users']

    async def init_db(self):
        """Создание индексов"""
        try:
            # Проверяем, существуют ли уже индексы
            indexes = await self.collection.index_information()
            if "login_1" not in indexes:
                await self.collection.create_index("login", unique=True)
                await self.collection.create_index("user_id", unique=True)
                logger.info("✅ Индексы созданы")
            else:
                logger.info("✅ Индексы уже существуют")
        except Exception as e:
            logger.error(f"❌ Ошибка при инициализации: {e}")

    async def create_users_table(self):
        """Создание коллекции users (в MongoDB это происходит автоматически при первой вставке)"""
        logger.info("✅ Коллекция 'users' создана или уже существует.")

    async def create_user(self, login: str, password: str, name: str, surname: str, role: str, admin: bool = False):
        """
        Добавляет нового пользователя в коллекцию users.

        :param users_id: ID пользователя (integer) - он создается автоматически
        :param login: Логин (обязательный, уникальный)
        :param password: Пароль (не хэшируется — для примера)
        :param name: Имя
        :param surname: Отчество
        :param role: Роль
        :param admin: Булево значение: True = админ, False = обычный пользователь (по умолчанию False)
        :return: Словарь с данными пользователя
        """
        try:
            # Проверка на существование логина
            existing = await self.collection.find_one({"login": login})
            if existing:
                logger.info(f"Пользователь с логином '{login}' уже существует.")
                raise ValueError(f"Пользователь с логином '{login}' уже существует.")

            # Вставка нового пользователя
            user_data = {
                "user_id": str(uuid.uuid4()),
                "login": login,
                "password": password,  # В реальном приложении хэшируйте пароль!
                "admin": admin,
                "name": name,
                "surname": surname,
                "role": role,
                "created_at": datetime.now(timezone.utc)
                
            }

            result = await self.collection.insert_one(user_data)

            status = "админ" if admin else "пользователь"
            logger.info(f"👤 Пользователь создан: {login} ({status})")

            # Получаем вставленный документ
            inserted_user = await self.collection.find_one({"_id": result.inserted_id})
            return inserted_user

        except DuplicateKeyError:
            logger.info(f"Пользователь с логином '{login}' уже существует.")
            raise ValueError(f"Пользователь с логином '{login}' уже существует.")
        except Exception as e:
            logger.error(f"❌ Ошибка при создании пользователя: {e}")
            raise

    async def ensure_admin_exists(self):
        """
        При каждом запуске проверяет, есть ли пользователь с логином 'admin'.
        Если нет — создаёт его с паролем 'admin'.
        """
        try:
            # Проверяем, есть ли админ
            admin = await self.collection.find_one({"login": "admin"})

            if not admin:
                logger.info("🔐 Админ не найден. Создаём админа...")
                admin_data = {
                    "user_id": str(uuid.uuid4()),
                    "login": "admin",
                    "password": "admin",  # В реальности — хэш!
                    "admin": True,
                    "name": "Администратор",
                    "surname": "Системный",
                    "role": "admin",
                    "created_at": datetime.now(timezone.utc)
                }

                await self.collection.insert_one(admin_data)
                logger.info("✅ Админ успешно создан!")
            else:
                logger.info("✅ Админ уже существует.")

        except Exception as e:
            logger.error(f"❌ Ошибка при проверке/создании админа: {e}")
            raise

    async def get_all_users(self):
        """
        Получает всех пользователей из коллекции users.
        Возвращает список словарей с полями: _id, login, name, surname, admin, created_at.
        """
        try:
            cursor = self.collection.find().sort("created_at", -1)
            users = await cursor.to_list(length=None)

            if not users:
                logger.info("📭 Нет пользователей в базе данных.")
                return []

            logger.info(f"👥 Получено {len(users)} пользователей.")
            return users

        except Exception as e:
            logger.error(f"❌ Ошибка при получении пользователей: {e}")
            raise

    async def delete_user(self, login: str):
        """
        Удаляет пользователя из коллекции users по логину.
        Возвращает True, если пользователь был найден и удалён.
        """
        try:
            # Проверяем, существует ли пользователь
            existing = await self.collection.find_one({"login": login})
            if not existing:
                logger.warning(f"Попытка удалить несуществующего пользователя: {login}")
                raise ValueError(f"Пользователь с логином '{login}' не найден.")

            # Удаляем пользователя
            result = await self.collection.delete_one({"login": login})

            if result.deleted_count == 0:
                logger.warning(f"Пользователь {login} не был удалён (возможно, не найден).")
                raise RuntimeError("Ошибка при удалении пользователя.")
            else:
                logger.info(f"🗑️ Пользователь {login} успешно удалён.")
                return True

        except Exception as e:
            logger.error(f"❌ Ошибка при удалении пользователя {login}: {e}")
            raise

    async def get_user_by_user_id(self, user_id: str):
        """
        Находит пользователя по user_id.
        """
        try:
            user = await self.collection.find_one({"user_id": user_id})

            if user:
                logger.info(f"🔍 Пользователь {user['login']} найден по  user_id - {user_id}")
                return user
            else:
                logger.info(f"🧩 Пользователь {user['login']} по user_id - {user_id} не найден.")
                return None

        except Exception as e:
            logger.error(f"❌ Ошибка при поиске пользователя по user_id - {user_id}: {e}")
            raise


    async def get_user_by_login(self, login: str):
        """
        Находит пользователя по логину.
        Возвращает словарь с данными или None, если не найден.
        """
        try:
            user = await self.collection.find_one({"login": login})

            if user:
                logger.info(f"🔍 Пользователь найден: {login}")
                return user
            else:
                logger.info(f"🧩 Пользователь с логином '{login}' не найден.")
                return None

        except Exception as e:
            logger.error(f"❌ Ошибка при поиске пользователя {login}: {e}")
            raise

    async def update_password(self, login: str, new_password: str):
        """
        Меняет пароль пользователя.
        Если пользователь не найден — выбрасывает ошибку.
        """
        try:
            # Проверяем существование пользователя
            existing = await self.collection.find_one({"login": login})
            if not existing:
                logger.warning(f"Попытка изменить пароль у несуществующего пользователя: {login}")
                raise ValueError(f"Пользователь с логином '{login}' не найден.")

            # Обновляем пароль
            result = await self.collection.update_one(
                {"login": login},
                {"$set": {"password": new_password}}
            )

            # Возвращаем True, даже если ничего не изменилось (это нормально)
            # MongoDB автоматически не обновит документ, если значение совпадает
            logger.info(f"🔐 Пароль пользователя {login} обновлён. "
                    f"Найденных записей: {result.matched_count}, "
                    f"Изменено: {result.modified_count}")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка при обновлении пароля для {login}: {e}")
            raise

    async def update_name_surname(self, login: str, name: str | None = None, surname: str | None = None):
        """
        Обновляет имя и/или отчество пользователя.
        Если параметр пустой (None), значение остаётся прежним.
        """
        try:
            # Проверяем существование пользователя
            existing = await self.collection.find_one({"login": login})
            if not existing:
                logger.warning(f"Попытка обновить данные у несуществующего пользователя: {login}")
                raise ValueError(f"Пользователь с логином '{login}' не найден.")

            # Собираем обновления
            update_fields = {}

            if name is not None:
                update_fields["name"] = name

            if surname is not None:
                update_fields["surname"] = surname

            if not update_fields:
                logger.info(f"⚠️ Нет данных для обновления у пользователя {login}.")
                return False

            # Обновляем данные
            result = await self.collection.update_one(
                {"login": login},
                {"$set": update_fields}
            )

            if result.modified_count > 0:
                updated_user = await self.collection.find_one({"login": login})
                logger.info(f"✏️ Данные пользователя {login} обновлены")
                return updated_user
            else:
                logger.warning(f"Обновление данных пользователя {login} не произошло.")
                return None

        except Exception as e:
            logger.error(f"❌ Ошибка при обновлении имени/отчества для {login}: {e}")
            raise

    async def set_admin_role(self, login: str, is_admin: bool):
        """
        Устанавливает статус админа для пользователя по логину.

        :param login: Логин пользователя
        :param is_admin: True — сделать админом, False — снять роль
        :return: True, если обновление прошло успешно
        """
        try:
            # Проверяем, существует ли пользователь
            existing = await self.collection.find_one({"login": login})
            if not existing:
                logger.warning(f"Попытка установить роль админа для несуществующего пользователя: {login}")
                raise ValueError(f"Пользователь с логином '{login}' не найден.")

            # Обновляем поле admin
            result = await self.collection.update_one(
                {"login": login},
                {"$set": {"admin": is_admin}}
            )

            # Возвращаем True, даже если ничего не изменилось
            logger.info(f"🛡️ Статус администратора пользователя {login} обновлён. "
                    f"Найденных записей: {result.matched_count}, "
                    f"Изменено: {result.modified_count}")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка при установке роли админа для {login}: {e}")
            raise

    async def update_user_role(self, login: str, role: str):
        """
        Изменение роли у пользователя по логину.

        :param login: Логин пользователя
        :param role: Роль для пользователя
        :return: True, если обновление прошло успешно
        """
        try:
            # Проверяем, существует ли пользователь
            existing = await self.collection.find_one({"login": login})
            if not existing:
                logger.warning(f"Попытка обновить роль для несуществующего пользователя: {login}")
                raise ValueError(f"Пользователь с логином '{login}' не найден.")

            # Обновляем поле role
            result = await self.collection.update_one(
                {"login": login},
                {"$set": {"role": role}}
            )

            # Возвращаем True, даже если ничего не изменилось
            logger.info(f"🛡️ Роль пользователя {login} обновлена. "
                    f"Найденных записей: {result.matched_count}, "
                    f"Изменено: {result.modified_count}")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка при установке роли {role} для {login}: {e}")
            raise

    async def authenticate_user(self, login: str, password: str):
        """
        Метод для проверки корректности логина и пароля
        """
        try:
            user = await self.get_user_by_login(login=login)
            if user["password"] == password:
                logger.info(f"Пользователь {login} успешно прошел аутентификацию")
                return user
            else:
                logger.error(f"Пользователь {login} не прошел аутентификацию")
                return None
        except Exception as e:
            logger.error("Неверный логин или пароль")

    async def drop_collection(self):
        try:
            result = self.collection.drop()
            if result == 0:
                logger.error(f"Не удалось удалить коллекцию {self.collection.name}")
                return False
            else:
                logger.info(f"Коллекция {self.collection.name} удалена успешно")
        except Exception as e:
            logger.error(f"Непредвиденная ошибка: {e}")


    async def close_connection(self):
        """Закрытие соединения с базой данных"""
        self.client.close()

db = AsyncUserDatabase()
