from dotenv import load_dotenv
import os
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()

class Settings(BaseSettings):
    # Данные для работы с PostgreSQL
    DATABASE_USER:str
    DATABASE_PASSWORD:str
    DATABASE_NAME:str
    DATABASE_HOST:str
    DATABASE_PORT:str
    # Данные для векторизации
    QDRANT_URL:str
    DENSE_MODEL_PROVIDER:str
    SPARSE_MODEL_NAME:str
    USE_SPARSE:bool
    # Данные для работы с JWT
    SECRET_KEY:str
    ALGORITHM:str
    # Данные для работы с LLM
    LLM_API_URL:str
    LLM_API_KEY:str
    OPENAI_API_KEY:str
    OPENAI_MODEL:str
    # Данные для работы с MongoDB
    MONGODB_URL_DEV:str
    MONGODB_URL_PROD:str

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
    )

settings=Settings()

def get_db_url():
    return (
        f"postgresql+asyncpg://{settings.DATABASE_USER}:{settings.DATABASE_PASSWORD}@"
        f"{settings.DATABASE_HOST}:{settings.DATABASE_PORT}/{settings.DATABASE_NAME}"
    )

    
def get_auth_data():
    return {"secret_key": settings.SECRET_KEY, "algorithm": settings.ALGORITHM}

def get_llm_data():
    return {"api_url": settings.LLM_API_URL, "api_key": settings.LLM_API_KEY}

# class Settings_LLM(BaseSettings):
#     QWEN_THINK:str
#     QWEN_THINK_URL:str
#     QWEN_INSTRUCT:str
#     QWEN_INSTRUCT_URL:str

# settings_llm=Settings_LLM()

# print(settings.ALGORITHM, settings.DATABASE_HOST, settings.DATABASE_USER, settings.DATABASE_NAME, settings.DATABASE_PASSWORD, settings.DATABASE_PORT, settings.SECRET_KEY)
# print(get_auth_data())