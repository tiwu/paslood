"""Bank and portfolio CSV statement ingestion APIRouter."""

from __future__ import annotations

import tempfile
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from pydantic import BaseModel

from paslood.adapters.ingestion.base import BaseIngestionGateway
from paslood.adapters.repositories.config_repo import ConfigRepository
from paslood.adapters.repositories.local_db import LocalDbRepository
from paslood.delivery.web.dependencies import (
    get_bunq_gateway,
    get_db,
    get_generic_gateway,
    get_kbc_gateway,
    get_repo,
)
from paslood.use_cases.categorize_transactions import CategorizeTransactionsUseCase

router = APIRouter(tags=["ingestion"])


class RebucketRequest(BaseModel):
    transaction_id: str
    target_category: str
    counterparty_name: str | None = None
    pattern: str | None = None
    remember_rule: bool = False


@router.post("/api/ingest/kbc")
async def ingest_kbc_file(
    file: UploadFile,
    repo: ConfigRepository = Depends(get_repo),
    db: LocalDbRepository = Depends(get_db),
    kbc_gateway: BaseIngestionGateway = Depends(get_kbc_gateway),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")

    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        rules = repo.load_transaction_rules()
        known_accounts = repo.load_known_accounts()
        kbc_gateway.categorizer = CategorizeTransactionsUseCase()

        # Content-based auto-detection fallback
        sample = content[:2048].decode("utf-8", errors="replace").lower()
        if '"date"' in sample and '"amount"' in sample and '"account"' in sample:
            from paslood.adapters.ingestion.bunq_csv import BunqCsvGateway

            data = BunqCsvGateway(kbc_gateway.categorizer).parse_file(tmp_path)
            cash_assets = data.get("discovered_cash_assets") or (
                [data["cash_asset"]] if data.get("cash_asset") else []
            )
            source = "bunq_csv"
        else:
            data = kbc_gateway.parse_file(tmp_path)
            cash_assets = [data["cash_asset"]] if data.get("cash_asset") else []
            source = "kbc_csv"

        categorized_txs = kbc_gateway.categorizer.execute(
            data["transactions"], rules, known_accounts=known_accounts
        )

        inserted_txs = db.save_transactions(categorized_txs, source=source)
        if cash_assets:
            db.save_discovered_assets(cash_assets, source=source)
        if data.get("discovered_liabilities"):
            db.save_discovered_liabilities(data["discovered_liabilities"])

        total_txs = len(db.get_transactions())

        # Check for unmapped / unknown accounts
        clean_known_set = {
            k.account_number.replace(" ", "").upper() for k in known_accounts if k.account_number
        }
        all_account_numbers = set()
        if data.get("account_number"):
            all_account_numbers.add(data["account_number"])
        for ca in cash_assets:
            if ca.account_id:
                all_account_numbers.add(ca.account_id)
        for tx in categorized_txs:
            if tx.account_id:
                all_account_numbers.add(tx.account_id)

        unregistered = []
        for acc in sorted(all_account_numbers):
            clean_acc = acc.replace(" ", "").upper()
            if clean_acc and clean_acc not in clean_known_set:
                inst = LocalDbRepository._infer_institution_from_account(acc)
                unregistered.append(
                    {
                        "account_id": acc,
                        "institution_hint": inst,
                        "suggested_label": f"{inst} {acc[-4:]}" if len(acc) >= 4 else inst,
                    }
                )

        return {
            "status": "success",
            "account_number": data["account_number"],
            "latest_balance": data["latest_balance"].format(),
            "transaction_count": len(categorized_txs),
            "transactions_processed": len(categorized_txs),
            "new_transactions": inserted_txs,
            "total_cumulative_transactions": total_txs,
            "discovered_liabilities_count": len(data["discovered_liabilities"]),
            "unregistered_accounts": unregistered,
        }
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


@router.post("/api/ingest/bunq")
async def ingest_bunq_file(
    file: UploadFile,
    repo: ConfigRepository = Depends(get_repo),
    db: LocalDbRepository = Depends(get_db),
    bunq_gateway: BaseIngestionGateway = Depends(get_bunq_gateway),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")

    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        rules = repo.load_transaction_rules()
        known_accounts = repo.load_known_accounts()
        bunq_gateway.categorizer = CategorizeTransactionsUseCase()
        data = bunq_gateway.parse_file(tmp_path)

        categorized_txs = bunq_gateway.categorizer.execute(
            data["transactions"], rules, known_accounts=known_accounts
        )

        inserted_txs = db.save_transactions(categorized_txs, source="bunq_csv")
        cash_assets = data.get("discovered_cash_assets") or (
            [data["cash_asset"]] if data.get("cash_asset") else []
        )
        if cash_assets:
            db.save_discovered_assets(cash_assets, source="bunq_csv")

        total_txs = len(db.get_transactions())

        # Check for unmapped / unknown accounts
        clean_known_set = {
            k.account_number.replace(" ", "").upper() for k in known_accounts if k.account_number
        }
        all_account_numbers = set()
        if data.get("account_number"):
            all_account_numbers.add(data["account_number"])
        for ca in cash_assets:
            if ca.account_id:
                all_account_numbers.add(ca.account_id)
        for tx in categorized_txs:
            if tx.account_id:
                all_account_numbers.add(tx.account_id)

        unregistered = []
        for acc in sorted(all_account_numbers):
            clean_acc = acc.replace(" ", "").upper()
            if clean_acc and clean_acc not in clean_known_set:
                inst = LocalDbRepository._infer_institution_from_account(acc)
                unregistered.append(
                    {
                        "account_id": acc,
                        "institution_hint": inst,
                        "suggested_label": f"{inst} {acc[-4:]}" if len(acc) >= 4 else inst,
                    }
                )

        return {
            "status": "success",
            "account_number": data["account_number"],
            "latest_balance": data["latest_balance"].format(),
            "transaction_count": len(categorized_txs),
            "transactions_processed": len(categorized_txs),
            "new_transactions": inserted_txs,
            "total_cumulative_transactions": total_txs,
            "unregistered_accounts": unregistered,
        }
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


@router.post("/api/ingest/generic")
async def ingest_generic_csv(
    file: UploadFile,
    db: LocalDbRepository = Depends(get_db),
    generic_gateway: BaseIngestionGateway = Depends(get_generic_gateway),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")

    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        assets = generic_gateway.parse_assets_file(tmp_path)
        db.save_discovered_assets(assets, source="generic_csv")
        return {
            "status": "success",
            "asset_count": len(assets),
            "total_value": sum((a.current_value.amount for a in assets), Decimal("0.00")),
        }
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


@router.get("/api/template/generic")
async def download_generic_template(
    generic_gateway: BaseIngestionGateway = Depends(get_generic_gateway),
):
    content = generic_gateway.generate_template_csv()
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="paslood_portfolio_template.csv"'},
    )


@router.post("/api/transactions/rebucket")
async def rebucket_transaction(
    req: RebucketRequest,
    repo: ConfigRepository = Depends(get_repo),
    db: LocalDbRepository = Depends(get_db),
):
    updated_historical_count = 1
    rule_pattern = (req.pattern or req.counterparty_name or "").strip()

    if req.remember_rule and rule_pattern:
        repo.save_transaction_rule(
            {
                "match_field": "counterparty_name",
                "pattern": rule_pattern,
                "target_category": req.target_category,
            }
        )
        # Apply retroactively to historical matching transactions
        retro_count = db.apply_rule_to_transactions(rule_pattern, req.target_category)
        updated_historical_count = max(updated_historical_count, retro_count)
    else:
        db.update_transaction_category(req.transaction_id, req.target_category)

    return {
        "status": "success",
        "updated_historical_count": updated_historical_count,
    }


@router.post("/api/data/reset-cache")
async def reset_cached_data(db: LocalDbRepository = Depends(get_db)):
    db.clear_all_cached_data()
    return {"status": "success", "message": "All ingested CSV cache cleared"}
