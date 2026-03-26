from fastapi import APIRouter, Depends, HTTPException, Response
from app.schemas import SUserAuth
from app.utils import get_current_user, get_current_admin_user
from database.mongodb.main import db

router = APIRouter(prefix="/admin")

@router.get("/get_all_users")
async def get_all_users(user_id: int = Depends(get_current_admin_user)):
    """
    Получение полного списка юзеров
    """
    users = await db.get_all_users()
    return users

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