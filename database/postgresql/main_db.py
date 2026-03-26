import asyncpg
import asyncio
from config import DATABASE_HOST, DATABASE_NAME, DATABASE_PASSWORD, DATABASE_PORT, DATABASE_USER
from setup_logger import setup_logger

logger = setup_logger("database", log_file="database.log")

async def connect_to_db():
    conn = await asyncpg.connect(
        user=DATABASE_USER,
        password=DATABASE_PASSWORD,
        database=DATABASE_NAME,
        host=DATABASE_HOST,  # или IP
        port=DATABASE_PORT
    )
    return conn
