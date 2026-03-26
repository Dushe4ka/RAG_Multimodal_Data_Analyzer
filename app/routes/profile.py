from fastapi import APIRouter, Depends, HTTPException, Response
from app.schemas import SUserAuth
from app.utils import create_jwt_token, get_current_user, get_current_admin_user
from database.mongodb.main import db

router = APIRouter(prefix="/profile")

@router.get("/")
async def profile(user_id: int = Depends(get_current_user)):
    """
    Личный профиль пользователя

    :param user_id: ID пользователя
    :return: 
        {
            "login": str,
            "admin": bool,
            "name": str,
            "surname": str,
            "role": str,
            "created_at": strftime('%d.%m.%Y')
        }
    """
    user = await db.profile_get_user_data(user_id=user_id)
    return user

@router.post("/edit_name_surname")
async def edit_name_surname(name: str = None, 
                            surname: str = None, 
                            user_id: int = Depends(get_current_user)):
    """
    Изменение имени и фамилии в профиле пользователем

    :param name: Имя пользователя
    :param surname: Фамилия пользователя
    :return {
                "login": str,
                "admin": bool,
                "name": str,
                "surname": str,
                "role": str,
                "created_at": strftime('%d.%m.%Y')
            }
    """
    result = await db.profile_update_name_surname(user_id=user_id, 
                                   name=name, 
                                   surname=surname)
    return result

@router.post("/edit_password")
async def edit_password(old_pwd: str,
                        new_pwd: str,
                        confirm_pwd: str,
                        user_id: int = Depends(get_current_user)):
    """
    Изменение пароля паользователем

    :param old_pwd: Старый пароль
    :param new_pwd: Новый пароль
    :param confirm_pwd: Подтверждение нового пароля
    :return bool
    """
    result = await db.update_password_modified(
        user_id=user_id,
        old_password=old_pwd,
        new_password=new_pwd,
        confirm_password=confirm_pwd
    )
    return result
