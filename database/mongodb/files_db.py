import asyncio
import uuid
from datetime import datetime, timezone
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient

from config import settings


class AsyncWorkspaceFilesDatabase:
    _instance: Optional["AsyncWorkspaceFilesDatabase"] = None
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
                self._collection = self._db["workspace_files"]
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
        await self._collection.create_index("file_id", unique=True)
        await self._collection.create_index([("workspace_id", 1), ("created_at", -1)])
        await self._collection.create_index("owner_user_id")

    async def create_file_record(
        self,
        workspace_id: str,
        owner_user_id: str,
        filename: str,
        media_type: str,
        object_key: str,
        content_type: str,
        size_bytes: int,
        extraction_status: str = "pending",
        extra_metadata: Optional[dict] = None,
    ):
        await self.ensure_connection()
        doc = {
            "file_id": str(uuid.uuid4()),
            "workspace_id": workspace_id,
            "owner_user_id": owner_user_id,
            "filename": filename,
            "media_type": media_type,
            "object_key": object_key,
            "content_type": content_type,
            "size_bytes": size_bytes,
            "extraction_status": extraction_status,
            "metadata": extra_metadata or {},
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        await self._collection.insert_one(doc)
        return doc

    async def set_extraction_status(self, file_id: str, extraction_status: str, metadata: Optional[dict] = None):
        await self.ensure_connection()
        update = {"extraction_status": extraction_status, "updated_at": datetime.now(timezone.utc)}
        if metadata is not None:
            update["metadata"] = metadata
        result = await self._collection.update_one({"file_id": file_id}, {"$set": update})
        return result.modified_count > 0

    async def list_workspace_files(self, workspace_id: str):
        await self.ensure_connection()
        cursor = self._collection.find({"workspace_id": workspace_id}).sort("created_at", -1)
        return await cursor.to_list(length=None)

    async def get_file(self, file_id: str):
        await self.ensure_connection()
        return await self._collection.find_one({"file_id": file_id})
