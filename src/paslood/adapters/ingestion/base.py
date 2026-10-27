"""Abstract Base Ingestion Gateway."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class BaseIngestionGateway(ABC):
    """Abstract contract for all financial data source parsers and connectors."""

    @abstractmethod
    def parse_file(self, file_path: str | Path) -> dict[str, Any]:
        """Parse raw file content into standard domain entities."""
        pass
