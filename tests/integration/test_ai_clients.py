"""Integration tests for AI Advisor Providers (Gemini, OpenAI, Anthropic, Ollama)."""

import httpx
import pytest

from wealth_pilot.adapters.ai.llm_client import UniversalAIAdvisorClient


@pytest.mark.asyncio
async def test_ai_fallback_algorithmic():
    client = UniversalAIAdvisorClient(provider="gemini", api_key="")
    res = await client.generate_advice(prompt="Net worth: € 100.000")
    assert "Wealth Pilot Strategic Review" in res
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
