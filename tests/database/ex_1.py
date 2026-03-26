from database.postgresql.users import ( create_user,
                            create_users_table, 
                            ensure_admin_exists, 
                            get_all_users,
                            delete_user,
                            get_user_by_login,
                            update_name_surname,
                            update_password)
import asyncio

async def init_db():
    """
    Инициализирует базу данных: создаёт таблицу и админа.
    Вызывается при старте приложения.
    """
    # await create_users_table()

    # await ensure_admin_exists()

    # users = await get_all_users()
    # print(users)

    

if __name__ == "__main__":
    asyncio.run(init_db())