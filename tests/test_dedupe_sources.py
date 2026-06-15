from services.sources import dedupe_sources


def test_dedupe_sources_by_file_id_keeps_best_score():
    sources = [
        {"file_id": "f1", "source": "news.mp4", "score": 0.5},
        {"file_id": "f1", "source": "news.mp4", "score": 0.9},
        {"file_id": "f2", "source": "doc.pdf", "score": 0.7},
    ]
    result = dedupe_sources(sources)
    assert len(result) == 2
    by_file = {item["file_id"]: item for item in result}
    assert by_file["f1"]["score"] == 0.9
    assert result[0]["file_id"] == "f1"
