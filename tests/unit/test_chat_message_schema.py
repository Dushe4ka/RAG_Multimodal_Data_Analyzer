from app.schemas import ChatMessageRequest


def test_chat_message_schema_defaults():
    payload = ChatMessageRequest(message="hello")
    assert payload.smart_search is False
    assert payload.smart_iterations == 3
    assert payload.smart_extra_queries == 2
