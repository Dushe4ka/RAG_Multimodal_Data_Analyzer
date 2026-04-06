import pytest

from services.ingest.pipeline import IngestPipeline


class DummyTika:
    async def extract_text(self, content: bytes, filename: str):
        return "Hello from tika", {"filename": filename}


class DummyVectorStore:
    def __init__(self):
        self.called = False

    def add_documents(self, texts, payloads, chunk_options):
        self.called = True
        assert len(texts) == 1
        assert payloads[0]["workspace_id"] == "ws-1"


@pytest.mark.asyncio
async def test_pipeline_indexes_text(monkeypatch):
    pipeline = IngestPipeline(collection_name="workspace_ws-1")
    pipeline.tika = DummyTika()
    dummy_vector = DummyVectorStore()
    pipeline.vector_store = dummy_vector

    result = await pipeline.process_and_index(
        content=b"doc",
        filename="a.pdf",
        content_type="application/pdf",
        workspace_id="ws-1",
        file_id="f-1",
        object_key="ws-1/a.pdf",
    )
    assert result["status"] == "indexed"
    assert dummy_vector.called is True
