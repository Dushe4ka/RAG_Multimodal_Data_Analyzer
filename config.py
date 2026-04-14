from dotenv import load_dotenv
import os
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()

class Settings(BaseSettings):
    # Данные для работы с PostgreSQL
    DATABASE_USER:str
    DATABASE_PASSWORD:str
    DATABASE_NAME:str
    DATABASE_HOST:str
    DATABASE_PORT:str
    DATABASE_URL: str = ""
    # Данные для векторизации
    QDRANT_URL:str
    DENSE_MODEL_PROVIDER:str
    SPARSE_MODEL_NAME:str
    USE_SPARSE:bool
    # BGE-M3 (локально, FlagEmbedding); при DENSE_MODEL_PROVIDER=bge_m3
    BGE_M3_MODEL: str = Field(default="BAAI/bge-m3")
    BGE_M3_USE_FP16: bool = Field(default=True)
    # Multivector ColBERT в Qdrant (только с bge_m3 + sparse_backend bgem3 при USE_SPARSE)
    VECTOR_USE_COLBERT: bool = Field(default=False)
    # Данные для работы с JWT
    SECRET_KEY:str
    ALGORITHM:str
    # Данные для работы с LLM
    LLM_API_URL:str
    LLM_API_KEY:str
    AGENT_LLM_PROVIDER: str = "openai"
    OPENAI_API_KEY:str
    OPENAI_MODEL:str
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_MODEL: str = "deepseek-chat"
    OLLAMA_CHAT_MODEL: str = "qwen2.5:7b"
    # Данные для работы с MongoDB
    MONGODB_URL_DEV:str
    MONGODB_URL_PROD:str
    # MinIO / S3
    S3_ENDPOINT: str = "localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET_UPLOADS: str = "uploads"
    S3_SECURE: bool = False
    S3_PRESIGNED_EXPIRE_SEC: int = 3600
    # Tika
    TIKA_URL: str = "http://localhost:9998"
    TIKA_TIMEOUT_SEC: float = 120.0
    TIKA_MAX_RETRIES: int = 3
    # Ingest/chunking
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    UPLOAD_MAX_FILE_MB: int = 100
    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_VISION_MODEL: str = "qwen2.5vl:7b"
    OLLAMA_TIMEOUT_SEC: float = 120.0
    # ASR / video preprocessing
    WHISPER_MODEL_SIZE: str = "small"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"
    WHISPER_BEAM_SIZE: int = 5
    FFMPEG_BIN: str = "ffmpeg"

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
    )

settings=Settings()

def get_db_url():
    return (
        f"postgresql+asyncpg://{settings.DATABASE_USER}:{settings.DATABASE_PASSWORD}@"
        f"{settings.DATABASE_HOST}:{settings.DATABASE_PORT}/{settings.DATABASE_NAME}"
    )


def get_memory_db_url():
    """
    URL для LangGraph PostgresSaver/PostgresStore через psycopg.
    Важно: psycopg не понимает диалектный суффикс '+asyncpg'.
    """
    return (
        f"postgresql://{settings.DATABASE_USER}:{settings.DATABASE_PASSWORD}@"
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