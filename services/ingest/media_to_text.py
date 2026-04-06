from __future__ import annotations

import base64

import httpx

from config import settings


async def image_to_text_via_ollama(content: bytes, filename: str) -> str:
    """Извлекает текстовое описание изображения через Ollama vision."""
    image_b64 = base64.b64encode(content).decode("utf-8")
    payload = {
        "model": settings.OLLAMA_VISION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": f"Опиши подробно изображение {filename} и извлеки возможный текст.",
                "images": [image_b64],
            }
        ],
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=settings.OLLAMA_TIMEOUT_SEC) as client:
        response = await client.post(f"{settings.OLLAMA_BASE_URL}/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()
    message = data.get("message", {})
    return message.get("content", "")


async def audio_to_text_stub(_: bytes, filename: str) -> str:
    """
    Локальная заглушка ASR.
    Здесь оставлена точка расширения для whisper/faster-whisper.
    """
    return f"[ASR-STUB] Транскрипция для файла {filename} пока не реализована."
