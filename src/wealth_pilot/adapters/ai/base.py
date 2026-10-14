"""Abstract Base AI Financial Advisor Client."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseAIAdvisorClient(ABC):
    """Contract for AI LLM providers (Gemini, OpenAI, Anthropic, Ollama)."""

    @abstractmethod
    async def generate_advice(self, prompt: str, system_prompt: str | None = None) -> str:
        """Query LLM provider and return markdown-formatted strategic advice."""
        pass
