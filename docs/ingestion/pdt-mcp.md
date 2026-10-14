# PDT MCP Server Integration

Wealth Pilot connects directly to the **Portfolio Dividend Tracker (PDT)** MCP server over JSON-RPC.

---

## How it Works

1. The `PdtMcpGateway` queries the PDT MCP server tools:
   - `pdt-get-portfolio`: Returns aggregate net invested, current worth, and cash.
   - `pdt-get-portfolio-holdings`: Returns open positions, live prices, quantities, and cost basis.
   - `pdt-list-x-ray-holdings`: Provides look-through breakdown into underlying ETF holdings.
2. The responses are automatically converted into unified domain `Asset` entities.
3. Assets are mapped into your configured **Strategic Buckets** by ticker, ISIN, or asset class.

---

## Configuration

In `~/.wealth_pilot/portfolio.yaml` or environment variables:

```yaml
pdt_mcp:
  url: "http://localhost:3000/mcp"
  auth_token: "your-pdt-token"
```
