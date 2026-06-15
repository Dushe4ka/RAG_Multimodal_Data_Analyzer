from __future__ import annotations

from typing import Any


def _source_key(source: dict[str, Any]) -> str:
    """Уникальный ключ источника: один файл — одна запись в списке."""
    file_id = source.get("file_id")
    if file_id:
        return f"file:{file_id}"
    object_key = source.get("object_key")
    if object_key:
        return f"object:{object_key}"
    name = source.get("source")
    if name:
        return f"name:{name}"
    download_url = source.get("download_url")
    if download_url:
        return f"url:{download_url}"
    return f"text:{hash(source.get('text') or '')}"


def dedupe_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Объединяет чанки одного файла в один источник.
    При дубликатах оставляет запись с наибольшим score.
    """
    best: dict[str, dict[str, Any]] = {}
    for source in sources:
        key = _source_key(source)
        current_score = float(source.get("score") or 0)
        prev = best.get(key)
        if prev is None or current_score > float(prev.get("score") or 0):
            best[key] = source
    return sorted(best.values(), key=lambda item: float(item.get("score") or 0), reverse=True)


def hits_to_sources(hits: list[dict[str, Any]], *, minio_service: Any | None = None) -> list[dict[str, Any]]:
    """Преобразует Qdrant hits в список источников для API."""
    sources: list[dict[str, Any]] = []
    for hit in hits:
        payload = hit.get("payload", {}) or {}
        source: dict[str, Any] = {
            "file_id": payload.get("file_id"),
            "workspace_id": payload.get("workspace_id"),
            "object_key": payload.get("object_key"),
            "score": hit.get("score"),
            "text": payload.get("text", ""),
            "source": payload.get("source"),
            "media_type": payload.get("media_type"),
        }
        object_key = payload.get("object_key")
        if object_key and minio_service is not None:
            source["download_url"] = minio_service.presigned_get_url(object_key)
        sources.append(source)
    return sources
