from database.postgresql.users import ( create_user,
                            create_users_table, 
                            ensure_admin_exists, 
                            get_all_users,
                            delete_user,
                            get_user_by_login,
                            update_name_surname,
                            update_password,
                            set_admin_role,
                            )
import asyncio

async def init_db():
    """
    Создаем юзера, выводим в консоль, изменяем ему ИМЯ и ФМ, выводим, изменяем пароль, выводим, изменяем роль на админа, удаляем
    """
    # # 1
    # await create_user(
    #     login="test1",
    #     password="test123",
    #     name="awda",
    #     surname="dawai"
    # )
    # # 2
    # test_user = await get_user_by_login(login="test1")
    # print(test_user)
    # # 3
    # await update_name_surname(
    #     login="test1",
    #     name="success1",
    #     surname="success2"
    # )
    # # 4
    # test_user = await get_user_by_login(login="test1")
    # print(test_user)
    # # 5
    # await update_password(
    #     login="test1",
    #     new_password="success123"
    # )
    # # 6
    # test_user = await get_user_by_login(login="test1")
    # print(test_user)
    # # 7
    # await set_admin_role(
    #     login="test1",
    #     is_admin=True
    # )
    # 8 
    await delete_user(login="admin")
    # 9 
    await get_user_by_login(login="test1")

if __name__ == "__main__":
    asyncio.run(init_db())