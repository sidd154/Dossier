"""Connector contract shared by every external integration.

An adapter knows how to authenticate, enumerate the usable sources it exposes, and
fetch one of them as a flat table. Everything downstream — snapshots, permissions,
retrieval, mail — depends only on this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class ConnectorError(Exception):
    """Base class for adapter failures shown to administrators."""


class ConnectorAuthError(ConnectorError):
    """Credentials were rejected or have expired."""


class ConnectorFetchError(ConnectorError):
    """The remote source could not be read."""


@dataclass(frozen=True, slots=True)
class ConnectorAsset:
    """A usable source exposed by a connector, not yet registered as a DataSource."""

    external_id: str
    name: str
    kind: str
    config: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FetchedTable:
    columns: list[str]
    rows: list[dict[str, Any]]
    partial: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseConnector(ABC):
    def __init__(
        self, *, config: dict[str, Any], credentials: dict[str, Any]
    ) -> None:
        self.config = config
        self.credentials = credentials

    @abstractmethod
    async def validate(self) -> None:
        """Raise a ConnectorError if the credentials or base config are unusable."""

    @abstractmethod
    async def list_assets(self) -> list[ConnectorAsset]:
        """Enumerate sources the connector can expose."""

    @abstractmethod
    async def fetch(self, source_config: dict[str, Any]) -> FetchedTable:
        """Read one source as a flat table."""
