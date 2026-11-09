"""Zoho CRM adapter using a self-client OAuth refresh token."""

from typing import Any

import httpx

from app.connectors.base import (
    BaseConnector,
    ConnectorAsset,
    ConnectorAuthError,
    ConnectorError,
    ConnectorFetchError,
    FetchedTable,
)

DEFAULT_ACCOUNTS_DOMAIN = "https://accounts.zoho.com"
DEFAULT_API_DOMAIN = "https://www.zohoapis.com"
API_VERSION = "v8"
PAGE_SIZE = 200
MAX_PAGES = 50


class ZohoCrmConnector(BaseConnector):
    def _credential(self, key: str) -> str:
        value = str(self.credentials.get(key, "")).strip()
        if not value:
            raise ConnectorAuthError(f"Zoho credential '{key}' is missing")
        return value

    @property
    def accounts_domain(self) -> str:
        domain = self.credentials.get("accounts_domain") or DEFAULT_ACCOUNTS_DOMAIN
        return str(domain).rstrip("/")

    @property
    def api_domain(self) -> str:
        domain = self.config.get("api_domain") or DEFAULT_API_DOMAIN
        return str(domain).rstrip("/")

    async def _access_token(self) -> str:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.accounts_domain}/oauth/v2/token",
                data={
                    "refresh_token": self._credential("refresh_token"),
                    "client_id": self._credential("client_id"),
                    "client_secret": self._credential("client_secret"),
                    "grant_type": "refresh_token",
                },
            )
        if response.status_code != 200:
            raise ConnectorAuthError(
                f"Zoho rejected the refresh token ({response.status_code})"
            )
        payload = response.json()
        if payload.get("error"):
            raise ConnectorAuthError(f"Zoho auth error: {payload['error']}")
        token = payload.get("access_token")
        if not token:
            raise ConnectorAuthError("Zoho returned no access token")
        return str(token)

    async def validate(self) -> None:
        token = await self._access_token()
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self.api_domain}/crm/{API_VERSION}/settings/modules",
                headers={"Authorization": f"Zoho-oauthtoken {token}"},
            )
        if response.status_code in (401, 403):
            raise ConnectorAuthError(
                "Zoho denied access. Check the refresh token scopes and data centre."
            )
        if response.status_code != 200:
            raise ConnectorFetchError(
                f"Could not read Zoho modules ({response.status_code})"
            )

    async def list_assets(self) -> list[ConnectorAsset]:
        token = await self._access_token()
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self.api_domain}/crm/{API_VERSION}/settings/modules",
                headers={"Authorization": f"Zoho-oauthtoken {token}"},
            )
        if response.status_code in (401, 403):
            raise ConnectorAuthError(
                "Zoho denied access. Check the refresh token scopes and data centre."
            )
        if response.status_code != 200:
            raise ConnectorFetchError(
                f"Could not list Zoho modules ({response.status_code})"
            )

        assets: list[ConnectorAsset] = []
        for module in response.json().get("modules", []):
            api_name = str(module.get("api_name", "")).strip()
            if not api_name or not module.get("api_supported", True):
                continue
            label = str(module.get("plural_label") or module.get("singular_label") or api_name)
            assets.append(
                ConnectorAsset(
                    external_id=api_name,
                    name=label,
                    kind="crm_module",
                    config={"module": api_name},
                )
            )
        return assets

    async def fetch(self, source_config: dict[str, Any]) -> FetchedTable:
        module = str(source_config.get("module", "")).strip()
        if not module:
            raise ConnectorError("A Zoho module is required for this data source")

        token = await self._access_token()
        headers = {"Authorization": f"Zoho-oauthtoken {token}"}
        records: list[dict[str, Any]] = []
        columns: list[str] = []
        seen_columns: set[str] = set()
        pages = 0

        async with httpx.AsyncClient(timeout=60) as client:
            page = 1
            while page <= MAX_PAGES:
                response = await client.get(
                    f"{self.api_domain}/crm/{API_VERSION}/{module}",
                    params={"page": page, "per_page": PAGE_SIZE},
                    headers=headers,
                )
                if response.status_code in (401, 403):
                    raise ConnectorAuthError(
                        "Zoho denied access to this module. Check the token scopes."
                    )
                if response.status_code != 200:
                    raise ConnectorFetchError(
                        f"Could not read Zoho {module} ({response.status_code})"
                    )
                payload = response.json()
                page_records = payload.get("data", []) or []
                pages += 1
                for record in page_records:
                    record_id = str(record.get("id", "")) or None
                    row = {
                        key: _json_safe(value)
                        for key, value in record.items()
                        if key not in {"$approval", "$process_flow", "$editable", "$review_process"}
                    }
                    if record_id:
                        row["id"] = record_id
                    records.append(row)
                    for key in row:
                        if key not in seen_columns:
                            seen_columns.add(key)
                            columns.append(key)

                if not payload.get("info", {}).get("more_records"):
                    break
                page += 1

        partial = pages >= MAX_PAGES
        return FetchedTable(
            columns=columns,
            rows=records,
            partial=partial,
            metadata={"module": module, "pages": pages},
        )


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return str(value)
