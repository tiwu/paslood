"""Use Case: Categorize Transactions and Rule Persistence."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from paslood.domain.balance_sheet import Transaction, TransactionCategory

if TYPE_CHECKING:
    from paslood.domain.account import KnownAccount

DEFAULT_PATTERNS = [
    (r"WONINGKREDIET|HYPOTHEEK|MORTGAGE", TransactionCategory.MORTGAGE.value),
    (r"FLEX BUDGET|CONSUMER|KREDIET", TransactionCategory.DEBT_REPAYMENT.value),
    (r"VERZEKERING|ASSURANCE|SCHULDSALDO|POLIS", TransactionCategory.INSURANCE.value),
    (
        r"ALDI|LIDL|JUMBO|DELHAIZE|COLRUYT|CARREFOUR|ALBERT HEIJN",
        TransactionCategory.GROCERIES.value,
    ),
    (
        r"BASIC-FIT|NETFLIX|SPOTIFY|APPLE|GOOGLE|AMAZON PRIME",
        TransactionCategory.SUBSCRIPTION.value,
    ),
    (r"SALARY|LOON|WEDDE|PAYROLL|WAGE|EMPLOYER", TransactionCategory.INCOME.value),
    (
        r"SAXO|DEGIRO|BOLERO|INTERACTIVE BROKERS|TRADE REPUBLIC|BROKER",
        TransactionCategory.INVESTMENTS.value,
    ),
    (r"SPAARREKENING|SPAREN|SAVINGS|ÉPARGNE", TransactionCategory.SAVINGS.value),
    (
        r"EIGEN REKENING|INTERN|INTERNAL TRANSFER|VIREMENT PROPRE",
        TransactionCategory.TRANSFER.value,
    ),
]


class CategorizeTransactionsUseCase:
    """Classifies cashflow transactions and applies custom learned user rules."""

    def execute(
        self,
        transactions: Sequence[Transaction],
        rules: Sequence[dict[str, Any]] | None = None,
        known_accounts: Sequence[KnownAccount] | None = None,
    ) -> list[Transaction]:
        user_rules = rules or []
        accounts = known_accounts or []
        categorized: list[Transaction] = []

        # Prepare normalized lookup for known accounts
        cleaned_accounts = []
        for acc in accounts:
            clean_num = re.sub(r"[^A-Za-z0-9]", "", acc.account_number).upper()
            cleaned_accounts.append((clean_num, acc.label.lower(), acc.account_type.upper()))

        for tx in transactions:
            matched_category = None

            # 1. Check user-defined custom rules first (highest precedence)
            for rule in user_rules:
                field_name = rule.get("match_field", "description")
                pattern = rule.get("pattern", "")
                target_cat = rule.get("target_category", "")

                val_to_check = str(getattr(tx, field_name, "") or "")
                # If checking counterparty_name and it is empty, also fall back to description
                if not val_to_check and field_name == "counterparty_name":
                    val_to_check = str(tx.description or "")

                if pattern and target_cat:
                    # Safely match pattern without breaking on special regex characters like '*'
                    try:
                        matched = bool(re.search(pattern, val_to_check, re.IGNORECASE))
                    except re.error:
                        matched = pattern.lower() in val_to_check.lower()

                    if not matched and pattern.lower() in val_to_check.lower():
                        matched = True

                    if matched:
                        matched_category = target_cat
                        break

            # 2. Check known accounts cross-referencing (Saxo, savings, checking)
            if not matched_category and cleaned_accounts:
                tx_desc_clean = re.sub(r"[^A-Za-z0-9]", "", tx.description or "").upper()
                tx_iban_clean = re.sub(r"[^A-Za-z0-9]", "", tx.counterparty_iban or "").upper()
                tx_name_lower = (tx.counterparty_name or "").lower()
                tx_desc_lower = (tx.description or "").lower()

                for clean_num, label_lower, acc_type in cleaned_accounts:
                    matched = False
                    if (
                        clean_num
                        and (clean_num in tx_iban_clean or clean_num in tx_desc_clean)
                        or label_lower
                        and (label_lower in tx_name_lower or label_lower in tx_desc_lower)
                    ):
                        matched = True

                    if matched:
                        if acc_type == "INVESTMENT":
                            matched_category = TransactionCategory.INVESTMENTS.value
                        elif acc_type == "SAVINGS":
                            matched_category = TransactionCategory.SAVINGS.value
                        elif acc_type == "CHECKING":
                            matched_category = TransactionCategory.TRANSFER.value
                        break

            # 3. Fall back to default heuristic patterns
            if not matched_category:
                combined_text = f"{tx.description} {tx.counterparty_name}"
                for regex, cat in DEFAULT_PATTERNS:
                    if re.search(regex, combined_text, re.IGNORECASE):
                        matched_category = cat
                        break

            # 3. Income heuristic fallback based on amount sign
            if not matched_category:
                if tx.is_inflow:
                    matched_category = TransactionCategory.INCOME.value
                else:
                    matched_category = TransactionCategory.LIVING_EXPENSES.value

            tx.category = matched_category
            categorized.append(tx)

        return categorized

    def create_rule(
        self,
        match_field: str,
        pattern: str,
        target_category: str,
        description: str = "",
    ) -> dict[str, Any]:
        """Creates a learned categorization rule to be persisted to rules.yaml."""
        return {
            "match_field": match_field,
            "pattern": pattern,
            "target_category": target_category,
            "description": description or f"Auto-classify {pattern} as {target_category}",
        }
