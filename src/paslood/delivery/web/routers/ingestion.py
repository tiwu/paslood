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
        kbc_gateway.categorizer = CategorizeTransactionsUseCase()

        # Content-based auto-detection fallback
        sample = content[:2048].decode("utf-8", errors="replace").lower()
        if '"date"' in sample and '"amount"' in sample and '"account"' in sample:
            from paslood.adapters.ingestion.bunq_csv import BunqCsvGateway

            data = BunqCsvGateway(kbc_gateway.categorizer).parse_file(tmp_path)
        else:
            data = kbc_gateway.parse_file(tmp_path)

        categorized_txs = kbc_gateway.categorizer.execute(data["transactions"], rules)

        inserted_txs = db.save_transactions(categorized_txs, source="kbc_csv")
        if data.get("cash_asset"):
            db.save_discovered_assets([data["cash_asset"]], source="kbc_csv")
        if data.get("discovered_liabilities"):
            db.save_discovered_liabilities(data["discovered_liabilities"])

        total_txs = len(db.get_transactions())

        return {
            "status": "success",
            "account_number": data["account_number"],
            "latest_balance": data["latest_balance"].format(),
            "transaction_count": len(categorized_txs),
            "transactions_processed": len(categorized_txs),
            "new_transactions": inserted_txs,
            "total_cumulative_transactions": total_txs,
            "discovered_liabilities_count": len(data["discovered_liabilities"]),
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
        bunq_gateway.categorizer = CategorizeTransactionsUseCase()
        data = bunq_gateway.parse_file(tmp_path)

        categorized_txs = bunq_gateway.categorizer.execute(data["transactions"], rules)

        inserted_txs = db.save_transactions(categorized_txs, source="bunq_csv")
        if data.get("cash_asset"):
            db.save_discovered_assets([data["cash_asset"]], source="bunq_csv")

        total_txs = len(db.get_transactions())

        return {
            "status": "success",
            "account_number": data["account_number"],
            "latest_balance": data["latest_balance"].format(),
            "transaction_count": len(categorized_txs),
            "transactions_processed": len(categorized_txs),
            "new_transactions": inserted_txs,
            "total_cumulative_transactions": total_txs,
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
    db.update_transaction_category(req.transaction_id, req.target_category)

    if req.remember_rule and req.counterparty_name:
        repo.save_transaction_rule(
            {
                "match_field": "counterparty_name",
                "pattern": req.counterparty_name,
                "target_category": req.target_category,
            }
        )

    return {"status": "success"}


@router.post("/api/data/reset-cache")
async def reset_cached_data(db: LocalDbRepository = Depends(get_db)):
    db.clear_all_cached_data()
    return {"status": "success", "message": "All ingested CSV cache cleared"}
