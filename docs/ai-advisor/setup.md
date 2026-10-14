# AI Financial Advisor Setup

Wealth Pilot includes an optional **AI Financial Advisor** layer designed to provide qualitative, human-readable reviews of your macro financial plan.

---

## Bring Your Own API Key (BYO Key)

To guarantee complete privacy and zero markups, you provide your own API key from your preferred provider:

1. **Google Gemini (Recommended)**: Free or pay-as-you-go via [Google AI Studio](https://aistudio.google.com/).
2. **OpenAI**: GPT-4o / GPT-4o-mini via [platform.openai.com](https://platform.openai.com/).
3. **Anthropic**: Claude 3.5 Haiku / Sonnet via [console.anthropic.com](https://console.anthropic.com/).
4. **Local Ollama**: 100% offline local inference (no API key required).

---

## Configuration

You can enter your API key directly in the Web Dashboard under the **🤖 AI Advisor** tab, or export it in your environment:

```bash
# Example environment variables
export GEMINI_API_KEY="your-gemini-key"
# or
export OPENAI_API_KEY="your-openai-key"
```

---

## Privacy Protection

When an AI review is requested, Wealth Pilot:
- **Never** transmits your account numbers, bank identifiers, counterparty names, or personal identities.
- Sends **only** high-level aggregated metrics: total assets, total debt, debt APRs, bucket percentage deviations, and monthly cashflow surplus.
