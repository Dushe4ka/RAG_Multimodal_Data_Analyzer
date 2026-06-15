from __future__ import annotations

from typing import Any, Literal

from services.ingest.pipeline import IngestPipeline
from services.storage.minio_service import MinioService

FailedStage = Literal["extraction", "indexing", "full"]


def infer_failed_stage(metadata: dict[str, Any] | None) -> FailedStage:
    """Определяет, на каком этапе ingest остановился."""
    meta = metadata or {}
    explicit = meta.get("failed_stage")
    if explicit in {"extraction", "indexing", "full"}:
        return explicit

    error = str(meta.get("error") or "")
    if meta.get("extracted_text"):
        return "indexing"
    if error == "empty_text_after_extraction":
        return "extraction"
    return "full"


def resolve_reprocess_stage(metadata: dict[str, Any] | None) -> FailedStage:
    """
    Этап для повторной обработки:
    - indexing — только Qdrant/эмбеддинги, если текст уже сохранён;
    - extraction — заново извлечь текст и проиндексировать;
    - full — полный цикл (скачать из MinIO → extract → index).
    """
    stage = infer_failed_stage(metadata)
    if stage == "indexing" and not (metadata or {}).get("extracted_text"):
        return "full"
    return stage


def stage_label(stage: FailedStage) -> str:
    labels = {
        "indexing": "индексация",
        "extraction": "извлечение текста",
        "full": "полная обработка",
    }
    return labels[stage]


async def reprocess_workspace_file(*, file_doc: dict[str, Any]) -> tuple[str, dict[str, Any], FailedStage]:
    """
    Повторяет только упавший этап ingest для уже загруженного файла.
    Возвращает (extraction_status, result_metadata, reprocess_stage).
    """
    metadata = file_doc.get("metadata") or {}
    stage = resolve_reprocess_stage(metadata)
    pipeline = IngestPipeline(collection_name=f"workspace_{file_doc['workspace_id']}")

    if stage == "indexing":
        extracted_text = metadata.get("extracted_text")
        if not extracted_text:
            stage = "full"
        else:
            try:
                result = pipeline.index_cleaned_text(
                    cleaned=extracted_text,
                    workspace_id=file_doc["workspace_id"],
                    file_id=file_doc["file_id"],
                    object_key=file_doc["object_key"],
                    filename=file_doc["filename"],
                    media_type=file_doc.get("media_type", "text"),
                    extraction_metadata=metadata.get("extraction_metadata") or {},
                )
                result["reprocess_stage"] = stage
                return "indexed", result, stage
            except Exception as exc:
                return "error", _indexing_error_result(
                    exc=exc,
                    file_doc=file_doc,
                    extraction_metadata=metadata.get("extraction_metadata") or {},
                    extracted_text=extracted_text,
                ), stage

    minio = MinioService()
    if not minio.stat(file_doc["object_key"]):
        return "error", {
            "status": "error",
            "failed_stage": "storage",
            "error": "Файл отсутствует в MinIO. Загрузите его заново.",
        }, "full"

    content = minio.download_bytes(file_doc["object_key"])
    result = await pipeline.process_and_index(
        content=content,
        filename=file_doc["filename"],
        content_type=file_doc.get("content_type") or "application/octet-stream",
        workspace_id=file_doc["workspace_id"],
        file_id=file_doc["file_id"],
        object_key=file_doc["object_key"],
    )
    result["reprocess_stage"] = stage
    if result.get("status") == "indexed":
        return "indexed", result, stage
    if result.get("status") == "error":
        return "error", result, stage
    return "stub", result, stage


def _indexing_error_result(
    *,
    exc: Exception,
    file_doc: dict[str, Any],
    extraction_metadata: dict[str, Any],
    extracted_text: str,
) -> dict[str, Any]:
    return {
        "status": "error",
        "failed_stage": "indexing",
        "error": str(exc),
        "media_type": file_doc.get("media_type"),
        "metadata": extraction_metadata,
        "extracted_text": extracted_text,
    }
