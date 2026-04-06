# Создание глобального объекта класса БД (с пуллом соединений)

from database.mongodb.async_db import AsyncUserDatabase
from database.mongodb.chats_db import AsyncChatsDatabase
from database.mongodb.workspaces_db import AsyncWorkspacesDatabase
from database.mongodb.files_db import AsyncWorkspaceFilesDatabase

db = AsyncUserDatabase()
chats_db = AsyncChatsDatabase()
workspaces_db = AsyncWorkspacesDatabase()
workspace_files_db = AsyncWorkspaceFilesDatabase()