from datetime import datetime, timedelta
from typing import Optional
from jose import jwt
from fastapi import Cookie, HTTPException, Depends, status
from config import settings
from database.mongodb.main import db
from setup_logger import setup_logger
from passlib.context import CryptContext

logger = setup_logger("utils", log_file="server.log")

async def create_jwt_token(user_id: str):
    """
    Создание JWT токена валидного 1 час
    если токен валидный и его срок жизни не подошел 
    к концу — мы будем возвращать айди пользователя, 
    иначе выбрасываем ошибку.
    """
    expire = datetime.now() + timedelta(hours=1)
    payload = {
        "sub": str(user_id),
        "exp": expire.timestamp(),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return token

async def verify_jwt_token(token: str):
    """
    Проверяет валидность JWT-токена и его срок действия.

    Args:
        token (str): JWT-токен для проверки

    Returns:
        str: ID пользователя из токена, если токен валиден

    Raises:
        HTTPException: При истечении срока действия токена (401)
        HTTPException: При недействительном токене (401)

    Пример использования:
        user_id = await verify_jwt_token("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")

    Обработка:
        - Декодирует JWT-токен с использованием секретного ключа
        - Проверяет срок действия токена
        - Возвращает user_id из поля "sub" токена
        - Выбрасывает соответствующую ошибку при невалидности
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user(
    access_token: Optional[str] = Cookie(default=None),
):
    """
    Проверяет авторизацию пользователя по JWT-токену из cookies.

    Args:
        access_token (Optional[str]): Токен доступа из cookies, по умолчанию None

    Returns:
        int: ID пользователя, если токен валиден

    Raises:
        HTTPException: При отсутствии токена (401)
        HTTPException: При недействительном или просроченном токене (401)

    Пример использования:
        current_user_id = await get_current_user()

    Обработка:
        - Извлекает токен из cookies
        - Проверяет наличие токена
        - Выполняет валидацию токена через verify_jwt_token()
        - Возвращает ID пользователя при успешной авторизации
        - Выбрасывает ошибку при отсутствии токена или его недействительности
    """
    if not access_token:
        raise HTTPException(status_code=401, detail="Missing token")
    user_id = await verify_jwt_token(access_token)
    return user_id


async def get_optional_current_user(
    access_token: Optional[str] = Cookie(default=None),
) -> Optional[int]:
    """
    Опциональная проверка авторизации пользователя по JWT-токену.

    Args:
        access_token (Optional[str]): Токен доступа из cookies, по умолчанию None

    Returns:
        Optional[int]: ID пользователя, если токен валиден, иначе None

    Пример использования:
        current_user_id = await get_optional_current_user()

    Обработка:
        - Извлекает токен из cookies
        - Если токен отсутствует - возвращает None
        - Проверяет валидность токена через verify_jwt_token()
        - Возвращает ID пользователя при успешной авторизации
        - Возвращает None при отсутствии токена или его недействительности
        - Используется для необязательной авторизации (например, в веб-интерфейсе)
    """
    if not access_token:
        return None
    try:
        user_id = await verify_jwt_token(access_token)
        return user_id
    except Exception:
        return None
    
async def check_user_admin(user_id: str):
    """
    Проверка у пользователя прав админа
    """
    try:
        await db.ensure_connection()
        user = await db.get_user_by_user_id(user_id=user_id)
        if user["admin"] == True:
            logger.info(f"Пользователь {user['login']} является админом")
            return True
        else:
            logger.info(f"Пользователь {user['login']} не является админом")
            return False
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при проверке пользователя на админа: {e}")

async def get_current_admin_user(user_id: str = Depends(get_current_user)):
    response = await check_user_admin(user_id=user_id)
    if response:
        return user_id
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Недостаточно прав!')
