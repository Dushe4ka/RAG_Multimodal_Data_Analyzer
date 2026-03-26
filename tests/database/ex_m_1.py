from database.mongodb.main import db
import asyncio

async def main():
    # result = await client_db.get_all_users()
    await db.ensure_connection()
    await db.create_user(
        login="davidi",
        password="123",
        name="pavel",
        surname="golbi",
        role="user",
        admin=False
    )
    # a = await db.authenticate_user(
    #     login="davidi",
    #     password="123"
    # )
    # print(a)
    # await db.get_user_by_login(login="davidi")
    # await db.update_password(login="davidi", new_password="123")
    # await db.update_name_surname(login="davidi", name="success", surname="success")
    # await db.set_admin_role(login="davidi", is_admin=True)
    # await db.update_user_role(login="davidi", role="user")
    # await db.ensure_admin_exists()
    # await db.get_all_users()
    # await db.delete_user(login="davidi")
    # await db.drop_collection()
    # await db.close_connection()

if __name__ == "__main__":
    asyncio.run(main())