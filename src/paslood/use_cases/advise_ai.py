"""Use Case: Advise AI (Generative Strategic Wealth Consultation)."""

from __future__ import annotations

import re
from collections.abc import Sequence

from paslood.domain.advice import AdviceItem
from paslood.domain.balance_sheet import BalanceSheet
from paslood.domain.bucket import BucketAllocationResult
from paslood.use_cases.ports import AIAdvisorPort

MAX_QUESTION_LENGTH = 1000
_INJECTION_PATTERNS = re.compile(
    r"(ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules)|"
    r"disregard\s+(all\s+)?(previous|prior)\s+(instructions|prompts)|"
    r"you\s+are\s+now\s+a|forget\s+your\s+system\s+prompt)",
    re.IGNORECASE,
)

SYSTEM_PROMPT = """You are Paslood AI, an experienced fee-only financial planner and strategic wealth advisor.
Your goal is to provide objective, mathematical, and actionable long-term financial guidance based strictly on the user's consolidated balance sheet metrics.
Focus on:
1. Macro asset allocation & bucket alignment (rebalancing with new cash vs selling).
2. Debt payoff optimization (comparing debt APR against expected compound equity returns).
3. Risk management & emergency cash reserves.
4. Belgian / European fiscal considerations when relevant (e.g. capital gains exemptions, wash sales).
Format your response in clean Markdown with concise sections and bullet points. Never give high-frequency trading advice or recommend specific speculative meme stocks.
Domain Guardrail: You must remain strictly within the domain of personal finance, wealth strategy, tax planning, and life/spending scenarios that impact the user's balance sheet. If the user asks about a non-financial topic (e.g. entertainment, trivia, coding, general chat), do NOT answer the general trivia; instead, briefly state that as Paslood AI you only provide financial strategy, and if applicable, pivot to how discretionary purchases or sector speculation relate to their monthly cashflow surplus and diversified buckets."""


class AdviseAiUseCase:
    """Orchestrates structured, privacy-preserving financial prompt generation and AI advisory consultation."""

    def __init__(self, ai_client: AIAdvisorPort | None = None) -> None:
        self.ai_client = ai_client

    @staticmethod
    def validate_question(question: str | None) -> str | None:
        if not question:
            return None
        cleaned = question.strip()
        if not cleaned:
            return None
        if len(cleaned) > MAX_QUESTION_LENGTH:
            raise ValueError(
                f"Question exceeds maximum length of {MAX_QUESTION_LENGTH:,} characters."
            )
        if _INJECTION_PATTERNS.search(cleaned):
            raise ValueError(
                "Prompt override detected. Please ask a question related to your financial strategy or balance sheet."
            )
        return cleaned

    @staticmethod
    def _validate_question(question: str | None) -> str | None:
        return AdviseAiUseCase.validate_question(question)

    async def execute(
        self,
        balance_sheet: BalanceSheet,
        allocations: Sequence[BucketAllocationResult],
        deterministic_advices: Sequence[AdviceItem],
        user_question: str | None = None,
    ) -> str:
        if self.ai_client is None:
            raise RuntimeError("AI client is required to execute AI advisory consultation.")
        prompt = self.build_prompt(
            bs=balance_sheet,
            allocations=allocations,
            advices=deterministic_advices,
            question=user_question,
        )
        return await self.ai_client.generate_advice(prompt=prompt, system_prompt=SYSTEM_PROMPT)

    def build_prompt(
        self,
        bs: BalanceSheet,
        allocations: Sequence[BucketAllocationResult],
        advices: Sequence[AdviceItem],
        question: str | None = None,
    ) -> str:
        validated_question = self.validate_question(question)
        return self._format_prompt(bs, allocations, advices, validated_question)

    def _build_prompt(
        self,
        bs: BalanceSheet,
        allocations: Sequence[BucketAllocationResult],
        advices: Sequence[AdviceItem],
        question: str | None,
    ) -> str:
        return self._format_prompt(bs, allocations, advices, question)

    def _format_prompt(
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
            lines.append(
                f"\n## User Question / Scenario:\n{question}\n\n"
                "## Advisory Instruction:\n"
                "Address the user's question or scenario strictly through the lens of their Consolidated Financial Snapshot above. "
                "If the prompt is unrelated to finance, wealth planning, or budget impact, politely decline the off-topic subject in one sentence and summarize their top portfolio priority instead."
            )
        else:
            lines.append(
                "\n## Request:\nProvide a high-level strategic review of this portfolio. "
                "Evaluate the asset allocation balance, debt vs investing prioritization, "
                "and advise on how to strategically deploy the monthly surplus over the next 12-36 months."
            )

        return "\n".join(lines)
