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

class AsyncUserDatabase:
    _instance: Optional['AsyncUserDatabase'] = None
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
                    self._collection = self._db['users']
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
            if "login_1" not in indexes:
                await self._collection.create_index("login", unique=True)
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

    async def create_users_table(self):
        """Создание коллекции users (в MongoDB это происходит автоматически при первой вставке)"""
        logger.info("✅ Коллекция 'users' создана или уже существует.")

    async def create_user(self, login: str, password: str, name: str, surname: str, role: str, admin: bool = False):
        """
        Добавляет нового пользователя в коллекцию users.

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
            existing = await self._collection.find_one({"login": login})
            if existing:
                logger.info(f"Пользователь с логином '{login}' уже существует.")
                raise ValueError(f"Пользователь с логином '{login}' уже существует.")

            # Хэширование пароля
            hash_password = await get_password_hash(password=password)

            # Вставка нового пользователя
            user_data = {
                "user_id": str(uuid.uuid4()),
                "login": login,
                "password": hash_password,
                "admin": admin,
                "name": name,
                "surname": surname,
                "role": role,
                "created_at": datetime.now(timezone.utc)
            }

            result = await self._collection.insert_one(user_data)

            status = "админ" if admin else "пользователь"
            logger.info(f"👤 Пользователь создан: {login} ({status})")

            # Получаем вставленный документ
            inserted_user = await self._collection.find_one({"_id": result.inserted_id})
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
            # Убедимся, что подключение активно
            await self.ensure_connection()

            # Проверяем, есть ли админ
            admin = await self._collection.find_one({"login": "admin"})

            # Хэшируем пароль админа
            hash_password = await get_password_hash(password="admin")

            if not admin:
                logger.info("🔐 Админ не найден. Создаём админа...")
                admin_data = {
                    "user_id": str(uuid.uuid4()),
                    "login": "admin",
                    "password": hash_password, 
                    "admin": True,
                    "name": "Администратор",
                    "surname": "Системный",
                    "role": "admin",
                    "created_at": datetime.now(timezone.utc)
                }

                await self._collection.insert_one(admin_data)
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
            await self.ensure_connection()
            cursor = self._collection.find().sort("created_at", -1)
            users = await cursor.to_list(length=None)

            if not users:
                logger.info("📭 Нет пользователей в базе данных.")
                return []

            logger.info(f"👥 Получено {len(users)} пользователей.")
            users = await self.convert_user_for_api_response(users)
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
            await self.ensure_connection()
            # Проверяем, существует ли пользователь
            existing = await self._collection.find_one({"login": login})
            if not existing:
                logger.warning(f"Попытка удалить несуществующего пользователя: {login}")
                raise ValueError(f"Пользователь с логином '{login}' не найден.")

            # Удаляем пользователя
            result = await self._collection.delete_one({"login": login})

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
            await self.ensure_connection()
            user = await self._collection.find_one({"user_id": user_id})

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
            await self.ensure_connection()
            user = await self._collection.find_one({"login": login})

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
            await self.ensure_connection()
            # Проверяем существование пользователя
            existing = await self._collection.find_one({"login": login})
            if not existing:
                logger.warning(f"Попытка изменить пароль у несуществующего пользователя: {login}")
                raise ValueError(f"Пользователь с логином '{login}' не найден.")

            # Хэшируем новый пароль
            hash_password = await get_password_hash(password=new_password)

            # Обновляем пароль
            result = await self._collection.update_one(
                {"login": login},
                {"$set": {"password": hash_password}}
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

    async def update_password_modified(self, user_id: str, old_password: str, new_password: str, confirm_password: str):
        """
        Меняет пароль пользователя.
        Проверяет старый пароль и подтверждение нового пароля.
        Если пользователь не найден — выбрасывает ошибку.
        """
        try:
            await self.ensure_connection()

            # Проверяем существование пользователя
            existing = await self._collection.find_one({"user_id": user_id})
            if not existing:
                logger.warning(f"Попытка изменить пароль у несуществующего пользователя: {existing['login']}")
                raise ValueError(f"Пользователь с логином '{existing['login']}' не найден.")

            # Проверяем старый пароль
            if not await verify_password(old_password, existing["password"]):
                logger.warning(f"Неправильный старый пароль для пользователя: {existing['login']}")
                raise ValueError("Неправильный старый пароль.")

            # Проверяем совпадение нового пароля и подтверждения
            if new_password != confirm_password:
                logger.warning(f"Подтверждение нового пароля не совпадает для пользователя: {existing['login']}")
                raise ValueError("Новый пароль и его подтверждение не совпадают.")

            # Проверяем сложность пароля (опционально)
            secure = await self._is_password_secure(new_password)
            if not secure:
                raise ValueError("Пароль слишком слабый. Используйте не менее 8 символов с буквами и цифрами.")

            # Хэшируем новый пароль
            hash_password = await get_password_hash(password=new_password)

            # Обновляем пароль
            result = await self._collection.update_one(
                {"user_id": user_id},
                {"$set": {"password": hash_password}}
            )

            # Возвращаем True, даже если ничего не изменилось (это нормально)
            logger.info(f"🔐 Пароль пользователя {existing['login']} обновлён. "
                    f"Найденных записей: {result.matched_count}, "
                    f"Изменено: {result.modified_count}")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка при обновлении пароля для {existing['login']}: {e}")
            raise

    async def _is_password_secure(self, password: str) -> bool:
        """
        Проверяет сложность пароля.
        """
        if len(password) < 8:
            return False
        if not any(c.isalpha() for c in password):
            return False
        if not any(c.isdigit() for c in password):
            return False
        return True

    async def update_name_surname(self, login: str, name: str | None = None, surname: str | None = None):
        """
        Обновляет имя и/или отчество пользователя.
        Если параметр пустой (None), значение остаётся прежним.
        """
        try:
            await self.ensure_connection()
            # Проверяем существование пользователя
            existing = await self._collection.find_one({"login": login})
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
            result = await self._collection.update_one(
                {"login": login},
                {"$set": update_fields}
            )

            if result.modified_count > 0:
                updated_user = await self._collection.find_one({"login": login})
                logger.info(f"✏️ Данные пользователя {login} обновлены")
                updated_user = await self. convert_user_for_api_response(updated_user)
                return updated_user
            else:
                logger.warning(f"Обновление данных пользователя {login} не произошло.")
                return None

        except Exception as e:
            logger.error(f"❌ Ошибка при обновлении имени/отчества для {login}: {e}")
            raise

    async def profile_update_name_surname(self, user_id: str, name: str | None = None, surname: str | None = None):
        """
        Обновляет имя и/или фамилии пользователя.
        Если параметр пустой (None), значение остаётся прежним.
        """
        try:
            await self.ensure_connection()
            # Проверяем существование пользователя
            existing = await self._collection.find_one({"user_id": user_id})
            if not existing:
                logger.warning(f"Попытка обновить данные у несуществующего пользователя ID: {user_id}")
                raise ValueError(f"Пользователь с ID '{user_id}' не найден.")

            # Собираем обновления
            update_fields = {}

            if name is not None:
                update_fields["name"] = name

            if surname is not None:
                update_fields["surname"] = surname

            if not update_fields:
                logger.info(f"⚠️ Нет данных для обновления у пользователя ID: {user_id}.")
                return False

            # Обновляем данные
            result = await self._collection.update_one(
                {"user_id": user_id},
                {"$set": update_fields}
            )

            if result.modified_count > 0:
                updated_user = await self._collection.find_one({"user_id": user_id})
                logger.info(f"✏️ Данные пользователя (ID: {user_id}) {updated_user['login']} обновлены")
                updated_user = await self.convert_user_for_api_response(updated_user)
                return updated_user
            else:
                logger.warning(f"Обновление данных пользователя (ID: {user_id}) не произошло.")
                return None

        except Exception as e:
            logger.error(f"❌ Ошибка при обновлении имени/фамилии для (ID: {user_id}): {e}")
            raise

    async def set_admin_role(self, login: str, is_admin: bool):
        """
        Устанавливает статус админа для пользователя по логину.

        :param login: Логин пользователя
        :param is_admin: True — сделать админом, False — снять роль
        :return: True, если обновление прошло успешно
        """
        try:
            await self.ensure_connection()
            # Проверяем, существует ли пользователь
            existing = await self._collection.find_one({"login": login})
            if not existing:
                logger.warning(f"Попытка установить роль админа для несуществующего пользователя: {login}")
                raise ValueError(f"Пользователь с логином '{login}' не найден.")

            # Обновляем поле admin
            result = await self._collection.update_one(
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
            await self.ensure_connection()
            # Проверяем, существует ли пользователь
            existing = await self._collection.find_one({"login": login})
            if not existing:
                logger.warning(f"Попытка обновить роль для несуществующего пользователя: {login}")
                raise ValueError(f"Пользователь с логином '{login}' не найден.")

            # Обновляем поле role
            result = await self._collection.update_one(
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
            if user and await verify_password(password, user["password"]):
                logger.info(f"Пользователь {login} успешно прошел аутентификацию")
                return user
            else:
                logger.error(f"Пользователь {login} не прошел аутентификацию")
                return None
        except Exception as e:
            logger.error("Неверный логин или пароль")

    async def profile_get_user_data(self, user_id: str):
        """
        Берет данные пользователя для профиля
        """
        try:
            await self.ensure_connection()
            user = await self.get_user_by_user_id(user_id=user_id)

            # Преобразуем datetime в строку формата ДД.ММ.ГГГГ
            created_at_date = user['created_at'].strftime('%d.%m.%Y')

            return {
                "login": user['login'],
                "admin": user['admin'],
                "name": user['name'],
                "surname": user['surname'],
                "role": user['role'],
                "created_at": created_at_date  # Теперь будет в формате "11.02.2026"
            }
        except Exception as e:
            logger.error(f"Ошибка при получении данных пользователя: {e}")
            raise

    async def convert_user_for_api_response(self, user: dict | list):
        """
        Конвертирует пользовательские данные из базы данных в формат для API ответа.
        Поддерживает как один пользователь, так и список пользователей.

        Args:
            user (dict | list): Данные пользователя(ей) из MongoDB

        Returns:
            dict | list: Отформатированные данные пользователя(ей) для API ответа
        """
        # Если передана одна запись
        if isinstance(user, dict):
            # Конвертируем дату в нужный формат
            created_at_date = user['created_at'].strftime("%d.%m.%Y")

            return {
                "login": user['login'],
                "admin": user['admin'],
                "name": user['name'],
                "surname": user['surname'],
                "role": user['role'],
                "created_at": created_at_date  # Теперь будет в формате "11.02.2026"
            }

        # Если передан список пользователей
        elif isinstance(user, list):
            result_list = []
            for user_item in user:
                # Конвертируем дату в нужный формат
                created_at_date = user_item['created_at'].strftime("%d.%m.%Y")

                result_list.append({
                    "login": user_item['login'],
                    "admin": user_item['admin'],
                    "name": user_item['name'],
                    "surname": user_item['surname'],
                    "role": user_item['role'],
                    "created_at": created_at_date  # Теперь будет в формате "11.02.2026"
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