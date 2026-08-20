"""
Tests for the Flask app. All provider calls are mocked — running this
suite never hits Groq/Gemini/OpenRouter/HF/Pollinations, so it costs
nothing against your free-tier quotas and works even with an empty .env.

Run with:
    pytest
"""

import pytest

import app as flaskapp
import db


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Point the DB at a throwaway file for each test so tests never touch
    # your real chat_history.db.
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test_chat_history.db"))
    flaskapp.app.config["TESTING"] = True
    db.init_db()
    db.init_usage_table()
    with flaskapp.app.test_client() as c:
        yield c


@pytest.fixture
def conversation(client):
    """Creates a real conversation and returns its id — most routes need
    a valid conversation_id, not just any string."""
    r = client.post("/api/conversations", json={"browser_id": "test-browser"})
    return r.get_json()["conversation"]["id"]


def test_index_loads(client):
    r = client.get("/")
    assert r.status_code == 200


def test_create_and_list_conversations(client):
    r = client.post("/api/conversations", json={"browser_id": "b1", "title": "Chat A"})
    assert r.status_code == 200
    conv = r.get_json()["conversation"]
    assert conv["title"] == "Chat A"

    r = client.get("/api/conversations?browser_id=b1")
    assert r.status_code == 200
    assert len(r.get_json()["conversations"]) == 1


def test_rename_and_set_persona(client, conversation):
    r = client.patch(f"/api/conversations/{conversation}", json={"title": "Renamed"})
    assert r.status_code == 200
    assert r.get_json()["conversation"]["title"] == "Renamed"

    r = client.patch(f"/api/conversations/{conversation}", json={"system_prompt": "Be terse."})
    assert r.get_json()["conversation"]["system_prompt"] == "Be terse."


def test_delete_conversation(client, conversation):
    r = client.delete(f"/api/conversations/{conversation}")
    assert r.status_code == 200
    r = client.get(f"/api/history?conversation_id={conversation}")
    assert r.get_json()["messages"] == []


def test_history_starts_empty(client, conversation):
    r = client.get(f"/api/history?conversation_id={conversation}")
    assert r.status_code == 200
    assert r.get_json()["messages"] == []


def test_chat_requires_conversation_id(client):
    r = client.post("/api/chat", json={"message": "hi"})
    assert r.status_code == 400


def test_chat_requires_message(client, conversation):
    r = client.post("/api/chat", json={"conversation_id": conversation})
    assert r.status_code == 400


def test_chat_success_with_mocked_provider(client, conversation, monkeypatch):
    monkeypatch.setattr(
        flaskapp.providers, "CHAT_CHAIN",
        [("mock", lambda messages, system_prompt=None, image=None: "mocked reply")],
    )
    r = client.post("/api/chat", json={"conversation_id": conversation, "message": "hi"})
    assert r.status_code == 200
    data = r.get_json()
    assert data["reply"] == "mocked reply"
    assert data["provider"] == "mock"


def test_chat_falls_through_to_second_provider(client, conversation, monkeypatch):
    def failing(messages, system_prompt=None, image=None):
        raise RuntimeError("first provider down")

    monkeypatch.setattr(
        flaskapp.providers, "CHAT_CHAIN",
        [("broken", failing), ("backup", lambda messages, system_prompt=None, image=None: "backup reply")],
    )
    r = client.post("/api/chat", json={"conversation_id": conversation, "message": "hi"})
    assert r.status_code == 200
    assert r.get_json()["provider"] == "backup"


def test_chat_all_providers_failing_returns_502(client, conversation, monkeypatch):
    def failing(messages, system_prompt=None, image=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(flaskapp.providers, "CHAT_CHAIN", [("mock", failing)])
    r = client.post("/api/chat", json={"conversation_id": conversation, "message": "hi"})
    assert r.status_code == 502


def test_image_requires_prompt(client, conversation):
    r = client.post("/api/image", json={"conversation_id": conversation, "prompt": ""})
    assert r.status_code == 400


def test_image_success_with_mocked_provider(client, conversation, monkeypatch):
    monkeypatch.setattr(
        flaskapp.providers, "IMAGE_CHAIN",
        [("mock-img", lambda prompt: b"fake-image-bytes")],
    )
    r = client.post("/api/image", json={"conversation_id": conversation, "prompt": "a cat"})
    assert r.status_code == 200
    data = r.get_json()
    assert data["provider"] == "mock-img"
    assert "image_base64" in data


def test_history_persists_and_clears(client, conversation, monkeypatch):
    monkeypatch.setattr(
        flaskapp.providers, "CHAT_CHAIN",
        [("mock", lambda messages, system_prompt=None, image=None: "hey there")],
    )
    client.post("/api/chat", json={"conversation_id": conversation, "message": "hi"})

    r = client.get(f"/api/history?conversation_id={conversation}")
    assert len(r.get_json()["messages"]) == 2  # user message + assistant reply

    client.post("/api/history/clear", json={"conversation_id": conversation})
    r = client.get(f"/api/history?conversation_id={conversation}")
    assert r.get_json()["messages"] == []


def test_delete_last_messages_for_edit_flow(client, conversation, monkeypatch):
    monkeypatch.setattr(
        flaskapp.providers, "CHAT_CHAIN",
        [("mock", lambda messages, system_prompt=None, image=None: "reply")],
    )
    client.post("/api/chat", json={"conversation_id": conversation, "message": "hi"})
    r = client.post("/api/history/delete_last", json={"conversation_id": conversation, "count": 1})
    assert r.status_code == 200
    r = client.get(f"/api/history?conversation_id={conversation}")
    assert len(r.get_json()["messages"]) == 1  # only the user message remains


def test_chat_stream_success_with_mocked_provider(client, conversation, monkeypatch):
    class FakeStreamResponse:
        def iter_lines(self):
            yield b'data: {"choices":[{"delta":{"content":"Hel"}}]}'
            yield b'data: {"choices":[{"delta":{"content":"lo"}}]}'
            yield b"data: [DONE]"

    monkeypatch.setattr(
        flaskapp.providers, "STREAM_CHAIN",
        [("mock-stream", lambda messages, system_prompt=None, image=None: FakeStreamResponse(),
          flaskapp.providers.extract_openai_chunk)],
    )
    r = client.post("/api/chat/stream", json={"conversation_id": conversation, "message": "hi"})
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "mock-stream" in body
    assert "Hel" in body
    assert "lo" in body


def test_chat_regenerate_replaces_last_reply(client, conversation, monkeypatch):
    replies = iter(["first reply", "second reply"])

    class FakeStreamResponse:
        def __init__(self, text):
            self._text = text

        def iter_lines(self):
            yield f'data: {{"choices":[{{"delta":{{"content":"{self._text}"}}}}]}}'.encode()
            yield b"data: [DONE]"

    def opener(messages, system_prompt=None, image=None):
        return FakeStreamResponse(next(replies))

    monkeypatch.setattr(
        flaskapp.providers, "STREAM_CHAIN",
        [("mock-stream", opener, flaskapp.providers.extract_openai_chunk)],
    )
    client.post("/api/chat/stream", json={"conversation_id": conversation, "message": "hi"}).get_data()
    r = client.post("/api/chat/regenerate", json={"conversation_id": conversation})
    body = r.get_data(as_text=True)
    assert "second reply" in body

    r = client.get(f"/api/history?conversation_id={conversation}")
    assistant_messages = [m for m in r.get_json()["messages"] if m["role"] == "assistant"]
    assert len(assistant_messages) == 1  # old reply was replaced, not appended
    assert assistant_messages[0]["content"] == "second reply"


def test_vision_message_saved_with_vision_kind(client, conversation, monkeypatch):
    monkeypatch.setattr(
        flaskapp.providers, "CHAT_CHAIN",
        [("mock", lambda messages, system_prompt=None, image=None: "I see a red square")],
    )
    r = client.post("/api/chat", json={
        "conversation_id": conversation,
        "message": "what is this?",
        "image": {"mime_type": "image/png", "data": "AAAA"},
    })
    assert r.status_code == 200

    r = client.get(f"/api/history?conversation_id={conversation}")
    kinds = [m["kind"] for m in r.get_json()["messages"]]
    assert "vision" in kinds


def test_usage_endpoint(client):
    r = client.get("/api/usage")
    assert r.status_code == 200
    body = r.get_json()
    assert "today" in body


def test_tool_calling_executes_real_calculator(client, conversation, monkeypatch):
    """Confirms the tool-call loop actually runs the real calculator tool
    (not a mocked result) and feeds it back for a final answer."""
    first_response = {
        "choices": [{"message": {
            "role": "assistant", "content": None,
            "tool_calls": [{"id": "call_1", "type": "function",
                "function": {"name": "calculator", "arguments": '{"expression": "6 * 7"}'}}],
        }}]
    }
    second_response = {
        "choices": [{"message": {"role": "assistant", "content": "6 * 7 is 42.", "tool_calls": None}}]
    }
    responses = iter([first_response, second_response])

    def fake_tool_chat(messages, system_prompt=None, tools=None, model=None):
        return next(responses)

    monkeypatch.setattr(flaskapp.providers, "TOOL_CHAT_CHAIN", [("mock", fake_tool_chat)])
    r = client.post("/api/chat/tools", json={"conversation_id": conversation, "message": "what is 6*7?"})
    assert r.status_code == 200
    data = r.get_json()
    assert data["reply"] == "6 * 7 is 42."
    assert data["tool_calls"][0]["result"] == "42"  # the real calculator ran, not a mock
