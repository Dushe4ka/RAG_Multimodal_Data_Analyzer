from fastapi import FastAPI
# from server.routes.auth import login, admin, profile
from app.routes import auth, profile, admin
from database.mongodb.main import db
from contextlib import asynccontextmanager
from setup_logger import setup_logger

logger = setup_logger("main-server", log_file="server.log")

# Создаем lifespan-менеджер
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        logger.info("Инициализация базы данных...")
        await db.connect()
        await db.ensure_admin_exists()
        logger.info("База данных инициализирована успешно")
    except Exception as e:
        logger.error(f"Ошибка инициализации базы данных: {e}")
        raise

    yield

    # Shutdown 
    logger.info("Приложение завершено")
    await db.disconnect()  # Закрываем соединение при завершении

# Создаем FastAPI приложение с lifespan
app = FastAPI(
    title="RAG Chat System",
    description="Система с RAG, чатами и авторизацией",
    version="1.0.0",
    lifespan=lifespan  # Используем lifespan вместо on_event
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(profile.router)

@app.get("/")
async def root():
    return {"message": "RAG Chat System API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)