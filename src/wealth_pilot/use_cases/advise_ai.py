"""Use Case: Advise AI (Generative Strategic Wealth Consultation)."""

from __future__ import annotations

from collections.abc import Sequence

from wealth_pilot.adapters.ai.base import BaseAIAdvisorClient
from wealth_pilot.domain.advice import AdviceItem
from wealth_pilot.domain.balance_sheet import BalanceSheet
from wealth_pilot.domain.bucket import BucketAllocationResult

SYSTEM_PROMPT = """You are Paslood AI, an experienced fee-only financial planner and strategic wealth advisor.
Your goal is to provide objective, mathematical, and actionable long-term financial guidance based strictly on the user's consolidated balance sheet metrics.
Focus on:
1. Macro asset allocation & bucket alignment (rebalancing with new cash vs selling).
2. Debt payoff optimization (comparing debt APR against expected compound equity returns).
3. Risk management & emergency cash reserves.
4. Belgian / European fiscal considerations when relevant (e.g. capital gains exemptions, wash sales).
Format your response in clean Markdown with concise sections and bullet points. Never give high-frequency trading advice or recommend specific speculative meme stocks."""


class AdviseAiUseCase:
    """Orchestrates structured, privacy-preserving financial prompt generation and AI advisory consultation."""

    def __init__(self, ai_client: BaseAIAdvisorClient) -> None:
        self.ai_client = ai_client

    async def execute(
        self,
        balance_sheet: BalanceSheet,
        allocations: Sequence[BucketAllocationResult],
        deterministic_advices: Sequence[AdviceItem],
        user_question: str | None = None,
    ) -> str:
        prompt = self._build_prompt(
            balance_sheet, allocations, deterministic_advices, user_question
        )
        return await self.ai_client.generate_advice(prompt=prompt, system_prompt=SYSTEM_PROMPT)

    def _build_prompt(
        self,
        bs: BalanceSheet,
        allocations: Sequence[BucketAllocationResult],
        advices: Sequence[AdviceItem],
        question: str | None,
    ) -> str:
        lines: list[str] = [
            "# Consolidated Financial Snapshot",
            f"- Total Assets: {bs.total_assets.format()}",
            f"- Total Liabilities (Debts): {bs.total_liabilities.format()}",
            f"- Net Worth: {bs.net_worth.format()}",
            f"- Debt-to-Asset Ratio: {bs.debt_to_asset_ratio:.1f}%",
            f"- Monthly Income: {bs.cashflow.monthly_income.format()}",
            f"- Monthly Debt Servicing: {bs.cashflow.debt_payments.format()}",
            f"- Monthly Free Cashflow Surplus: {bs.cashflow.free_monthly_cashflow.format()}",
            f"- Savings Rate: {bs.cashflow.savings_rate_pct:.1f}%",
            "",
            "## Strategic Allocation Buckets:",
        ]

        for a in allocations:
            lines.append(
                f"- {a.name}: Current {a.current_weight_pct:.1f}% (Target: {a.target_weight_pct:.1f}%), "
                f"Diff: € {a.diff_value:,.2f}, Status: {a.drift_status.value}"
            )

        if bs.liabilities:
            lines.append("\n## Active Liabilities:")
            for liab in bs.liabilities:
                lines.append(
                    f"- {liab.name}: Balance {liab.principal_balance.format()}, Rate {liab.interest_rate_pct:.2f}% APR, Payment {liab.monthly_payment.format()}/mo"
                )

        lines.append("\n## Algorithmic Engine Findings:")
        for adv in advices:
            lines.append(f"- [{adv.priority.value}] {adv.title}: {adv.message}")

        if question:
            lines.append(f"\n## User Question:\n{question}")
        else:
            lines.append(
                "\n## Request:\nProvide a high-level strategic review of this portfolio. "
                "Evaluate the asset allocation balance, debt vs investing prioritization, "
                "and advise on how to strategically deploy the monthly surplus over the next 12-36 months."
            )

        return "\n".join(lines)
