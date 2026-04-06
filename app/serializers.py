from __future__ import annotations

from datetime import datetime
from typing import Any

from bson import ObjectId


def to_jsonable(data: Any) -> Any:
    if isinstance(data, ObjectId):
        return str(data)
    if isinstance(data, datetime):
        return data.isoformat()
    if isinstance(data, dict):
        return {k: to_jsonable(v) for k, v in data.items() if k != "_id"}
    if isinstance(data, list):
        return [to_jsonable(item) for item in data]
    return data
