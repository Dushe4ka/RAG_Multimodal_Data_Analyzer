"""
Tika Service.
Text extraction using Apache Tika server.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional, Tuple

import httpx

from config import settings


class TikaService:
    def __init__(
        self,
        server_url: str = settings.TIKA_URL,
        timeout: float = settings.TIKA_TIMEOUT_SEC,
        max_retries: int = settings.TIKA_MAX_RETRIES,
    ):
        self.server_url = server_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(self.timeout))
        return self._client

    async def extract_text(self, content: bytes, filename: str) -> Tuple[str, Dict[str, Any]]:
        client = await self._get_client()
        content_type = self._guess_content_type(filename)
        headers = {"Content-Type": content_type, "Accept": "text/plain"}
        metadata: Dict[str, Any] = {}

        for attempt in range(self.max_retries):
            try:
                response = await client.put(f"{self.server_url}/tika", content=content, headers=headers)
                response.raise_for_status()
                text = response.text
                meta_response = await client.put(
                    f"{self.server_url}/meta",
                    content=content,
                    headers={"Content-Type": content_type, "Accept": "application/json"},
                )
                if meta_response.status_code == 200:
                    metadata = meta_response.json()
                return text, metadata
            except Exception:
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(2**attempt)

        return "", metadata

    async def detect_mime_type(self, content: bytes) -> str:
        client = await self._get_client()
        try:
            response = await client.put(
                f"{self.server_url}/detect/stream",
                content=content,
                headers={"Content-Type": "application/octet-stream"},
            )
            response.raise_for_status()
            return response.text.strip()
        except Exception:
            return "application/octet-stream"

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def _guess_content_type(self, filename: str) -> str:
        ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
        mapping = {
            "pdf": "application/pdf",
            "doc": "application/msword",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "txt": "text/plain",
            "md": "text/markdown",
            "html": "text/html",
            "xml": "application/xml",
            "json": "application/json",
            "csv": "text/csv",
        }
        return mapping.get(ext, "application/octet-stream")
