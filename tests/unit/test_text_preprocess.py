from services.ingest.text_preprocess import clean_for_embedding


def test_clean_for_embedding_removes_html_urls_and_spaces():
    dirty = "<p>Hello   world</p> https://example.com\n\nnext"
    cleaned = clean_for_embedding(dirty)
    assert "<p>" not in cleaned
    assert "https://example.com" not in cleaned
    assert "  " not in cleaned
    assert cleaned.startswith("Hello world")
