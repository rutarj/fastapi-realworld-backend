import json

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.routes import agent as agent_module




pytestmark = pytest.mark.asyncio
class _FakeAIMessage:
    def __init__(self, content, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


class _FakeLLMWithTools:
    def __init__(self, tools):
        self._tools = tools
        # Call once: propose a tool call, then respond with natural language.
        self._invocation_count = 0

    async def ainvoke(self, messages):
        self._invocation_count += 1
        if self._invocation_count == 1:
            # First call: request a get_article tool call.
            return _FakeAIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call-1",
                        "name": "get_article",
                        "args": {"slug": "test-slug"},
                    }
                ],
            )

        # Second call: return a natural language answer.
        return _FakeAIMessage(
            content="Here is the article about tests.",
            tool_calls=[],
        )


class _FakeChatOpenAI:
    def __init__(self, *args, **kwargs):
        pass

    def bind_tools(self, tools):
        return _FakeLLMWithTools(tools)


async def test_agent_read_only_get_article(
    app: FastAPI,
    client: AsyncClient,
    test_article,
    monkeypatch,
) -> None:
    # Stub ChatOpenAI so CI does not hit the real OpenAI API.
    monkeypatch.setattr(agent_module, "ChatOpenAI", _FakeChatOpenAI)

    response = await client.post(
        app.url_path_for("agent:handle-query"),
        content=json.dumps({"query": "get the article test-slug"}),
    )

    assert response.status_code == 200
    payload = response.json()
    assert "response" in payload
    assert "article" not in payload  # we wrap tool results into tool_calls trace
    # ensure tool trace captured a get_article call
    assert payload["tool_calls"]
    first_call = payload["tool_calls"][0]
    assert first_call["tool"] == "get_article"
    assert first_call["args"]["slug"] == "test-slug"
