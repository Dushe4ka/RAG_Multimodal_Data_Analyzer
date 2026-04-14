from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.utils import get_current_admin_user
from database.mongodb.main import db

router = APIRouter(prefix="/admin")


class AdminCreateUserRequest(BaseModel):
    login: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=120)
    name: str = Field(default="", max_length=120)
    surname: str = Field(default="", max_length=120)
    role: str = Field(default="user", max_length=120)
    admin: bool = False


class AdminDeleteUserRequest(BaseModel):
    login: str = Field(min_length=1, max_length=120)

@router.get("/get_all_users")
async def get_all_users(user_id: int = Depends(get_current_admin_user)):
    """
    Получение полного списка юзеров
    """
    users = await db.get_all_users()
    return users


@router.post("/create_user")
async def create_user(
    payload: AdminCreateUserRequest,
    user_id: int = Depends(get_current_admin_user),
):
    """
    Создание нового пользователя администратором.
    """
    try:
        created_user = await db.create_user(
            login=payload.login,
            password=payload.password,
            name=payload.name,
            surname=payload.surname,
            role=payload.role,
            admin=payload.admin,
        )
        return await db.convert_user_for_api_response(created_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.post("/update_user_name_surname")
async def update_user_name_surname(login: str,
                                   name: str = None,
                                   surname: str = None,
                                   user_id: int = Depends(get_current_admin_user)):
    """
    Обновление имени и фамилии у пользователя по логину

    :param login: Логин пользователя
    :param name: Имя пользователя (новая)
    :param surname: Фамилия пользователя (новая)
    :return ...
    """
    result = await db.update_name_surname(
        login=login,
        name=name,
        surname=surname
    )
    return result

@router.post("/update_user_password")
async def update_user_password(login: str,
                               new_pwd: str,
                               user_id: int = Depends(get_current_admin_user)):
    """
    Обновление пароля у пользователя по логину

    :param login: Логин пользователя
    :param new_pwd: Новый пароль (новая)
    :return ...
    """
    result = await db.update_password(
        login=login,
        new_password=new_pwd
    )
    return result


@router.delete("/delete_user")
async def delete_user(
    payload: AdminDeleteUserRequest,
    user_id: int = Depends(get_current_admin_user),
):
    """
    Удаление пользователя администратором по логину.
    """
    try:
        await db.delete_user(login=payload.login)
        return {"status": "ok", "message": f"Пользователь '{payload.login}' удален"}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc