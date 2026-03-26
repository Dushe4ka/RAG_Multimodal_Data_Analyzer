from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Хешируем пароль
password = "admin"
hashed = pwd_context.hash(password)
print(f"Хеш: {hashed}")

# Проверяем пароль
is_valid = pwd_context.verify(password, hashed)
print(f"Пароль верен: {is_valid}")