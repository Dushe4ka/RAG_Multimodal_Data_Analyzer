from langchain_core.tools import tool
import asyncio
import os
from faker import Faker
from langchain_mcp_adapters.client import MultiServerMCPClient


@tool
async def add(a: int, b: int) -> int:
    """Складывает два целых числа и возвращает результат."""
    await asyncio.sleep(0.1)
    return a + b


@tool
async def list_files() -> list:
    """Возвращает список файлов в текущей папке."""
    await asyncio.sleep(0.1)
    return os.listdir("..")


@tool
async def get_random_user_name(gender: str) -> str:
    """
    Возвращает случайное мужское или женское имя в зависимости от условия:
    male - мужчина, female - женщина
    """
    faker = Faker("ru_RU")
    gender = gender.lower()
    if gender == "male":
        return f"{faker.first_name_male()} {faker.last_name_male()}"
    return f"{faker.first_name_female()} {faker.last_name_female()}"

async def get_custom_tools():
    custom_tools = [get_random_user_name, list_files, add]
    return custom_tools