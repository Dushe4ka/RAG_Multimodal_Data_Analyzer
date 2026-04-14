from ai.llm.rag_agent.tools import run_smart_search


class DummyVectorStore:
    def __init__(self):
        self.calls = []

    def search(self, query, limit, mode, query_filter):
        self.calls.append(query)
        if "подробности" in query:
            return [
                {"score": 0.81, "payload": {"file_id": "f1", "object_key": "o1", "text": "A"}},
                {"score": 0.79, "payload": {"file_id": "f2", "object_key": "o2", "text": "B"}},
            ]
        return [{"score": 0.2, "payload": {"file_id": "f1", "object_key": "o1", "text": "A"}}]


def test_run_smart_search_dedup_and_trace():
    store = DummyVectorStore()
    hits, trace = run_smart_search(
        vector_store=store,
        query="test query",
        workspace_id="ws1",
        iterations=3,
        extra_queries=2,
    )
    assert len(trace) >= 1
    assert len(hits) >= 1
    keys = {(h["payload"].get("file_id"), h["payload"].get("object_key")) for h in hits}
    assert len(keys) == len(hits)
