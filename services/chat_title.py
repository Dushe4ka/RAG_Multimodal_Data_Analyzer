from __future__ import annotations


def make_chat_title(message: str, *, max_len: int = 80) -> str:
    """Короткое название чата из первого сообщения пользователя."""
    text = " ".join(message.strip().split())
    if not text:
        return "Новый чат"
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"
