"""AI Advisory and Model Discovery APIRouter for Paslood."""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from paslood.adapters.ai.llm_client import UniversalAIAdvisorClient
from paslood.adapters.repositories.config_repo import ConfigRepository, _is_masked_secret
from paslood.adapters.repositories.local_db import LocalDbRepository
from paslood.adapters.security.secret_vault import SecretVault
from paslood.delivery.web.dependencies import (
    get_alloc_calc,
    get_db,
    get_debt_advisor,
    get_repo,
    get_secret_vault,
)
from paslood.delivery.web.helpers import get_consolidated_balance_sheet
from paslood.use_cases.advise_ai import AdviseAiUseCase
from paslood.use_cases.advise_debt_payoff import AdviseDebtPayoffUseCase
from paslood.use_cases.calculate_allocation import CalculateBucketAllocationUseCase

logger = logging.getLogger("paslood.delivery.web.ai")
router = APIRouter(tags=["ai"])


class AiAdviseRequest(BaseModel):
    provider: str = "gemini"
    api_key: str | None = None
    model: str | None = None
    question: str | None = None


@router.get("/api/ai/models")
async def get_ai_models(
    request: Request,
    provider: str = "gemini",
    base_url: str | None = None,
    repo: ConfigRepository = Depends(get_repo),
    secret_vault: SecretVault = Depends(get_secret_vault),
):
    header_key = request.headers.get("X-AI-API-Key")
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        header_key = header_key or auth_header.removeprefix("Bearer ").strip()

    effective_key = header_key
    s = repo.load_settings()
    if not effective_key or _is_masked_secret(effective_key):
        raw_key = s.get("ai", {}).get("api_key")
        effective_key = secret_vault.decrypt(raw_key) if raw_key else ""

    effective_base_url = (
        base_url or s.get("ai", {}).get("ollama_url") if provider == "ollama" else base_url
    )

    kwargs = {"provider": provider, "api_key": effective_key}
    if effective_base_url:
        kwargs["base_url"] = effective_base_url

    models = await UniversalAIAdvisorClient.fetch_available_models(**kwargs)
    return {"models": models}


@router.post("/api/ai/advise")
async def run_ai_consultation(
    req: AiAdviseRequest,
    repo: ConfigRepository = Depends(get_repo),
    db: LocalDbRepository = Depends(get_db),
    secret_vault: SecretVault = Depends(get_secret_vault),
    alloc_calc: CalculateBucketAllocationUseCase = Depends(get_alloc_calc),
    debt_advisor: AdviseDebtPayoffUseCase = Depends(get_debt_advisor),
):
    bs = get_consolidated_balance_sheet(repo, db)
    buckets = repo.load_buckets()
    allocations = alloc_calc.execute(assets=bs.assets, buckets=buckets)
    advices = debt_advisor.execute(
        liabilities=bs.liabilities, monthly_surplus=bs.free_monthly_cashflow
    )

    s = repo.load_settings()
    effective_key = req.api_key
    if not effective_key or _is_masked_secret(effective_key):
        raw_key = s.get("ai", {}).get("api_key")
        effective_key = secret_vault.decrypt(raw_key) if raw_key else ""

    effective_model = req.model
    if not effective_model:
        effective_model = s.get("ai", {}).get("model")

    effective_base_url = s.get("ai", {}).get("ollama_url") if req.provider == "ollama" else None

    ai_client = UniversalAIAdvisorClient(
        provider=req.provider,
        api_key=effective_key,
        model=effective_model,
        base_url=effective_base_url,
    )
    ai_use_case = AdviseAiUseCase(ai_client=ai_client)
    t0 = time.perf_counter()
    try:
        prompt = ai_use_case.build_prompt(
            bs=bs,
            allocations=allocations,
            advices=advices,
            question=req.question,
        )
        advice_text = await ai_use_case.execute(
            balance_sheet=bs,
            allocations=allocations,
            deterministic_advices=advices,
            user_question=req.question,
        )
        elapsed = time.perf_counter() - t0
        trace = getattr(ai_client, "last_trace", None) or {
            "provider": req.provider,
            "model": effective_model,
            "duration_s": round(elapsed, 2),
            "attempts": 1,
            "status": "success",
        }
        return {"advice": advice_text, "prompt": prompt, "trace": trace}
    except Exception as e:
        elapsed = time.perf_counter() - t0
        logger.error("AI consultation failed after %.2fs: %s", elapsed, e)
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/api/ai/prompt-preview")
async def get_ai_prompt_preview(
    question: str | None = None,
    repo: ConfigRepository = Depends(get_repo),
    db: LocalDbRepository = Depends(get_db),
    alloc_calc: CalculateBucketAllocationUseCase = Depends(get_alloc_calc),
    debt_advisor: AdviseDebtPayoffUseCase = Depends(get_debt_advisor),
):
    bs = get_consolidated_balance_sheet(repo, db)
    buckets = repo.load_buckets()
    allocations = alloc_calc.execute(assets=bs.assets, buckets=buckets)
    advices = debt_advisor.execute(
        liabilities=bs.liabilities, monthly_surplus=bs.free_monthly_cashflow
    )
    ai_use_case = AdviseAiUseCase()
    try:
        prompt = ai_use_case.build_prompt(
            bs=bs,
            allocations=allocations,
            advices=advices,
            question=question,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"prompt": prompt}
