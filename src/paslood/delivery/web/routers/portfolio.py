"""Portfolio, Buckets, Assets, and Liabilities APIRouter for Paslood."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from paslood.adapters.repositories.config_repo import ConfigRepository
from paslood.adapters.repositories.local_db import LocalDbRepository
from paslood.adapters.settings import AppSettings
from paslood.delivery.web.dependencies import (
    get_alloc_calc,
    get_app_settings,
    get_db,
    get_debt_advisor,
    get_net_worth_projector,
    get_repo,
)
from paslood.delivery.web.helpers import enrich_liability_dict, get_consolidated_balance_sheet
from paslood.domain.bucket import Bucket, validate_bucket_weights
from paslood.use_cases.advise_debt_payoff import AdviseDebtPayoffUseCase
from paslood.use_cases.build_overview import BuildPortfolioOverviewUseCase
from paslood.use_cases.calculate_allocation import CalculateBucketAllocationUseCase
from paslood.use_cases.project_net_worth import ProjectNetWorthUseCase

router = APIRouter(tags=["portfolio"])


class BucketCreateOrUpdateRequest(BaseModel):
    id: str | None = None
    name: str
    target_weight_pct: float
    color: str | None = None
    drift_tolerance_pct: float | None = 3.0
    description: str | None = None
    include_in_rebalancing: bool | None = True
    include_in_net_worth: bool | None = True


class TargetWeightRequest(BaseModel):
    bucket_id: str
    name: str = ""
    target_weight_pct: float


class BatchTargetWeightsRequest(BaseModel):
    targets: dict[str, float]


class AssignAssetRequest(BaseModel):
    bucket_id: str
    symbol: str | None = None
    isin: str | None = None
    asset_id: str | None = None
    name: str | None = None


class ManualAssetRequest(BaseModel):
    id: str | None = None
    name: str
    symbol: str | None = ""
    isin: str | None = None
    asset_class: str = "REAL_ESTATE"
    current_value: float
    institution: str | None = "Manual"
    currency: str = "EUR"


class ManualLiabilityRequest(BaseModel):
    id: str | None = None
    name: str
    loan_type: str = "MORTGAGE"
    principal_balance: float = 0.0
    interest_rate_pct: float = 0.0
    monthly_payment: float = 0.0
    monthly_payment_pct: float | None = None
    start_capital: float | None = None
    start_date: str | None = None
    end_date: str | None = None
    duration_months: int | None = None
    institution: str | None = "Manual"
    currency: str = "EUR"
    is_tax_deductible: bool = False
    account_reference: str | None = None


@router.get("/api/overview")
async def get_overview(
    request: Request,
    exclude_property: bool = False,
    repo: ConfigRepository = Depends(get_repo),
    db: LocalDbRepository = Depends(get_db),
    settings: AppSettings = Depends(get_app_settings),
    alloc_calc: CalculateBucketAllocationUseCase = Depends(get_alloc_calc),
    debt_advisor: AdviseDebtPayoffUseCase = Depends(get_debt_advisor),
    net_worth_projector: ProjectNetWorthUseCase = Depends(get_net_worth_projector),
):
    bs = get_consolidated_balance_sheet(repo, db)
    buckets = repo.load_buckets()
    configured_milestones = repo.load_milestones()

    overview_builder = BuildPortfolioOverviewUseCase(
        alloc_calc=alloc_calc,
        debt_advisor=debt_advisor,
        net_worth_projector=net_worth_projector,
    )
    data = overview_builder.execute(
        balance_sheet=bs,
        buckets=buckets,
        configured_milestones=configured_milestones,
        exclude_property=exclude_property,
    )

    txs = db.get_transactions(limit=1000)
    data["transactions"] = [
        {
            "id": t.id,
            "date": t.date,
            "description": t.description,
            "counterparty_name": t.counterparty_name,
            "amount_value": float(t.amount.amount),
            "amount_formatted": t.amount.format(),
            "category": t.category,
        }
        for t in txs
    ]

    tenant = getattr(request.state, "tenant", None)
    data["current_user"] = {
        "email": tenant.email if tenant else "local@paslood",
        "tenant_id": tenant.tenant_id if tenant else "default",
        "auth_mode": settings.auth_mode,
    }
    return data


@router.post("/api/buckets")
async def add_or_update_bucket(
    req: BucketCreateOrUpdateRequest,
    repo: ConfigRepository = Depends(get_repo),
):
    bucket_id = repo.save_bucket(req.model_dump(exclude_unset=True))
    return {"status": "success", "bucket_id": bucket_id}


@router.put("/api/buckets/{bucket_id}")
async def update_bucket(
    bucket_id: str,
    req: BucketCreateOrUpdateRequest,
    repo: ConfigRepository = Depends(get_repo),
):
    data = req.model_dump(exclude_unset=True)
    data["id"] = bucket_id
    repo.save_bucket(data)
    return {"status": "success", "bucket_id": bucket_id}


@router.delete("/api/buckets/{bucket_id}")
async def delete_bucket(
    bucket_id: str,
    repo: ConfigRepository = Depends(get_repo),
):
    deleted = repo.delete_bucket(bucket_id)
    return {"status": "success", "deleted": deleted}


@router.post("/api/buckets/target")
async def update_bucket_target(
    req: TargetWeightRequest,
    repo: ConfigRepository = Depends(get_repo),
):
    buckets = repo.load_buckets()
    new_weight = Decimal(str(req.target_weight_pct))
    updated_buckets: list[Bucket] = []
    found = False
    for b in buckets:
        if b.id == req.bucket_id:
            found = True
            updated_buckets.append(
                Bucket(
                    id=b.id,
                    name=req.name or b.name,
                    target_weight_pct=new_weight,
                    drift_tolerance_pct=b.drift_tolerance_pct,
                    rules=b.rules,
                    description=b.description,
                    color=b.color,
                    include_in_rebalancing=b.include_in_rebalancing,
                    include_in_net_worth=b.include_in_net_worth,
                )
            )
        else:
            updated_buckets.append(b)

    if not found:
        updated_buckets.append(
            Bucket(
                id=req.bucket_id,
                name=req.name or req.bucket_id,
                target_weight_pct=new_weight,
            )
        )

    try:
        validate_bucket_weights(updated_buckets)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    repo.save_bucket_target(
        bucket_id=req.bucket_id,
        name=req.name,
        target_weight_pct=new_weight,
    )
    return {"status": "success"}


@router.post("/api/buckets/targets")
async def update_bucket_targets(
    req: BatchTargetWeightsRequest,
    repo: ConfigRepository = Depends(get_repo),
):
    buckets = repo.load_buckets()
    updated_buckets: list[Bucket] = []
    for b in buckets:
        if b.id in req.targets:
            new_weight = Decimal(str(req.targets[b.id]))
            updated_buckets.append(
                Bucket(
                    id=b.id,
                    name=b.name,
                    target_weight_pct=new_weight,
                    drift_tolerance_pct=b.drift_tolerance_pct,
                    rules=b.rules,
                    description=b.description,
                    color=b.color,
                    include_in_rebalancing=b.include_in_rebalancing,
                    include_in_net_worth=b.include_in_net_worth,
                )
            )
        else:
            updated_buckets.append(b)

    try:
        validate_bucket_weights(updated_buckets)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    repo.save_bucket_targets(req.targets)
    return {"status": "success"}


@router.post("/api/buckets/assign-asset")
async def assign_asset_to_bucket(
    req: AssignAssetRequest,
    repo: ConfigRepository = Depends(get_repo),
    db: LocalDbRepository = Depends(get_db),
    alloc_calc: CalculateBucketAllocationUseCase = Depends(get_alloc_calc),
):
    repo.assign_asset_to_bucket(
        bucket_id=req.bucket_id,
        symbol=req.symbol,
        isin=req.isin,
        asset_id=req.asset_id,
        name=req.name,
    )
    bs = get_consolidated_balance_sheet(repo, db)
    buckets = repo.load_buckets()
    allocations = alloc_calc.execute(assets=bs.assets, buckets=buckets)
    return {
        "status": "success",
        "allocations": [
            {
                "bucket_id": a.bucket_id,
                "name": a.name,
                "current_value": float(a.current_value),
                "current_weight_pct": float(a.current_weight_pct),
                "target_weight_pct": float(a.target_weight_pct),
                "diff_value": float(a.diff_value),
                "diff_weight_pct": float(a.diff_weight_pct),
                "drift_status": a.drift_status.value,
                "drift_tolerance_pct": float(a.drift_tolerance_pct),
                "color": a.color,
                "include_in_rebalancing": getattr(a, "include_in_rebalancing", True),
            }
            for a in allocations
        ],
    }


@router.post("/api/assets/manual")
async def save_manual_asset(
    req: ManualAssetRequest,
    repo: ConfigRepository = Depends(get_repo),
):
    asset_dict = req.model_dump(exclude_unset=True)
    repo.save_manual_asset(asset_dict)
    return {"status": "success", "asset": asset_dict}


@router.put("/api/assets/manual/{asset_id}")
async def update_manual_asset(
    asset_id: str,
    req: ManualAssetRequest,
    repo: ConfigRepository = Depends(get_repo),
):
    asset_dict = req.model_dump(exclude_unset=True)
    asset_dict["id"] = asset_id
    repo.save_manual_asset(asset_dict)
    return {"status": "success", "asset": asset_dict}


@router.delete("/api/assets/manual/{asset_id}")
async def delete_manual_asset(
    asset_id: str,
    repo: ConfigRepository = Depends(get_repo),
):
    repo.delete_manual_asset(asset_id)
    return {"status": "success"}


@router.post("/api/liabilities/manual")
async def save_manual_liability(
    req: ManualLiabilityRequest,
    repo: ConfigRepository = Depends(get_repo),
    db: LocalDbRepository = Depends(get_db),
):
    liab_dict = enrich_liability_dict(req.model_dump(exclude_unset=True))
    repo.save_manual_liability(liab_dict)
    if req.id:
        db.update_liability(req.id, liab_dict)
    return {"status": "success", "liability": liab_dict}


@router.put("/api/liabilities/manual/{liability_id}")
async def update_manual_liability(
    liability_id: str,
    req: ManualLiabilityRequest,
    repo: ConfigRepository = Depends(get_repo),
    db: LocalDbRepository = Depends(get_db),
):
    liab_dict = enrich_liability_dict(req.model_dump(exclude_unset=True))
    liab_dict["id"] = liability_id
    repo.save_manual_liability(liab_dict)
    db.update_liability(liability_id, liab_dict)
    return {"status": "success", "liability": liab_dict}


@router.delete("/api/liabilities/manual/{liability_id}")
async def delete_manual_liability(
    liability_id: str,
    repo: ConfigRepository = Depends(get_repo),
    db: LocalDbRepository = Depends(get_db),
):
    repo.delete_manual_liability(liability_id)
    db.delete_liability(liability_id)
    return {"status": "success"}
