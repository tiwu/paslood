"""Unit tests for Known Accounts management and inter-account flow classification (#43)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from paslood.adapters.repositories.config_repo import ConfigRepository
from paslood.domain.account import KnownAccount
from paslood.domain.balance_sheet import Money, Transaction, TransactionCategory
from paslood.use_cases.categorize_transactions import CategorizeTransactionsUseCase


def test_config_repo_known_accounts_crud(tmp_path: Path) -> None:
    config_file = tmp_path / "portfolio.yaml"
    repo = ConfigRepository(config_path=config_file)

    assert repo.load_known_accounts() == []

    acc1 = KnownAccount(
        id="acc-saxo-1",
        account_number="BE12 3456 7890 1234",
        label="Saxo Trader Account",
        account_type="INVESTMENT",
        institution="Saxo",
    )
    acc2 = KnownAccount(
        id="acc-bunq-sav",
        account_number="NL28BUNQ2120824827",
        label="Bunq High-Yield Savings",
        account_type="SAVINGS",
        institution="bunq",
    )

    repo.save_known_account(acc1)
    repo.save_known_account(acc2)

    loaded = repo.load_known_accounts()
    assert len(loaded) == 2
    assert loaded[0].label == "Saxo Trader Account"
    assert loaded[0].account_type == "INVESTMENT"
    assert loaded[1].account_number == "NL28BUNQ2120824827"

    # Delete acc1
    repo.delete_known_account("acc-saxo-1")
    remaining = repo.load_known_accounts()
    assert len(remaining) == 1
    assert remaining[0].id == "acc-bunq-sav"


def test_categorize_inter_account_flows_with_known_accounts() -> None:
    saxo_acc = KnownAccount(
        id="acc-saxo",
        account_number="BE99 1111 2222 3333",
        label="Saxo Bank",
        account_type="INVESTMENT",
        institution="Saxo",
    )
    savings_acc = KnownAccount(
        id="acc-savings",
        account_number="NL28BUNQ2120824827",
        label="Bunq Savings",
        account_type="SAVINGS",
        institution="bunq",
    )
    checking_acc = KnownAccount(
        id="acc-kbc",
        account_number="BE90735017192832",
        label="KBC Checking",
        account_type="CHECKING",
        institution="KBC",
    )

    known_accounts = [saxo_acc, savings_acc, checking_acc]
    use_case = CategorizeTransactionsUseCase()

    # 1. Transfer to Saxo (Investing)
    tx_to_saxo = Transaction(
        id="tx-1",
        date="2026-06-01",
        amount=Money(Decimal("-500.00")),
        account_id="BE90735017192832",
        description="Transfer to Saxo BE99 1111 2222 3333",
        counterparty_name="Saxo Bank A/S",
        counterparty_iban="BE99111122223333",
    )

    # 2. Withdrawal from Saxo
    tx_from_saxo = Transaction(
        id="tx-2",
        date="2026-06-15",
        amount=Money(Decimal("250.00")),
        account_id="BE90735017192832",
        description="Terugstorting Saxo",
        counterparty_name="Saxo Bank",
        counterparty_iban="BE99111122223333",
    )

    # 3. Transfer to Bunq Savings (Saving)
    tx_to_savings = Transaction(
        id="tx-3",
        date="2026-06-20",
        amount=Money(Decimal("-1000.00")),
        account_id="BE90735017192832",
        description="Overschrijving naar spaarrekening",
        counterparty_name="Tim Wuytens",
        counterparty_iban="NL28BUNQ2120824827",
    )

    # 4. Transfer between checking accounts (Internal Transfer)
    tx_transfer = Transaction(
        id="tx-4",
        date="2026-06-25",
        amount=Money(Decimal("-200.00")),
        account_id="NL31BUNQ2093809982",
        description="bunq geld naar KBC",
        counterparty_name="Tim Wuyts",
        counterparty_iban="BE90735017192832",
    )

    results = use_case.execute(
        [tx_to_saxo, tx_from_saxo, tx_to_savings, tx_transfer],
        known_accounts=known_accounts,
    )

    assert results[0].category == TransactionCategory.INVESTMENTS.value
    assert results[1].category == TransactionCategory.INVESTMENTS.value
    assert results[2].category == TransactionCategory.SAVINGS.value
    assert results[3].category == TransactionCategory.TRANSFER.value
