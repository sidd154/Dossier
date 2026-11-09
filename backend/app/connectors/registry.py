"""Connector type to adapter mapping."""

from typing import Any

from app.connectors.base import BaseConnector
from app.connectors.google_sheets import GoogleSheetsConnector
from app.connectors.models import ConnectorType
from app.connectors.zoho_crm import ZohoCrmConnector

_ADAPTERS: dict[ConnectorType, type[BaseConnector]] = {
    ConnectorType.GOOGLE_SHEETS: GoogleSheetsConnector,
    ConnectorType.ZOHO_CRM: ZohoCrmConnector,
}


def get_connector(
    connector_type: ConnectorType,
    *,
    config: dict[str, Any],
    credentials: dict[str, Any],
) -> BaseConnector:
    adapter = _ADAPTERS.get(connector_type)
    if adapter is None:
        raise ValueError(f"Unsupported connector type: {connector_type}")
    return adapter(config=config, credentials=credentials)
