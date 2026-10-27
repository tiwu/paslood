"""FastAPI APIRouters for Paslood delivery layer."""

from __future__ import annotations

from paslood.delivery.web.routers.ai import router as ai_router
from paslood.delivery.web.routers.auth import router as auth_router
from paslood.delivery.web.routers.ingestion import router as ingestion_router
from paslood.delivery.web.routers.planning import router as planning_router
from paslood.delivery.web.routers.portfolio import router as portfolio_router
from paslood.delivery.web.routers.settings import router as settings_router

__all__ = [
    "ai_router",
    "auth_router",
    "ingestion_router",
    "planning_router",
    "portfolio_router",
    "settings_router",
]
