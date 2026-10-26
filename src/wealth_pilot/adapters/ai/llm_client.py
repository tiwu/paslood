"""Pluggable AI LLM Advisor Client (Gemini, OpenAI, Anthropic, Ollama)."""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

from wealth_pilot.adapters.ai.base import BaseAIAdvisorClient

logger = logging.getLogger("wealth_pilot.ai")


class UniversalAIAdvisorClient(BaseAIAdvisorClient):
    """Connects to user-selected LLM provider using their private API key."""

    def __init__(
        self,
        provider: str = "gemini",
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        max_retries: int = 1,
    ) -> None:
        self.provider = provider.lower()
        if self.provider == "algorithmic":
            self.api_key = ""
        else:
            self.api_key = (
                api_key
                or os.getenv("AI_API_KEY")
                or os.getenv("GEMINI_API_KEY")
                or os.getenv("OPENAI_API_KEY")
                or os.getenv("ANTHROPIC_API_KEY")
                or ""
            )
        default_models = {
            "gemini": "gemini-2.5-flash",
            "anthropic": "claude-sonnet-4-20250514",
            "ollama": "llama3.2",
            "algorithmic": "algorithmic",
        }
        self.model = model or default_models.get(self.provider, "gpt-4o-mini")
        self.base_url = (
            base_url
            or os.getenv("OLLAMA_HOST")
            or os.getenv("OLLAMA_URL")
            or ("http://localhost:11434" if self.provider == "ollama" else None)
        )
        self.timeout = timeout
        self.max_retries = max_retries
        self.last_trace: dict[str, Any] = {}

    async def generate_advice(self, prompt: str, system_prompt: str | None = None) -> str:
        t0 = time.perf_counter()
        if self.provider == "algorithmic" or (not self.api_key and self.provider != "ollama"):
            advice = self._generate_fallback_algorithmic_review(prompt)
            duration = time.perf_counter() - t0
            self.last_trace = {
                "provider": "algorithmic"
                if self.provider == "algorithmic"
                else f"{self.provider}-fallback",
                "model": "deterministic-rules",
                "duration_s": round(duration, 3),
                "attempts": 1,
                "status": "success",
            }
            logger.info("Algorithmic review completed in %.3fs", duration)
            return advice

        base_timeout = self.timeout or (60.0 if self.provider == "ollama" else 30.0)
        total_attempts = self.max_retries + 1

        logger.info(
            "AI advice request started | provider=%s | model=%s | timeout=%.1fs | max_attempts=%d",
            self.provider,
            self.model,
            base_timeout,
            total_attempts,
        )

        for attempt in range(1, total_attempts + 1):
            attempt_timeout = base_timeout * (1.5 ** (attempt - 1))
            t_attempt_start = time.perf_counter()
            try:
                async with httpx.AsyncClient(timeout=attempt_timeout) as client:
                    if self.provider == "gemini":
                        res = await self._call_gemini(client, prompt, system_prompt)
                    elif self.provider == "openai":
                        res = await self._call_openai(client, prompt, system_prompt)
                    elif self.provider == "anthropic":
                        res = await self._call_anthropic(client, prompt, system_prompt)
                    elif self.provider == "ollama":
                        res = await self._call_ollama(client, prompt, system_prompt)
                    else:
                        res = await self._call_openai(client, prompt, system_prompt)

                duration = time.perf_counter() - t0
                self.last_trace = {
                    "provider": self.provider,
                    "model": self.model,
                    "duration_s": round(duration, 2),
                    "attempts": attempt,
                    "status": "success",
                }
                logger.info(
                    "AI provider '%s' succeeded in %.2fs (attempt %d/%d)",
                    self.provider,
                    duration,
                    attempt,
                    total_attempts,
                )
                return res

            except httpx.TimeoutException as exc:
                elapsed = time.perf_counter() - t_attempt_start
                if attempt < total_attempts:
                    logger.warning(
                        "AI provider '%s' timed out after %.1fs on attempt %d/%d. Retrying with extended timeout (%.1fs)...",
                        self.provider,
                        elapsed,
                        attempt,
                        total_attempts,
                        base_timeout * (1.5**attempt),
                    )
                else:
                    total_elapsed = time.perf_counter() - t0
                    self.last_trace = {
                        "provider": self.provider,
                        "model": self.model,
                        "duration_s": round(total_elapsed, 2),
                        "attempts": attempt,
                        "status": "timeout",
                    }
                    if self.provider == "ollama":
                        err_msg = (
                            f"Ollama request timed out after {round(total_elapsed, 1)}s ({attempt} attempts). "
                            f"The model '{self.model}' took too long to respond. It may still be loading into memory, "
                            f"or your machine is under heavy load. Please try again or select a smaller model."
                        )
                    else:
                        err_msg = (
                            f"{self.provider.capitalize()} API request timed out after {round(total_elapsed, 1)}s "
                            f"({attempt} attempts). Please try again."
                        )
                    logger.error("AI request timed out: %s", err_msg)
                    raise RuntimeError(err_msg) from exc

            except Exception as exc:
                total_elapsed = time.perf_counter() - t0
                self.last_trace = {
                    "provider": self.provider,
                    "model": self.model,
                    "duration_s": round(total_elapsed, 2),
                    "attempts": attempt,
                    "status": "error",
                }
                logger.error(
                    "AI provider '%s' failed on attempt %d/%d after %.2fs: %s",
                    self.provider,
                    attempt,
                    total_attempts,
                    total_elapsed,
                    exc,
                )
                raise

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
        cls,
        provider: str = "gemini",
        api_key: str | None = None,
        base_url: str | None = None,
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
            curated_anthropic = [
                {
                    "id": "claude-sonnet-4-20250514",
                    "name": "Claude Sonnet 4",
                    "description": "High-intelligence reasoning and financial analysis (Recommended)",
                    "recommended": True,
                },
                {
                    "id": "claude-3-7-sonnet-20250219",
                    "name": "Claude 3.7 Sonnet",
                    "description": "Advanced hybrid reasoning model",
                    "recommended": False,
                },
                {
                    "id": "claude-3-5-haiku-20241022",
                    "name": "Claude 3.5 Haiku",
                    "description": "Fast and cost-effective model",
                    "recommended": False,
                },
                {
                    "id": "claude-3-5-sonnet-20241022",
                    "name": "Claude 3.5 Sonnet",
                    "description": "Analytical intelligence model",
                    "recommended": False,
                },
            ]
            if api_key and "•" not in api_key:
                try:
                    headers = {
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                    }
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        resp = await client.get(
                            "https://api.anthropic.com/v1/models",
                            headers=headers,
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            live_models = []
                            for idx, m in enumerate(data.get("data", [])):
                                raw_id = m.get("id", "")
                                if raw_id:
                                    live_models.append(
                                        {
                                            "id": raw_id,
                                            "name": m.get("display_name") or raw_id,
                                            "description": "Live Anthropic model",
                                            "recommended": idx == 0 or "sonnet-4" in raw_id,
                                        }
                                    )
                            if live_models:
                                return live_models
                except Exception:
                    pass
            return curated_anthropic

        elif provider == "ollama":
            curated_ollama = [
                {
                    "id": "llama3.2",
                    "name": "Llama 3.2",
                    "description": "Local lightweight model (Default)",
                    "recommended": True,
                },
                {
                    "id": "qwen2.5-coder:7b",
                    "name": "Qwen 2.5 Coder 7B",
                    "description": "Code and financial reasoning model",
                    "recommended": False,
                },
                {
                    "id": "mistral",
                    "name": "Mistral 7B",
                    "description": "Local general purpose model",
                    "recommended": False,
                },
            ]
            host = (
                base_url
                or os.getenv("OLLAMA_HOST")
                or os.getenv("OLLAMA_URL")
                or "http://localhost:11434"
            ).rstrip("/")
            if host.endswith("/api/generate"):
                host = host.removesuffix("/api/generate")
            elif host.endswith("/api/tags"):
                host = host.removesuffix("/api/tags")

            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    resp = await client.get(f"{host}/api/tags")
                    if resp.status_code == 200:
                        data = resp.json()
                        models = data.get("models", [])
                        if models:
                            live_models = []
                            for idx, m in enumerate(models):
                                m_id = m.get("model") or m.get("name") or ""
                                if not m_id:
                                    continue
                                details = m.get("details") or {}
                                param_size = details.get("parameter_size") or ""
                                family = details.get("family") or ""
                                desc_parts = [p for p in [param_size, family, "local model"] if p]
                                desc = " ".join(desc_parts) if desc_parts else "Local Ollama model"
                                live_models.append(
                                    {
                                        "id": m_id,
                                        "name": m.get("name") or m_id,
                                        "description": desc,
                                        "recommended": idx == 0,
                                    }
                                )
                            if live_models:
                                return live_models
            except Exception:
                pass
            return curated_ollama

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
        if resp.is_error:
            try:
                err_data = resp.json()
                msg = err_data.get("error", {}).get("message", resp.text)
            except Exception:
                msg = resp.text
            raise RuntimeError(f"OpenAI API error ({resp.status_code}): {msg}")
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
            "model": self.model or "claude-sonnet-4-20250514",
            "max_tokens": 1500,
            "system": system_prompt or "You are a financial wealth advisor.",
            "messages": [{"role": "user", "content": prompt}],
        }
        resp = await client.post(url, headers=headers, json=payload)
        if resp.is_error:
            try:
                err_data = resp.json()
                msg = err_data.get("error", {}).get("message", resp.text)
            except Exception:
                msg = resp.text
            raise RuntimeError(f"Anthropic API error ({resp.status_code}): {msg}")
        data = resp.json()
        return data.get("content", [{}])[0].get("text", "")

    async def _call_ollama(
        self, client: httpx.AsyncClient, prompt: str, system_prompt: str | None = None
    ) -> str:
        host = (
            self.base_url
            or os.getenv("OLLAMA_HOST")
            or os.getenv("OLLAMA_URL")
            or "http://localhost:11434"
        ).rstrip("/")
        url = host if host.endswith("/api/generate") else f"{host}/api/generate"

        model_name = self.model or "llama3.2"
        payload: dict[str, Any] = {"model": model_name, "prompt": prompt, "stream": False}
        if system_prompt:
            payload["system"] = system_prompt
        try:
            resp = await client.post(url, json=payload)
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            raise RuntimeError(
                f"Cannot connect to Ollama at {url}. Make sure Ollama is running ('ollama serve')."
            ) from e

        if resp.is_error:
            try:
                err_data = resp.json()
                msg = err_data.get("error", resp.text)
            except Exception:
                msg = resp.text
            if resp.status_code == 404:
                raise RuntimeError(
                    f"Ollama error (404): model '{model_name}' not found. "
                    f"Run 'ollama pull {model_name}' or select an installed model from the dropdown."
                )
            raise RuntimeError(f"Ollama API error ({resp.status_code}): {msg}")

        return resp.json().get("response", "")

    def _generate_fallback_algorithmic_review(self, prompt: str) -> str:
        return (
            "### 🤖 Paslood Strategic Review (Algorithmic Summary)\n\n"
            "*Notice: Configure your AI API Key (Gemini, OpenAI, or Anthropic) in settings to unlock customized generative commentary.*\n\n"
            "**Key Observations & Recommendations:**\n"
            "- **Balance Sheet Strength**: Your emergency cash buffer and investment assets form a resilient foundation.\n"
            "- **Debt Servicing**: Maintain required monthly payments on low fixed-rate mortgages. If any debt APR exceeds 5-6%, prioritize paying it off before voluntary investments.\n"
            "- **Bucket Alignment**: Direct your monthly surplus to underweight buckets (buy-only rebalancing) to minimize portfolio tracking error without triggering tax or broker fees.\n"
            "- **Long-Term Compounding**: Continue regular monthly contributions to harness the power of exponential growth toward your financial independence milestones."
        )
