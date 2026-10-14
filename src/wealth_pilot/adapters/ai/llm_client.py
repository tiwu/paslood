"""Pluggable AI LLM Advisor Client (Gemini, OpenAI, Anthropic, Ollama)."""

from __future__ import annotations

import os
from typing import Any

import httpx

from wealth_pilot.adapters.ai.base import BaseAIAdvisorClient


class UniversalAIAdvisorClient(BaseAIAdvisorClient):
    """Connects to user-selected LLM provider using their private API key."""

    def __init__(
        self,
        provider: str = "gemini",
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.provider = provider.lower()
        self.api_key = (
            api_key
            or os.getenv("AI_API_KEY")
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or ""
        )
        self.model = model or ("gemini-2.5-flash" if self.provider == "gemini" else "gpt-4o-mini")
        self.base_url = base_url

    async def generate_advice(self, prompt: str, system_prompt: str | None = None) -> str:
        if not self.api_key and self.provider != "ollama":
            return self._generate_fallback_algorithmic_review(prompt)

        async with httpx.AsyncClient(timeout=30.0) as client:
            if self.provider == "gemini":
                return await self._call_gemini(client, prompt, system_prompt)
            elif self.provider == "openai":
                return await self._call_openai(client, prompt, system_prompt)
            elif self.provider == "anthropic":
                return await self._call_anthropic(client, prompt, system_prompt)
            elif self.provider == "ollama":
                return await self._call_ollama(client, prompt)
            else:
                return await self._call_openai(client, prompt, system_prompt)

    async def _call_gemini(
        self, client: httpx.AsyncClient, prompt: str, system_prompt: str | None
    ) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        contents: list[dict[str, Any]] = []
        if system_prompt:
            contents.append(
                {"role": "user", "parts": [{"text": f"SYSTEM INSTRUCTION: {system_prompt}"}]}
            )
            contents.append(
                {
                    "role": "model",
                    "parts": [{"text": "Understood. I will act as your Strategic Wealth Advisor."}],
                }
            )
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        resp = await client.post(url, json={"contents": contents})
        resp.raise_for_status()
        data = resp.json()
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                return parts[0].get("text", "")
        return "No response generated from Gemini."

    async def _call_openai(
        self, client: httpx.AsyncClient, prompt: str, system_prompt: str | None
    ) -> str:
        url = self.base_url or "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        resp = await client.post(
            url, headers=headers, json={"model": self.model, "messages": messages}
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")

    async def _call_anthropic(
        self, client: httpx.AsyncClient, prompt: str, system_prompt: str | None
    ) -> str:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model or "claude-3-5-haiku-20241022",
            "max_tokens": 1500,
            "system": system_prompt or "You are a financial wealth advisor.",
            "messages": [{"role": "user", "content": prompt}],
        }
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data.get("content", [{}])[0].get("text", "")

    async def _call_ollama(self, client: httpx.AsyncClient, prompt: str) -> str:
        url = self.base_url or "http://localhost:11434/api/generate"
        resp = await client.post(
            url, json={"model": self.model or "llama3", "prompt": prompt, "stream": False}
        )
        resp.raise_for_status()
        return resp.json().get("response", "")

    def _generate_fallback_algorithmic_review(self, prompt: str) -> str:
        return (
            "### 🤖 Wealth Pilot Strategic Review (Algorithmic Summary)\n\n"
            "*Notice: Configure your AI API Key (Gemini, OpenAI, or Anthropic) in settings to unlock customized generative commentary.*\n\n"
            "**Key Observations & Recommendations:**\n"
            "- **Balance Sheet Strength**: Your emergency cash buffer and investment assets form a resilient foundation.\n"
            "- **Debt Servicing**: Maintain required monthly payments on low fixed-rate mortgages. If any debt APR exceeds 5-6%, prioritize paying it off before voluntary investments.\n"
            "- **Bucket Alignment**: Direct your monthly surplus to underweight buckets (buy-only rebalancing) to minimize portfolio tracking error without triggering tax or broker fees.\n"
            "- **Long-Term Compounding**: Continue regular monthly contributions to harness the power of exponential growth toward your financial independence milestones."
        )
