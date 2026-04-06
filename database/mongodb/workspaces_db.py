import asyncio
import uuid
from datetime import datetime, timezone
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient

from config import settings
from setup_logger import setup_logger

logger = setup_logger("workspaces_db", log_file="database.log")


class AsyncWorkspacesDatabase:
    _instance: Optional["AsyncWorkspacesDatabase"] = None
    _client: Optional[AsyncIOMotorClient] = None
    _db = None
    _collection = None
    _is_connected = False
    _lock = asyncio.Lock()

    def __new__(cls, connection_string=None, db_name="Diplom"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, connection_string=None, db_name="Diplom"):
        if not hasattr(self, "_initialized"):
            self.connection_string = connection_string or settings.MONGODB_URL_DEV
            self.db_name = db_name
            self._initialized = True

    async def connect(self):
        async with self._lock:
            if not self._is_connected:
                self._client = AsyncIOMotorClient(self.connection_string)
                self._db = self._client[self.db_name]
                self._collection = self._db["workspaces"]
                await self._create_indexes()
                self._is_connected = True

    async def disconnect(self):
        async with self._lock:
            if self._is_connected and self._client:
                self._client.close()
                self._is_connected = False

    async def ensure_connection(self):
        if not self._is_connected:
            await self.connect()

    async def _create_indexes(self):
        await self._collection.create_index("workspace_id", unique=True)
        await self._collection.create_index([("owner_user_id", 1), ("created_at", -1)])
        await self._collection.create_index("is_private")
        await self._collection.create_index("name")

    async def create_workspace(self, owner_user_id: str, name: str, is_private: bool):
        await self.ensure_connection()
        doc = {
            "workspace_id": str(uuid.uuid4()),
            "owner_user_id": owner_user_id,
            "name": name.strip(),
            "is_private": is_private,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "member_user_ids": [owner_user_id],
        }
        await self._collection.insert_one(doc)
        return doc

    async def list_owned(self, owner_user_id: str):
        await self.ensure_connection()
        cursor = self._collection.find({"owner_user_id": owner_user_id}).sort("updated_at", -1)
        return await cursor.to_list(length=None)

    async def list_library(self, user_id: str):
        await self.ensure_connection()
        cursor = self._collection.find({"member_user_ids": user_id}).sort("updated_at", -1)
        return await cursor.to_list(length=None)

    async def search_public(self, query: str):
        await self.ensure_connection()
        cursor = self._collection.find(
            {"is_private": False, "name": {"$regex": query, "$options": "i"}}
        ).sort("updated_at", -1)
        return await cursor.to_list(length=100)

    async def get_workspace(self, workspace_id: str):
        await self.ensure_connection()
        return await self._collection.find_one({"workspace_id": workspace_id})

    async def add_to_library(self, workspace_id: str, user_id: str):
        await self.ensure_connection()
        result = await self._collection.update_one(
            {"workspace_id": workspace_id, "is_private": False},
            {"$addToSet": {"member_user_ids": user_id}, "$set": {"updated_at": datetime.now(timezone.utc)}},
        )
        return result.modified_count > 0

    async def set_visibility(self, workspace_id: str, owner_user_id: str, is_private: bool):
        await self.ensure_connection()
        result = await self._collection.update_one(
            {"workspace_id": workspace_id, "owner_user_id": owner_user_id},
            {"$set": {"is_private": is_private, "updated_at": datetime.now(timezone.utc)}},
        )
        return result.modified_count > 0

    async def rename_workspace(self, workspace_id: str, owner_user_id: str, name: str):
        await self.ensure_connection()
        result = await self._collection.update_one(
            {"workspace_id": workspace_id, "owner_user_id": owner_user_id},
            {"$set": {"name": name.strip(), "updated_at": datetime.now(timezone.utc)}},
        )
        return result.modified_count > 0

    async def delete_workspace(self, workspace_id: str, owner_user_id: str):
        await self.ensure_connection()
        result = await self._collection.delete_one(
            {"workspace_id": workspace_id, "owner_user_id": owner_user_id}
        )
        return result.deleted_count > 0
