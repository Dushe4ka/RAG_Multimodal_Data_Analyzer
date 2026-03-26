from database.postgresql.main_db import connect_to_db
import asyncpg
import asyncio
from setup_logger import setup_logger
from passlib.context import CryptContext

logger = setup_logger("database", log_file="database.log")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# === 1. Создание таблицы users ===
async def create_users_table():
    """
    Создаёт таблицу users с полями:
    - login (NOT NULL)
    - password (NOT NULL)
    - admin (BOOLEAN, DEFAULT FALSE)
    - name (NOT NULL)
    - surname (NOT NULL)
    - role (NOT NULL, DEFAULT 'user')
    """
    conn = None
    try:
        conn = await connect_to_db()

        query = """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            login VARCHAR(50) UNIQUE NOT NULL,
            password TEXT NOT NULL,
            admin BOOLEAN DEFAULT FALSE,
            name VARCHAR(100) NOT NULL,
            surname VARCHAR(100) NOT NULL,
            role VARCHAR(50) NOT NULL DEFAULT 'user',
            created_at TIMESTAMP DEFAULT NOW()
        );
        """

        await conn.execute(query)
        logger.info("✅ Таблица 'users' создана или уже существует.")

    except Exception as e:
        logger.error(f"❌ Ошибка при создании таблицы: {e}")
        raise

    finally:
        if conn:
            await conn.close()

# === 2. Создание пользователя (с возможностью задать admin и role) ===
async def create_user(login: str, password: str, name: str, surname: str, admin: bool = False, role: str = "user"):
    """
    Добавляет нового пользователя в таблицу users.

    :param login: Логин (обязательный, уникальный)
    :param password: Пароль (хэшируется)
    :param name: Имя
    :param surname: Отчество
    :param admin: Булево значение: True = админ, False = обычный пользователь (по умолчанию False)
    :param role: Роль пользователя (по умолчанию "user")
    :return: Словарь с данными пользователя
    """
    conn = None

    password = pwd_context.hash(password)

    try:
        conn = await connect_to_db()

        # Проверка на существование логина
        existing = await conn.fetchval(
            "SELECT 1 FROM users WHERE login = $1",
            login
        )
        if existing:
            logger.info(f"Пользователь с логином '{login}' уже существует.")
            raise ValueError(f"Пользователь с логином '{login}' уже существует.")

        # Вставка нового пользователя с указанием admin и role
        query = """
        INSERT INTO users (login, password, name, surname, admin, role)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id, login, name, surname, admin, role, created_at;
        """

        result = await conn.fetchrow(query, login, password, name, surname, admin, role)

        status = "админ" if admin else "пользователь"
        logger.info(f"👤 Пользователь создан: {login} ({status}), роль: {role}")
        return dict(result)

    except asyncpg.UniqueViolationError:
        logger.info(f"Пользователь с логином '{login}' уже существует.")
        raise ValueError(f"Пользователь с логином '{login}' уже существует.")
    except Exception as e:
        logger.error(f"❌ Ошибка при создании пользователя: {e}")
        raise

    finally:
        if conn:
            await conn.close()


# === 3. Обеспечение наличия админа ===
async def ensure_admin_exists():
    """
    При каждом запуске проверяет, есть ли пользователь с логином 'admin'.
    Если нет — создаёт его с паролем 'admin'.
    """
    conn = None
    try:
        conn = await connect_to_db()

        # Проверяем, есть ли админ
        admin = await conn.fetchrow(
            "SELECT * FROM users WHERE login = $1",
            "admin"
        )

        if not admin:
            logger.info("🔐 Админ не найден. Создаём админа...")
            await create_user(
                login="admin",
                password="admin",
                name="Администратор",
                surname="Системный",
                admin=True,
                role="admin"
            )
            logger.info("✅ Админ успешно создан!")
        else:
            logger.info("✅ Админ уже существует.")

    except Exception as e:
        logger.error(f"❌ Ошибка при проверке/создании админа: {e}")
        raise

    finally:
        if conn:
            await conn.close()

# === 4. Получение всех пользователей из таблицы users ===
async def get_all_users():
    """
    Получает всех пользователей из таблицы users.
    Возвращает список словарей с полями: id, login, name, surname, admin, role, created_at.
    """
    conn = None
    try:
        conn = await connect_to_db()

        query = """
        SELECT id, login, name, surname, admin, role, created_at 
        FROM users 
        ORDER BY created_at DESC;
        """

        rows = await conn.fetch(query)

        if not rows:
            logger.info("📭 Нет пользователей в базе данных.")
            return []

        users = [dict(row) for row in rows]
        logger.info(f"👥 Получено {len(users)} пользователей.")
        return users

    except Exception as e:
        logger.error(f"❌ Ошибка при получении пользователей: {e}")
        raise

    finally:
        if conn:
            await conn.close()

# === 5. Удаление пользователя по логину ===
async def delete_user(login: str):
    """
    Удаляет пользователя из таблицы users по логину.
    Возвращает True, если пользователь был найден и удалён.
    """
    conn = None
    try:
        conn = await connect_to_db()

        # Проверяем, существует ли пользователь
        existing = await conn.fetchval(
            "SELECT 1 FROM users WHERE login = $1",
            login
        )
        if not existing:
            logger.warning(f"Попытка удалить несуществующего пользователя: {login}")
            raise ValueError(f"Пользователь с логином '{login}' не найден.")

        # Удаляем пользователя
        result = await conn.execute(
            "DELETE FROM users WHERE login = $1",
            login
        )

        if result == "DELETE 0":
            logger.warning(f"Пользователь {login} не был удалён (возможно, не найден).")
            raise RuntimeError("Ошибка при удалении пользователя.")
        else:
            logger.info(f"🗑️ Пользователь {login} успешно удалён.")
            return True

    except Exception as e:
        logger.error(f"❌ Ошибка при удалении пользователя {login}: {e}")
        raise

    finally:
        if conn:
            await conn.close()

# === 6. Поиск пользователя по логину ===
async def get_user_by_login(login: str):
    """
    Находит пользователя по логину.
    Возвращает словарь с данными или None, если не найден.
    """
    conn = None
    try:
        conn = await connect_to_db()

        query = """
        SELECT id, login, password, admin, name, surname, role, created_at 
        FROM users 
        WHERE login = $1;
        """

        row = await conn.fetchrow(query, login)
        if row:
            user = dict(row)
            logger.info(f"🔍 Пользователь найден: {login}")
            return user
        else:
            logger.info(f"🧩 Пользователь с логином '{login}' не найден.")
            return None

    except Exception as e:
        logger.error(f"❌ Ошибка при поиске пользователя {login}: {e}")
        raise

    finally:
        if conn:
            await conn.close()


# === 7. Обновление пароля ===
async def update_password(login: str, new_password: str):
    """
    Меняет пароль пользователя.
    Если пользователь не найден — выбрасывает ошибку.
    """
    conn = None
    try:
        conn = await connect_to_db()

        # Проверяем существование пользователя
        existing = await conn.fetchval(
            "SELECT 1 FROM users WHERE login = $1",
            login
        )
        if not existing:
            logger.warning(f"Попытка изменить пароль у несуществующего пользователя: {login}")
            raise ValueError(f"Пользователь с логином '{login}' не найден.")

        # Хэшируем новый пароль
        new_password_hashed = pwd_context.hash(new_password)

        # Обновляем пароль
        result = await conn.execute(
            "UPDATE users SET password = $1 WHERE login = $2",
            new_password_hashed,
            login
        )

        if result == "UPDATE 0":
            logger.warning(f"Пароль пользователя {login} не был обновлён.")
            raise RuntimeError("Обновление пароля не удалось.")
        else:
            logger.info(f"🔐 Пароль пользователя {login} успешно изменён.")
            return True

    except Exception as e:
        logger.error(f"❌ Ошибка при обновлении пароля для {login}: {e}")
        raise

    finally:
        if conn:
            await conn.close()


# === 8. Обновление имени и отчества (по желанию) ===
async def update_name_surname(login: str, name: str | None = None, surname: str | None = None):
    """
    Обновляет имя и/или отчество пользователя.
    Если параметр пустой (None), значение остаётся прежним.
    """
    conn = None
    try:
        conn = await connect_to_db()

        # Проверяем существование пользователя
        existing = await conn.fetchval(
            "SELECT 1 FROM users WHERE login = $1",
            login
        )
        if not existing:
            logger.warning(f"Попытка обновить данные у несуществующего пользователя: {login}")
            raise ValueError(f"Пользователь с логином '{login}' не найден.")

        # Собираем запрос динамически
        updates = []
        values = []

        if name is not None:
            updates.append("name = $1")
            values.append(name)

        if surname is not None:
            updates.append("surname = $2")
            values.append(surname)

        if not updates:
            logger.info(f"⚠️ Нет данных для обновления у пользователя {login}.")
            return False

        # Добавляем login в конец значений
        values.append(login)

        query = f"""
        UPDATE users 
        SET {', '.join(updates)} 
        WHERE login = ${len(values)}
        RETURNING id, login, name, surname, admin, role;
        """

        result = await conn.fetchrow(query, *values)

        if result:
            logger.info(f"✏️ Данные пользователя {login} обновлены: Имя={result['name']}, Отчество={result['surname']}")
            return dict(result)
        else:
            logger.warning(f"Обновление данных пользователя {login} не произошло.")
            return None

    except Exception as e:
        logger.error(f"❌ Ошибка при обновлении имени/отчества для {login}: {e}")
        raise

    finally:
        if conn:
            await conn.close()

# === 9. Установка роли админа по логину ===
async def set_admin_role(login: str, is_admin: bool):
    """
    Устанавливает статус админа для пользователя по логину.

    :param login: Логин пользователя
    :param is_admin: True — сделать админом, False — снять роль
    :return: True, если обновление прошло успешно
    """
    conn = None
    try:
        conn = await connect_to_db()

        # Проверяем, существует ли пользователь
        existing = await conn.fetchval(
            "SELECT 1 FROM users WHERE login = $1",
            login
        )
        if not existing:
            logger.warning(f"Попытка установить роль админа для несуществующего пользователя: {login}")
            raise ValueError(f"Пользователь с логином '{login}' не найден.")

        # Обновляем поле admin
        result = await conn.execute(
            "UPDATE users SET admin = $1 WHERE login = $2",
            is_admin,
            login
        )

        if result == "UPDATE 0":
            logger.warning(f"Обновление роли для пользователя {login} не произошло.")
            raise RuntimeError("Ошибка при обновлении роли.")
        else:
            role_status = "стал админом" if is_admin else "потерял роль админа"
            logger.info(f"🛡️ Пользователь {login} {role_status}.")
            return True

    except Exception as e:
        logger.error(f"❌ Ошибка при установке роли админа для {login}: {e}")
        raise

    finally:
        if conn:
            await conn.close()

# === 10. Обновление роли пользователя ===
async def update_user_role(login: str, new_role: str):
    """
    Обновляет роль пользователя.

    :param login: Логин пользователя
    :param new_role: Новая роль пользователя
    :return: True, если обновление прошло успешно
    """
    conn = None
    try:
        conn = await connect_to_db()

        # Проверяем, существует ли пользователь
        existing = await conn.fetchval(
            "SELECT 1 FROM users WHERE login = $1",
            login
        )
        if not existing:
            logger.warning(f"Попытка обновить роль для несуществующего пользователя: {login}")
            raise ValueError(f"Пользователь с логином '{login}' не найден.")

        # Обновляем поле role
        result = await conn.execute(
            "UPDATE users SET role = $1 WHERE login = $2",
            new_role,
            login
        )

        if result == "UPDATE 0":
            logger.warning(f"Обновление роли для пользователя {login} не произошло.")
            raise RuntimeError("Ошибка при обновлении роли.")
        else:
            logger.info(f"🏷️ Роль пользователя {login} изменена на: {new_role}")
            return True

    except Exception as e:
        logger.error(f"❌ Ошибка при обновлении роли для {login}: {e}")
        raise

    finally:
        if conn:
            await conn.close()