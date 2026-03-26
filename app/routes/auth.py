from fastapi import APIRouter, Depends, HTTPException, Response
from app.schemas import SUserAuth
from app.utils import create_jwt_token, get_current_user, get_current_admin_user
from database.mongodb.main import db

router = APIRouter()

@router.post("/login")
async def login(
    response: Response,
    user_data: SUserAuth,
):
    """
    На вход принимаем логин с паролем. 
    Если все проверки пройдены, то создаем JWT-токен, который 
    помещается в куки-сессию.
    """
    await db.ensure_connection()
    user = await db.authenticate_user(user_data.login, user_data.password)
    await db.close_connection()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = await create_jwt_token(user["user_id"])
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=False,  # Включить True в проде (HTTPS)
        samesite="lax",
        max_age=3600,
        path="/",
    )
    return {"message": "Logged in"}

@router.post("/logout")
async def logout(response: Response):
    """
    Метод для выхода из сессии
    """
    response.delete_cookie("access_token")
    return {"message": "Logged out"}

@router.get("/protected")
async def protected_route(user_id: int = Depends(get_current_user)):
    """
    Проверка авторизации
    """
    user = await db.get_user_by_user_id(user_id=user_id)
    return {"message": f"Привет, пользователь {user['login']}!"}

@router.get("/protected_admin")
async def protected_admin_route(user_id: int = Depends(get_current_admin_user)):
    """
    Проверка авторизации
    """
    user = await db.get_user_by_user_id(user_id=user_id)
    return {"message": f"Привет, админ) {user['login']}!"}