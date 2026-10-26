"""Integration tests for AI Advisor Providers (Gemini, OpenAI, Anthropic, Ollama)."""

import httpx
import pytest

from wealth_pilot.adapters.ai.llm_client import UniversalAIAdvisorClient


@pytest.mark.asyncio
async def test_ai_fallback_algorithmic():
    client = UniversalAIAdvisorClient(provider="gemini", api_key="")
    res = await client.generate_advice(prompt="Net worth: € 100.000")
    assert "Paslood Strategic Review" in res
    assert "Balance Sheet Strength" in res


@pytest.mark.asyncio
async def test_ai_call_gemini():
    async def gemini_mock(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("x-goog-api-key") == "test-gemini-key"
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": "Gemini Strategic Advice: Keep buying core ETFs."}]
                        }
                    }
                ]
            },
        )

    transport = httpx.MockTransport(gemini_mock)
    async with httpx.AsyncClient(transport=transport) as http_client:
        ai_client = UniversalAIAdvisorClient(
            provider="gemini", api_key="test-gemini-key", model="gemini-2.5-flash"
        )
        res = await ai_client._call_gemini(
            http_client, prompt="Review my portfolio", system_prompt="You are an advisor"
        )
        assert "Gemini Strategic Advice" in res


@pytest.mark.asyncio
async def test_ai_call_openai():
    async def openai_mock(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-openai-key"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": "OpenAI Advice: Accelerate mortgage repayment."}}
                ]
            },
        )

    transport = httpx.MockTransport(openai_mock)
    async with httpx.AsyncClient(transport=transport) as http_client:
        ai_client = UniversalAIAdvisorClient(
            provider="openai", api_key="test-openai-key", model="gpt-4o-mini"
        )
        res = await ai_client._call_openai(
            http_client, prompt="Review my debts", system_prompt="Be concise"
        )
        assert "OpenAI Advice" in res


@pytest.mark.asyncio
async def test_ai_call_anthropic():
    async def anthropic_mock(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "test-claude-key"
        return httpx.Response(
            200,
            json={
                "content": [{"text": "Anthropic Advice: Your asset allocation drift is balanced."}]
            },
        )

    transport = httpx.MockTransport(anthropic_mock)
    async with httpx.AsyncClient(transport=transport) as http_client:
        ai_client = UniversalAIAdvisorClient(
            provider="anthropic", api_key="test-claude-key", model="claude-3-5-haiku-20241022"
        )
        res = await ai_client._call_anthropic(
            http_client, prompt="Review my buckets", system_prompt=None
        )
        assert "Anthropic Advice" in res


@pytest.mark.asyncio
async def test_ai_call_ollama():
    async def ollama_mock(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": "Ollama Local Advice: Rebalance Gold."})

    transport = httpx.MockTransport(ollama_mock)
    async with httpx.AsyncClient(transport=transport) as http_client:
        ai_client = UniversalAIAdvisorClient(
            provider="ollama",
            api_key="",
            model="llama3",
            base_url="http://localhost:11434/api/generate",
        )
        res = await ai_client._call_ollama(http_client, prompt="Review cashflow")
        assert "Ollama Local Advice" in res


@pytest.mark.asyncio
async def test_ollama_live_models_discovery():
    import respx

    with respx.mock:
        respx.get("http://localhost:11434/api/tags").respond(
            200,
            json={
                "models": [
                    {
                        "name": "qwen2.5-coder:7b",
                        "model": "qwen2.5-coder:7b",
                        "details": {"family": "qwen2", "parameter_size": "7.6B"},
                    },
                    {
                        "name": "gemma4-128k:12b-mlx",
                        "model": "gemma4-128k:12b-mlx",
                        "details": {"family": "", "parameter_size": ""},
                    },
                ]
            },
        )
        models = await UniversalAIAdvisorClient.fetch_available_models(
            provider="ollama", base_url="http://localhost:11434"
        )
        assert len(models) == 2
        assert models[0]["id"] == "qwen2.5-coder:7b"
        assert models[0]["recommended"] is True
        assert "7.6B" in models[0]["description"]
        assert models[1]["id"] == "gemma4-128k:12b-mlx"
        assert models[1]["recommended"] is False


@pytest.mark.asyncio
async def test_ollama_fallback_when_unreachable():
    import respx

    with respx.mock:
        respx.get("http://localhost:11434/api/tags").respond(500)
        models = await UniversalAIAdvisorClient.fetch_available_models(
            provider="ollama", base_url="http://localhost:11434"
        )
        assert any(m["id"] == "llama3.2" for m in models)


@pytest.mark.asyncio
async def test_ollama_404_model_not_found():
    import respx

    with respx.mock:
        respx.post("http://localhost:11434/api/generate").respond(
            404,
            json={"error": "model 'llama3.2' not found"},
        )
        client = UniversalAIAdvisorClient(
            provider="ollama",
            model="llama3.2",
            base_url="http://localhost:11434",
        )
        with pytest.raises(RuntimeError, match="model 'llama3.2' not found"):
            await client.generate_advice(prompt="Advise")


@pytest.mark.asyncio
async def test_ollama_connection_error():
    import respx

    with respx.mock:
        respx.post("http://localhost:11434/api/generate").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        client = UniversalAIAdvisorClient(
            provider="ollama",
            model="qwen2.5-coder:7b",
            base_url="http://localhost:11434",
        )
        with pytest.raises(RuntimeError, match="Cannot connect to Ollama"):
            await client.generate_advice(prompt="Advise")


@pytest.mark.asyncio
async def test_anthropic_live_models_and_error_detail():
    import respx

    with respx.mock:
        respx.get("https://api.anthropic.com/v1/models").respond(
            200,
            json={
                "data": [
                    {"id": "claude-sonnet-4-20250514", "display_name": "Claude Sonnet 4"},
                    {"id": "claude-3-7-sonnet-latest", "display_name": "Claude 3.7 Sonnet"},
                ]
            },
        )
        models = await UniversalAIAdvisorClient.fetch_available_models(
            provider="anthropic", api_key="sk-ant-test-key"
        )
        assert any(m["id"] == "claude-sonnet-4-20250514" for m in models)

        # Test that Anthropic 404/400 error returns detailed message
        respx.post("https://api.anthropic.com/v1/messages").respond(
            404,
            json={"error": {"type": "not_found_error", "message": "model: claude-old not found"}},
        )
        client = UniversalAIAdvisorClient(
            provider="anthropic", api_key="sk-ant-test-key", model="claude-old"
        )
        with pytest.raises(RuntimeError, match="Anthropic API error"):
            await client.generate_advice(prompt="Test")
