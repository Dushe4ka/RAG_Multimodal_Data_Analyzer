from __future__ import annotations

import asyncio
import base64
import os
import subprocess
import tempfile
from typing import Any, Optional

from faster_whisper import WhisperModel
from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama

from config import settings

_whisper_model: Optional[WhisperModel] = None


def _get_whisper_model() -> WhisperModel:
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = WhisperModel(
            model_size_or_path=settings.WHISPER_MODEL_SIZE,
            device=settings.WHISPER_DEVICE,
            compute_type=settings.WHISPER_COMPUTE_TYPE,
        )
    return _whisper_model


async def image_to_text_via_ollama(content: bytes, filename: str) -> tuple[str, dict[str, Any]]:
    """Извлекает текст из изображений через ChatOllama (langchain_ollama)."""
    image_b64 = base64.b64encode(content).decode("utf-8")
    llm = ChatOllama(
        model=settings.OLLAMA_VISION_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
        temperature=0.0,
        timeout=settings.OLLAMA_TIMEOUT_SEC,
    )
    response = await llm.ainvoke(
        [
            HumanMessage(
                content=[
                    {"type": "text", "text": f"Опиши изображение {filename} и извлеки весь читаемый текст."},
                    {"type": "image_url", "image_url": f"data:image/jpeg;base64,{image_b64}"},
                ]
            )
        ]
    )
    text = response.content if isinstance(response.content, str) else str(response.content)
    return text, {"source_model": settings.OLLAMA_VISION_MODEL, "modality": "image"}


def _transcribe_audio_file(audio_path: str) -> tuple[str, dict[str, Any]]:
    model = _get_whisper_model()
    segments, info = model.transcribe(
        audio_path,
        beam_size=settings.WHISPER_BEAM_SIZE,
    )
    text = " ".join(segment.text.strip() for segment in segments).strip()
    metadata = {
        "source_model": settings.WHISPER_MODEL_SIZE,
        "language": getattr(info, "language", None),
        "language_probability": getattr(info, "language_probability", None),
        "duration_sec": getattr(info, "duration", None),
        "modality": "audio",
    }
    return text, metadata


async def audio_to_text(content: bytes, filename: str) -> tuple[str, dict[str, Any]]:
    """Транскрибирует аудио через faster-whisper."""
    suffix = os.path.splitext(filename)[1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        return await asyncio.to_thread(_transcribe_audio_file, tmp_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


async def video_to_text(content: bytes, filename: str) -> tuple[str, dict[str, Any]]:
    """Извлекает аудио из видео через ffmpeg и транскрибирует через faster-whisper."""
    video_suffix = os.path.splitext(filename)[1] or ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=video_suffix) as src:
        src.write(content)
        src_path = src.name
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as dst:
        dst_path = dst.name

    try:
        cmd = [
            settings.FFMPEG_BIN,
            "-y",
            "-i",
            src_path,
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            dst_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        text, metadata = await asyncio.to_thread(_transcribe_audio_file, dst_path)
        metadata["modality"] = "video"
        metadata["source_video"] = filename
        return text, metadata
    finally:
        if os.path.exists(src_path):
            os.remove(src_path)
        if os.path.exists(dst_path):
            os.remove(dst_path)
