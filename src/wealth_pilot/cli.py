"""Paslood Command Line Interface (CLI)."""

from __future__ import annotations

import os
from pathlib import Path

import typer
import uvicorn
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from wealth_pilot import __version__
from wealth_pilot.adapters.ingestion.generic_csv import GenericCsvGateway
from wealth_pilot.adapters.ingestion.kbc_csv import KbcCsvGateway
from wealth_pilot.adapters.repositories.config_repo import ConfigRepository
from wealth_pilot.adapters.repositories.local_db import LocalDbRepository
from wealth_pilot.adapters.settings import AppSettings
from wealth_pilot.domain.balance_sheet import BalanceSheet
from wealth_pilot.domain.money import Money
from wealth_pilot.use_cases.advise_contribution import AdviseContributionUseCase
from wealth_pilot.use_cases.advise_debt_payoff import AdviseDebtPayoffUseCase
from wealth_pilot.use_cases.build_overview import BuildPortfolioOverviewUseCase
from wealth_pilot.use_cases.calculate_allocation import CalculateBucketAllocationUseCase

app = typer.Typer(
    name="paslood",
    help="🧭 Paslood: Whole-Life Balance Sheet, PDT Companion & Belgian Fiscal Shield",
    add_completion=False,
)
console = Console()


def version_callback(value: bool) -> None:
    if value:
        console.print(f"Paslood [bold cyan]v{__version__}[/bold cyan]")
        raise typer.Exit()


@app.callback()
def main_callback(
    version: bool | None = typer.Option(
        None,
        "--version",
        "-V",
        "-v",
        help="Show the application version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """Paslood CLI."""
    pass


@app.command()
def web(
    host: str = typer.Option("127.0.0.1", help="Host address to bind the web server"),
    port: int = typer.Option(8000, help="Port to listen on"),
    reload: bool = typer.Option(False, help="Enable auto-reload for development"),
    allow_unauthenticated: bool = typer.Option(
        False, help="Allow binding to non-localhost address without authentication (DANGEROUS)"
    ),
) -> None:
    """Launch the local interactive Web Dashboard."""
    settings = AppSettings.from_env()
    if (
        host not in ("127.0.0.1", "localhost")
        and settings.auth_mode == "none"
        and not settings.has_password
        and not settings.has_oauth
        and not allow_unauthenticated
    ):
        console.print(
            Panel.fit(
                "[bold red]SECURITY REFUSAL: Cannot bind to external host without authentication![/bold red]\n\n"
                "Paslood stores financial balances and private API keys.\n"
                "To expose this server remotely (via LAN, container, or Dynamic DNS):\n"
                "1. Run [bold green]paslood set-password[/bold green] to configure a login password, OR\n"
                "2. Set [bold cyan]WEALTH_PILOT_AUTH_MODE=password[/bold cyan] in your environment, OR\n"
                "3. Configure Google/GitHub OAuth credentials in your environment.\n\n"
                "If you are certain you want an unauthenticated server on your network,\n"
                "re-run with [bold yellow]--allow-unauthenticated[/bold yellow].",
                border_style="red",
            )
        )
        raise typer.Exit(1)

    console.print(
        Panel.fit(
            f"[bold blue]🧭 Paslood Dashboard[/bold blue]\n"
            f"Server running at: [bold green]http://{host}:{port}[/bold green]\n"
            f"Auth mode: [bold cyan]{settings.auth_mode}[/bold cyan]\n"
            f"Press [bold red]Ctrl+C[/bold red] to stop.",
            border_style="blue",
        )
    )
    uvicorn.run("wealth_pilot.delivery.web.app:app", host=host, port=port, reload=reload)


@app.command("set-password")
def set_password(
    password: str = typer.Option(
        None, prompt=True, hide_input=True, confirmation_prompt=True, help="New master passphrase"
    ),
) -> None:
    """Set or update the master admin password for remote access."""
    from wealth_pilot.delivery.web.auth import hash_password

    hashed = hash_password(password)
    settings = AppSettings.from_env()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    env_file = settings.data_dir / ".env"
    with open(env_file, "a", encoding="utf-8") as f:
        f.write(f"\nWEALTH_PILOT_ADMIN_PASSWORD_HASH={hashed}\nWEALTH_PILOT_AUTH_MODE=password\n")
    if os.name != "nt":
        env_file.chmod(0o600)
    console.print(
        Panel.fit(
            f"[bold green]Password set successfully![/bold green]\n"
            f"Stored in: [cyan]{env_file}[/cyan]\n"
            f"Auth mode enabled: [bold white]password[/bold white]",
            border_style="green",
        )
    )


@app.command()
def status(
    config: Path | None = typer.Option(None, help="Path to portfolio.yaml configuration file"),
) -> None:
    """Display consolidated Balance Sheet, Net Worth, and Bucket Allocation summary."""
    repo = ConfigRepository(config_path=config)
    db = LocalDbRepository(db_path=repo.config_path.parent / "wealth_pilot.db")
    buckets = repo.load_buckets()
    assets = repo.load_manual_assets()
    liabilities = repo.load_manual_liabilities()

    # Merge discovered assets from DB
    existing_asset_ids = {a.id for a in assets}
    for da in db.get_discovered_assets():
        if da.id not in existing_asset_ids:
            assets.append(da)
            existing_asset_ids.add(da.id)

    # Merge discovered liabilities from DB
    existing_liab_ids = {liab.id for liab in liabilities}
    for dl in db.get_discovered_liabilities():
        if dl.id not in existing_liab_ids:
            liabilities.append(dl)
            existing_liab_ids.add(dl.id)

    cashflow = db.get_monthly_cashflow()
    bs = BalanceSheet(
        assets=assets,
        liabilities=liabilities,
        cashflow=cashflow,
    )

    overview_builder = BuildPortfolioOverviewUseCase()
    overview_builder.execute(balance_sheet=bs, buckets=buckets)
    alloc_calc = CalculateBucketAllocationUseCase()
    allocations = alloc_calc.execute(assets=assets, buckets=buckets)

    # Balance Sheet Table
    console.print("\n[bold white]🏛️ Balance Sheet & Net Worth Overview[/bold white]")
    summary_table = Table(box=None)
    summary_table.add_column("Metric", style="cyan", width=26)
    summary_table.add_column("Amount", style="bold white", justify="right")

    summary_table.add_row("Total Assets", bs.total_assets.format())
    summary_table.add_row("Total Liabilities (Debts)", bs.total_liabilities.format())
    summary_table.add_row("─" * 26, "─" * 15)
    summary_table.add_row(
        "[bold green]Consolidated Net Worth[/bold green]",
        f"[bold green]{bs.net_worth.format()}[/bold green]",
    )
    summary_table.add_row("Debt-to-Asset Ratio", f"{bs.debt_to_asset_ratio:.1f}%")
    summary_table.add_row(
        "Monthly Free Cashflow", f"[emerald]{bs.free_monthly_cashflow.format()}[/emerald]"
    )
    console.print(summary_table)

    # Buckets Table
    console.print("\n[bold white]🪣 Strategic Allocation Buckets[/bold white]")
    b_table = Table(show_header=True, header_style="bold magenta")
    b_table.add_column("Bucket", style="bold white")
    b_table.add_column("Current Value", justify="right")
    b_table.add_column("Current %", justify="right")
    b_table.add_column("Target %", justify="right")
    b_table.add_column("Difference", justify="right")
    b_table.add_column("Status", justify="center")

    for a in allocations:
        status_style = (
            "green"
            if a.drift_status.value == "BALANCED"
            else ("blue" if a.drift_status.value == "UNDERWEIGHT" else "yellow")
        )
        b_table.add_row(
            a.name,
            f"€ {a.current_value:,.2f}",
            f"{a.current_weight_pct:.1f}%",
            f"{a.target_weight_pct:.1f}%",
            f"{'+' if a.diff_value > 0 else ''}€ {a.diff_value:,.2f}",
            f"[{status_style}]{a.drift_status.value}[/{status_style}]",
        )
    console.print(b_table)


@app.command()
def advise(
    deposit: float = typer.Option(1500.0, help="Planned monthly deposit amount in EUR"),
    config: Path | None = typer.Option(None, help="Path to portfolio.yaml configuration file"),
) -> None:
    """Calculate smart buy-only contribution advice and debt payoff priorities."""
    repo = ConfigRepository(config_path=config)
    buckets = repo.load_buckets()
    assets = repo.load_manual_assets()
    liabilities = repo.load_manual_liabilities()

    alloc_calc = CalculateBucketAllocationUseCase()
    allocations = alloc_calc.execute(assets=assets, buckets=buckets)

    contrib_calc = AdviseContributionUseCase()
    contribution_orders = contrib_calc.execute(
        deposit=Money.from_val(deposit),
        allocation_results=allocations,
    )

    console.print(
        f"\n[bold white]💡 Smart Buy-Only Rebalancing for € {deposit:,.2f} Deposit[/bold white]"
    )
    if not contribution_orders:
        console.print(
            "[dim]All buckets are balanced. Allocate proportionally across targets.[/dim]"
        )
    else:
        order_table = Table(show_header=True, header_style="bold green")
        order_table.add_column("Underweight Bucket", style="bold white")
        order_table.add_column("Recommended Allocation", style="bold green", justify="right")
        order_table.add_column("Share of Deposit", justify="right")

        for o in contribution_orders:
            order_table.add_row(o.bucket_name, o.amount.format(), f"{o.percentage_of_deposit:.1f}%")
        console.print(order_table)

    debt_advisor = AdviseDebtPayoffUseCase()
    debt_advices = debt_advisor.execute(
        liabilities=liabilities,
        monthly_surplus=Money.from_val(deposit),
    )

    console.print("\n[bold white]⚖️ Debt vs. Investing Strategy[/bold white]")
    for adv in debt_advices:
        color = (
            "red"
            if adv.priority.value == "CRITICAL"
            else ("yellow" if adv.priority.value == "HIGH" else "dim")
        )
        console.print(f"[{color}]• [{adv.priority.value}] {adv.title}:[/{color}] {adv.message}")


@app.command()
def ingest(
    file_path: Path = typer.Argument(..., help="Path to CSV file (KBC export or generic CSV)"),
) -> None:
    """Parse and inspect a bank statement or investment CSV file."""
    if not file_path.exists():
        console.print(f"[bold red]Error: File not found: {file_path}[/bold red]")
        raise typer.Exit(1)

    is_kbc = (
        "kbc" in file_path.name.lower()
        or ";" in file_path.read_text(encoding="iso-8859-1", errors="replace")[:500]
    )

    if is_kbc:
        gateway = KbcCsvGateway()
        res = gateway.parse_file(file_path)
        console.print(
            Panel.fit(
                f"[bold green]KBC Statement Parsed Successfully[/bold green]\n"
                f"Account: [cyan]{res['account_number']}[/cyan] ({res['account_holder']})\n"
                f"Liquid Balance: [bold white]{res['latest_balance'].format()}[/bold white]\n"
                f"Transactions Loaded: [white]{len(res['transactions'])}[/white]\n"
                f"Discovered Liabilities: [white]{len(res['discovered_liabilities'])}[/white]\n"
                f"Average Monthly Income: [bold green]{res['cashflow'].monthly_income.format()}[/bold green]\n"
                f"Monthly Debt Servicing: [bold red]{res['cashflow'].debt_payments.format()}[/bold red]",
                border_style="green",
            )
        )
    else:
        gateway = GenericCsvGateway()
        res = gateway.parse_file(file_path)
        console.print(
            Panel.fit(
                f"[bold green]Generic CSV Parsed Successfully[/bold green]\n"
                f"Assets Loaded: [bold white]{res['asset_count']}[/bold white]\n"
                f"Total Asset Value: [bold green]{res['total_value'].format()}[/bold green]",
                border_style="green",
            )
        )


@app.command()
def template(
    output: Path = typer.Option(
        Path("wealth_pilot_template.csv"), help="Target path to write sample template CSV"
    ),
) -> None:
    """Generate a sample generic CSV template for importing assets or accounts."""
    content = GenericCsvGateway.generate_template_csv()
    output.write_text(content, encoding="utf-8")
    console.print(f"[bold green]Template CSV generated at: {output.resolve()}[/bold green]")
