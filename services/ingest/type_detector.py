from __future__ import annotations


def detect_media_type(content_type: str, filename: str) -> str:
    ctype = (content_type or "").lower()
    name = (filename or "").lower()

    if ctype.startswith("image/") or name.endswith((".png", ".jpg", ".jpeg", ".webp")):
        return "image"
    if ctype.startswith("audio/") or name.endswith((".mp3", ".wav", ".m4a", ".ogg")):
        return "audio"
    if ctype.startswith("video/") or name.endswith((".mp4", ".mov", ".avi", ".mkv")):
        return "video"
    return "text"
