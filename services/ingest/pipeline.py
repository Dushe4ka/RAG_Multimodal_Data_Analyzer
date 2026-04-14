from __future__ import annotations

from ai.vector.embed_model import EmbedModel
from ai.vector.vector_store import VectorStore
from config import settings
from services.extract.tika_service import TikaService
from services.ingest.media_to_text import audio_to_text, image_to_text_via_ollama, video_to_text
from services.ingest.text_preprocess import clean_for_embedding
from services.ingest.type_detector import detect_media_type


class IngestPipeline:
    def __init__(self, collection_name: str):
        self.tika = TikaService()
        self.vector_store = VectorStore(
            collection_name=collection_name,
            embed_model=EmbedModel(provider=settings.DENSE_MODEL_PROVIDER),
            qdrant_url=settings.QDRANT_URL,
            use_sparse=settings.USE_SPARSE,
            sparse_model_name=settings.SPARSE_MODEL_NAME,
        )

    async def process_and_index(
        self,
        *,
        content: bytes,
        filename: str,
        content_type: str,
        workspace_id: str,
        file_id: str,
        object_key: str,
    ) -> dict:
        media_type = detect_media_type(content_type=content_type, filename=filename)
        if media_type == "text":
            raw_text, metadata = await self.tika.extract_text(content=content, filename=filename)
        elif media_type == "image":
            raw_text, metadata = await image_to_text_via_ollama(content=content, filename=filename)
        elif media_type == "audio":
            raw_text, metadata = await audio_to_text(content=content, filename=filename)
        elif media_type == "video":
            raw_text, metadata = await video_to_text(content=content, filename=filename)
        else:
            raw_text, metadata = "", {"source": "unsupported"}

        cleaned = clean_for_embedding(raw_text)
        if not cleaned:
            return {
                "status": "error",
                "media_type": media_type,
                "metadata": metadata,
                "error": "empty_text_after_extraction",
            }
        payload = {
            "workspace_id": workspace_id,
            "file_id": file_id,
            "source": filename,
            "object_key": object_key,
            "media_type": media_type,
        }
        self.vector_store.add_documents(
            texts=[cleaned],
            payloads=[payload],
            chunk_options={"chunk_size": settings.CHUNK_SIZE, "chunk_overlap": settings.CHUNK_OVERLAP},
        )
        return {"status": "indexed", "media_type": media_type, "metadata": metadata, "text_size": len(cleaned)}
