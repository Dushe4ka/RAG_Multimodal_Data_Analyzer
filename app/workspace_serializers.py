from __future__ import annotations

from typing import Any

from database.mongodb.async_db import AsyncUserDatabase


async def enrich_workspaces(
    workspaces: list[dict[str, Any]],
    *,
    users_db: AsyncUserDatabase,
    current_user_id: str,
) -> list[dict[str, Any]]:
    """Добавляет данные владельца и роль текущего пользователя."""
    owner_ids = {ws.get("owner_user_id") for ws in workspaces if ws.get("owner_user_id")}
    owners: dict[str, dict[str, Any]] = {}
    for owner_id in owner_ids:
        user = await users_db.get_user_by_user_id(owner_id)
        if user:
            owners[owner_id] = user

    enriched: list[dict[str, Any]] = []
    for ws in workspaces:
        owner = owners.get(ws.get("owner_user_id"), {})
        display_name = f"{owner.get('name', '')} {owner.get('surname', '')}".strip()
        item = {
            **ws,
            "owner_login": owner.get("login"),
            "owner_name": owner.get("name"),
            "owner_surname": owner.get("surname"),
            "owner_display_name": display_name or owner.get("login") or "Неизвестный автор",
            "is_owner": ws.get("owner_user_id") == current_user_id,
            "is_subscribed": (
                current_user_id in ws.get("member_user_ids", [])
                and ws.get("owner_user_id") != current_user_id
            ),
        }
        enriched.append(item)
    return enriched
