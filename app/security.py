from setup_logger import setup_logger
from passlib.context import CryptContext

logger = setup_logger("utils", log_file="server.log")

# Контекст для хэширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def get_password_hash(password: str):
    try:
        result = pwd_context.hash(password)
        logger.info("Успешно Хэширован пароль")
        return result
    except Exception as e:
        logger.error(f"Не удалось хэшировать: {e}")        
        
async def verify_password(plain_password: str, hashed_password: str):
    try:
        logger.info("Верификация прошла безошибочно")
        result = pwd_context.verify(plain_password, hashed_password)
        logger.info("Верификация прошла безошибочно")
        return result
    except Exception as e:
        logger.error(f"Ошибка в ходе верификации: {e}")
        