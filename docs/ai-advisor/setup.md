# AI Financial Advisor Setup

Paslood features a server-side AI advisory layer that provides qualitative assessments of macro financial plans.

---

## Privacy-Preserving Architecture

```mermaid
flowchart LR
    subgraph LocalHost["Local Paslood Instance (Private)"]
        DATA["Raw Balance Sheet & Ledger<br/>(IBANs, Accounts, Real Balances)"]
        ANON["Anonymization & Aggregation Layer<br/>Strips Account Numbers, Names, Identifiers"]
        METRICS["Aggregated Financial Metrics<br/>(Asset Totals, Debt APRs, Drift %, Surplus)"]
        VAULT["SecretVault (AES-256-GCM)<br/>Decrypts API Key In-Memory Only"]
    end

    subgraph Providers["Supported LLM Providers"]
        GEMINI["Google Gemini API"]
        OPENAI["OpenAI API"]
        CLAUDE["Anthropic Claude API"]
        OLLAMA["Local Ollama (100% Offline)"]
    end

    DATA --> ANON
    ANON --> METRICS
    METRICS --> AI_DISPATCH["Secure Server-Side Dispatch"]
    VAULT --> AI_DISPATCH
    AI_DISPATCH -->|TLS Request with Anonymized Metrics| Providers
    Providers -->|Strategic Narrative Advice| UI["Web Dashboard & CLI"]
```

---

## Supported Providers

| Provider | Supported Models | Key Management | Privacy Scope |
| :--- | :--- | :--- | :--- |
| **Google Gemini** *(Recommended)* | `gemini-2.0-flash`, `gemini-1.5-pro` | Encrypted in `SecretVault` | Anonymized metrics payload only |
| **Anthropic Claude** | `claude-3-5-sonnet`, `claude-3-5-haiku` | Encrypted in `SecretVault` | Anonymized metrics payload only |
| **OpenAI** | `gpt-4o`, `gpt-4o-mini` | Encrypted in `SecretVault` | Anonymized metrics payload only |
| **Local Ollama** | Any local model (e.g. `llama3`, `mistral`) | No API key required | **100% offline local inference** |

---

## Configuration

API keys can be supplied via environment variables or entered directly into the Web Dashboard under **Settings $\rightarrow$ AI Advisor**:

```bash
# Optional environment variables
export GEMINI_API_KEY="your-gemini-key"
export ANTHROPIC_API_KEY="your-anthropic-key"
export OPENAI_API_KEY="your-openai-key"
export OLLAMA_HOST="http://localhost:11434"
```

All credentials entered through the UI are encrypted at rest with AES-256-GCM using per-tenant keys derived via HKDF-SHA256.
