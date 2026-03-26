from langchain_core.embeddings import Embeddings
import httpx
import asyncio
from typing import List, Union, Optional

class UniversalEmbeddings(Embeddings):
    def __init__(self, api_url: str, model_name: str = "/Qwen3-Embedding-0.6B-f16.gguf"):
        """
        Инициализация класса

        Args:
            api_url (str): URL API сервера
            model_name (str): Название модели для использования (по умолчанию - Qwen3)
        """
        self.api_url = api_url
        self.model_name = model_name

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Возвращает энбеддинги для списка текстов"""
        return asyncio.run(self._embed_async(texts))

    async def _embed_async(self, texts: List[str]) -> List[List[float]]:
        async with httpx.AsyncClient() as client:
            tasks = [
                client.post(
                    f"{self.api_url}/v1/embeddings",
                    json={"input": text, "model": self.model_name}
                ) for text in texts
            ]
            responses = await asyncio.gather(*tasks)
            return [response.json()["data"][0]["embedding"] for response in responses]

    def embed_query(self, text: str) -> List[float]:
        """Возвращает энбеддинг для одного текста"""
        return asyncio.run(self._embed_single(text))

    async def _embed_single(self, text: str) -> List[float]:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/v1/embeddings",
                json={"input": text, "model": self.model_name}
            )
            return response.json()["data"][0]["embedding"]

    def set_model(self, model_name: str):
        """
        Установка новой модели для использования

        Args:
            model_name (str): Название новой модели
        """
        self.model_name = model_name

    def get_model(self) -> str:
        """
        Получение текущей модели

        Returns:
            str: Текущее название модели
        """
        return self.model_name

# Примеры использования:

# 1. Использование с дефолтной моделью
embeddings = UniversalEmbeddings("http://192.168.0.104:8082")

# 2. Использование с конкретной моделью
# embeddings = UniversalEmbeddings("http://192.168.0.104:8082", "/my-custom-model.gguf")

# 3. Изменение модели во время выполнения
# embeddings.set_model("/another-model.gguf")

# 4. Получение текущей модели
current_model = embeddings.get_model()
print(f"Текущая модель: {current_model}")

# Проверяем работу
try:
    result = embeddings.embed_query("Привет, мир!")
    print("Энбеддинг:", len(result), "мер")
    print("Первые 5 значений:", result[:5])
except Exception as e:
    print("Ошибка:", e)