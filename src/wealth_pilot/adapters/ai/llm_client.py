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
        clean_model = (self.model or "gemini-2.5-flash").removeprefix("models/")
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}:generateContent"
        )
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }
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

        resp = await client.post(url, headers=headers, json={"contents": contents})
        if resp.is_error:
            try:
                err_data = resp.json()
                msg = err_data.get("error", {}).get("message", resp.text)
            except Exception:
                msg = resp.text
            raise RuntimeError(f"Gemini API error ({resp.status_code}): {msg}")

        data = resp.json()
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                return parts[0].get("text", "")
        return "No response generated from Gemini."

    @classmethod
    async def fetch_available_models(
        cls, provider: str = "gemini", api_key: str | None = None
    ) -> list[dict[str, Any]]:
        """Queries or lists active models supported by the chosen AI provider."""
        provider = (provider or "gemini").lower()
        if provider == "gemini":
            curated_gemini = [
                {
                    "id": "gemini-2.5-flash",
                    "name": "Gemini 2.5 Flash",
                    "description": "Fastest and most capable model (Recommended)",
                    "recommended": True,
                },
                {
                    "id": "gemini-2.5-pro",
                    "name": "Gemini 2.5 Pro",
                    "description": "Advanced reasoning model for complex financial planning",
                    "recommended": False,
                },
                {
                    "id": "gemini-2.0-flash",
                    "name": "Gemini 2.0 Flash",
                    "description": "Ultra fast next-gen model",
                    "recommended": False,
                },
                {
                    "id": "gemini-1.5-flash",
                    "name": "Gemini 1.5 Flash",
                    "description": "High throughput model",
                    "recommended": False,
                },
                {
                    "id": "gemini-1.5-pro",
                    "name": "Gemini 1.5 Pro",
                    "description": "Deep reasoning model",
                    "recommended": False,
                },
            ]
            if api_key:
                try:
                    headers = {"x-goog-api-key": api_key}
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        resp = await client.get(
                            "https://generativelanguage.googleapis.com/v1beta/models",
                            headers=headers,
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            live_models = []
                            for m in data.get("models", []):
                                methods = m.get("supportedGenerationMethods", [])
                                if "generateContent" in methods:
                                    raw_id = m.get("name", "").removeprefix("models/")
                                    if "gemini" in raw_id:
                                        live_models.append(
                                            {
                                                "id": raw_id,
                                                "name": m.get("displayName") or raw_id,
                                                "description": m.get("description", ""),
                                                "recommended": "2.5-flash" in raw_id
                                                or "flash" in raw_id,
                                            }
                                        )
                            if live_models:
                                live_models.sort(key=lambda x: not x["recommended"])
                                return live_models
                except Exception:
                    pass
            return curated_gemini

        elif provider == "openai":
            return [
                {
                    "id": "gpt-4o-mini",
                    "name": "GPT-4o Mini",
                    "description": "Fast and intelligent multimodal model (Recommended)",
                    "recommended": True,
                },
                {
                    "id": "gpt-4o",
                    "name": "GPT-4o",
                    "description": "High-intelligence flagship model",
                    "recommended": False,
                },
                {
                    "id": "o3-mini",
                    "name": "o3-mini",
                    "description": "Advanced STEM and financial reasoning model",
                    "recommended": False,
                },
            ]

        elif provider == "anthropic":
            return [
                {
                    "id": "claude-3-5-haiku-20241022",
                    "name": "Claude 3.5 Haiku",
                    "description": "Ultra fast and cost-effective (Recommended)",
                    "recommended": True,
                },
                {
                    "id": "claude-3-5-sonnet-20241022",
                    "name": "Claude 3.5 Sonnet",
                    "description": "State-of-the-art analytical intelligence",
                    "recommended": False,
                },
            ]

        elif provider == "ollama":
            return [
                {
                    "id": "llama3.2",
                    "name": "Llama 3.2",
                    "description": "Local lightweight model (Recommended)",
                    "recommended": True,
                },
                {
                    "id": "llama3",
                    "name": "Llama 3 (8B)",
                    "description": "Local open source model",
                    "recommended": False,
                },
                {
                    "id": "mistral",
                    "name": "Mistral 7B",
                    "description": "Local general purpose model",
                    "recommended": False,
                },
            ]

        return [
            {
                "id": "algorithmic",
                "name": "Algorithmic Advisor",
                "description": "Local deterministic advice engine",
                "recommended": True,
            }
        ]

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
