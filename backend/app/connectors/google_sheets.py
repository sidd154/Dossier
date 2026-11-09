"""Google Sheets adapter using a service account.

A service account key is signed locally into an OAuth assertion, exchanged for an
access token, then used against the Sheets v4 REST API. The spreadsheet must be shared
with the service account address.
"""

import base64
import hashlib
import json
import time
from typing import Any

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from app.connectors.base import (
    BaseConnector,
    ConnectorAsset,
    ConnectorAuthError,
    ConnectorError,
    ConnectorFetchError,
    FetchedTable,
)

SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
DEFAULT_TOKEN_URI = "https://oauth2.googleapis.com/token"


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _normalise_private_key(raw: str) -> str:
    # Keys pasted into JSON forms often arrive with literal backslash-n sequences.
    return raw.replace("\\n", "\n")


def _build_assertion(*, client_email: str, private_key: str, token_uri: str) -> str:
    now = int(time.time())
    header = {"alg": "RS256", "typ": "JWT"}
    claims = {
        "iss": client_email,
        "scope": " ".join(SCOPES),
        "aud": token_uri,
        "iat": now,
        "exp": now + 3600,
    }
    signing_input = (
        f"{_b64url(json.dumps(header, separators=(',', ':')).encode())}."
        f"{_b64url(json.dumps(claims, separators=(',', ':')).encode())}"
    ).encode("ascii")

    try:
        key = serialization.load_pem_private_key(
            _normalise_private_key(private_key).encode("utf-8"), password=None
        )
    except (ValueError, TypeError) as exc:
        raise ConnectorAuthError(
            "The service account private key is not a valid PEM key"
        ) from exc
    if not isinstance(key, rsa.RSAPrivateKey):
        raise ConnectorAuthError("The service account key must be an RSA private key")
    signature = key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return f"{signing_input.decode('ascii')}.{_b64url(signature)}"


def column_hash(columns: list[str]) -> str:
    return hashlib.sha256(json.dumps(columns).encode("utf-8")).hexdigest()


class GoogleSheetsConnector(BaseConnector):
    def _spreadsheet_id(self) -> str:
        spreadsheet_id = str(self.config.get("spreadsheet_id", "")).strip()
        if not spreadsheet_id:
            raise ConnectorError("A spreadsheet id is required")
        return spreadsheet_id

    def _credential(self, key: str) -> str:
        value = str(self.credentials.get(key, "")).strip()
        if not value:
            raise ConnectorAuthError(f"Google Sheets credential '{key}' is missing")
        return value

    async def _access_token(self) -> str:
        token_uri = self.credentials.get("token_uri") or DEFAULT_TOKEN_URI
        assertion = _build_assertion(
            client_email=self._credential("client_email"),
            private_key=self._credential("private_key"),
            token_uri=str(token_uri),
        )
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                str(token_uri),
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": assertion,
                },
            )
        if response.status_code != 200:
            raise ConnectorAuthError(
                f"Google rejected the service account ({response.status_code})"
            )
        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise ConnectorAuthError("Google returned no access token")
        return str(token)

    async def validate(self) -> None:
        token = await self._access_token()
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{SHEETS_API}/{self._spreadsheet_id()}",
                params={"fields": "properties.title"},
                headers={"Authorization": f"Bearer {token}"},
            )
        if response.status_code in (401, 403):
            raise ConnectorAuthError(
                "Google denied access. Share the spreadsheet with the service account."
            )
        if response.status_code != 200:
            raise ConnectorFetchError(
                f"Could not read the spreadsheet ({response.status_code})"
            )

    async def list_assets(self) -> list[ConnectorAsset]:
        token = await self._access_token()
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{SHEETS_API}/{self._spreadsheet_id()}",
                params={"fields": "sheets.properties(title,sheetId)"},
                headers={"Authorization": f"Bearer {token}"},
            )
        if response.status_code in (401, 403):
            raise ConnectorAuthError(
                "Google denied access. Share the spreadsheet with the service account."
            )
        if response.status_code != 200:
            raise ConnectorFetchError(
                f"Could not list sheets ({response.status_code})"
            )

        assets: list[ConnectorAsset] = []
        for sheet in response.json().get("sheets", []):
            properties = sheet.get("properties", {})
            title = str(properties.get("title", "")).strip()
            sheet_id = properties.get("sheetId")
            if not title or sheet_id is None:
                continue
            assets.append(
                ConnectorAsset(
                    external_id=str(sheet_id),
                    name=title,
                    kind="sheet",
                    config={
                        "spreadsheet_id": self._spreadsheet_id(),
                        "sheet_title": title,
                    },
                )
            )
        return assets

    async def fetch(self, source_config: dict[str, Any]) -> FetchedTable:
        token = await self._access_token()
        spreadsheet_id = str(
            source_config.get("spreadsheet_id") or self._spreadsheet_id()
        )
        sheet_title = str(source_config.get("sheet_title", "")).strip()
        if not sheet_title:
            raise ConnectorError("A sheet title is required for this data source")

        range_name = source_config.get("range") or f"'{sheet_title}'"
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(
                f"{SHEETS_API}/{spreadsheet_id}/values/{range_name}",
                params={
                    "majorDimension": "ROWS",
                    "valueRenderOption": "UNFORMATTED_VALUE",
                    "dateTimeRenderOption": "FORMATTED_STRING",
                },
                headers={"Authorization": f"Bearer {token}"},
            )
        if response.status_code in (401, 403):
            raise ConnectorAuthError(
                "Google denied access to this sheet. Check the service account share."
            )
        if response.status_code != 200:
            raise ConnectorFetchError(
                f"Could not read '{sheet_title}' ({response.status_code})"
            )

        values: list[list[Any]] = response.json().get("values", []) or []
        if not values:
            return FetchedTable(columns=[], rows=[], metadata={"sheet": sheet_title})

        columns = unique_headers(values[0])
        rows: list[dict[str, Any]] = []
        for raw_row in values[1:]:
            if not any(cell not in (None, "") for cell in raw_row):
                continue
            padded = list(raw_row) + [None] * (len(columns) - len(raw_row))
            rows.append(
                {
                    column: _json_safe(padded[index])
                    for index, column in enumerate(columns)
                }
            )

        return FetchedTable(
            columns=columns,
            rows=rows,
            metadata={"sheet": sheet_title, "spreadsheet_id": spreadsheet_id},
        )


def unique_headers(raw: list[Any]) -> list[str]:
    seen: dict[str, int] = {}
    headers: list[str] = []
    for index, value in enumerate(raw):
        base = str(value).strip() if value not in (None, "") else f"column_{index + 1}"
        count = seen.get(base, 0)
        seen[base] = count + 1
        headers.append(base if count == 0 else f"{base}_{count + 1}")
    return headers


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
