"""FastAPI request dependency injectors for Paslood web routers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request

if TYPE_CHECKING:
    from paslood.adapters.ingestion.base import BaseIngestionGateway
    from paslood.adapters.ingestion.pdt_mcp import PdtMcpGateway
    from paslood.adapters.repositories.config_repo import ConfigRepository
    from paslood.adapters.repositories.local_db import LocalDbRepository
    from paslood.adapters.security.secret_vault import SecretVault
    from paslood.adapters.settings import AppSettings
    from paslood.delivery.web.auth import AuthManager
    from paslood.use_cases.advise_contribution import AdviseContributionUseCase
    from paslood.use_cases.advise_debt_payoff import AdviseDebtPayoffUseCase
    from paslood.use_cases.calculate_allocation import CalculateBucketAllocationUseCase
    from paslood.use_cases.categorize_transactions import CategorizeTransactionsUseCase
    from paslood.use_cases.optimize_tax import OptimizeTaxUseCase
    from paslood.use_cases.project_net_worth import ProjectNetWorthUseCase


def get_repo(request: Request) -> ConfigRepository:
    return request.app.state.repo


def get_db(request: Request) -> LocalDbRepository:
    return request.app.state.local_db


def get_app_settings(request: Request) -> AppSettings:
    return request.app.state.settings


def get_auth_manager(request: Request) -> AuthManager:
    return request.app.state.auth_manager


def get_secret_vault(request: Request) -> SecretVault:
    return request.app.state.secret_vault


def get_alloc_calc(request: Request) -> CalculateBucketAllocationUseCase:
    return request.app.state.alloc_calc


def get_contrib_advisor(request: Request) -> AdviseContributionUseCase:
    return request.app.state.contrib_advisor


def get_debt_advisor(request: Request) -> AdviseDebtPayoffUseCase:
    return request.app.state.debt_advisor


def get_net_worth_projector(request: Request) -> ProjectNetWorthUseCase:
    return request.app.state.net_worth_projector


def get_categorizer(request: Request) -> CategorizeTransactionsUseCase:
    return request.app.state.categorizer


def get_tax_optimizer(request: Request) -> OptimizeTaxUseCase:
    return request.app.state.tax_optimizer


def get_kbc_gateway(request: Request) -> BaseIngestionGateway:
    return request.app.state.kbc_gateway


def get_generic_gateway(request: Request) -> BaseIngestionGateway:
    return request.app.state.generic_gateway


def get_pdt_gateway(request: Request) -> PdtMcpGateway:
    return request.app.state.pdt_gateway
