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
from paslood.use_cases.ingest_statement import IngestStatementUseCase

router = APIRouter(tags=["ingestion"])


class RebucketRequest(BaseModel):
    transaction_id: str
    target_category: str
    counterparty_name: str | None = None
    pattern: str | None = None
    amount: Decimal | None = None
    remember_rule: bool = False


@router.post("/api/ingest/kbc")
async def ingest_kbc_file(
    file: UploadFile,
    repo: ConfigRepository = Depends(get_repo),
    db: LocalDbRepository = Depends(get_db),
    kbc_gateway: BaseIngestionGateway = Depends(get_kbc_gateway),
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
        sample = content[:2048].decode("utf-8", errors="replace").lower()
        if '"date"' in sample and '"amount"' in sample and '"account"' in sample:
            gateway = bunq_gateway
            source = "bunq_csv"
        else:
            gateway = kbc_gateway
            source = "kbc_csv"

        use_case = IngestStatementUseCase()
        return use_case.execute(
            file_path=tmp_path,
            gateway=gateway,
            repo=repo,
            db=db,
            source=source,
        )
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
        use_case = IngestStatementUseCase()
        return use_case.execute(
            file_path=tmp_path,
            gateway=bunq_gateway,
            repo=repo,
            db=db,
            source="bunq_csv",
        )
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
    # Always update the explicitly targeted transaction
    db.update_transaction_category(req.transaction_id, req.target_category)
    updated_historical_count = 1

    if req.pattern is not None:
        rule_pattern = req.pattern.strip()
        if not rule_pattern and req.amount is None:
            rule_pattern = (req.counterparty_name or "").strip()
    else:
        rule_pattern = (req.counterparty_name or "").strip()

    if not rule_pattern and req.amount is None:
        # Look up the transaction in DB to derive counterparty or description pattern
        existing_txs = db.get_transactions(limit=10000)
        matched_tx = next((t for t in existing_txs if t.id == req.transaction_id), None)
        if matched_tx:
            rule_pattern = (matched_tx.counterparty_name or matched_tx.description or "").strip()

    if rule_pattern or req.amount is not None:
        if req.remember_rule:
            rule_dict = {
                "match_field": "any",
                "pattern": rule_pattern,
                "target_category": req.target_category,
            }
            if req.amount is not None:
                rule_dict["amount"] = float(abs(req.amount))
            repo.save_transaction_rule(rule_dict)
        # Apply classification to all other matching rows in the ledger
        retro_count = db.apply_rule_to_transactions(
            rule_pattern,
            req.target_category,
            exclude_overrides=False,
            amount=req.amount,
        )
        updated_historical_count = max(updated_historical_count, retro_count)

    return {
        "status": "success",
        "updated_historical_count": updated_historical_count,
    }


@router.post("/api/data/reset-cache")
async def reset_cached_data(db: LocalDbRepository = Depends(get_db)):
    db.clear_all_cached_data()
    return {"status": "success", "message": "All ingested CSV cache cleared"}
