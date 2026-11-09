import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.connectors.base import ConnectorAuthError, ConnectorError, ConnectorFetchError
from app.connectors.google_sheets import GoogleSheetsConnector

_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.TraditionalOpenSSL,
    encryption_algorithm=serialization.NoEncryption(),
).decode("ascii")

CREDENTIALS = {
    "client_email": "service@example.iam.gserviceaccount.com",
    "private_key": _PRIVATE_KEY,
}
CONFIG = {"spreadsheet_id": "spreadsheet-1"}


_REAL_CLIENT = httpx.AsyncClient


def _patch_client(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    transport = httpx.MockTransport(handler)

    def factory(*_args: object, **_kwargs: object) -> httpx.AsyncClient:
        return _REAL_CLIENT(transport=transport)

    monkeypatch.setattr(
        "app.connectors.google_sheets.httpx.AsyncClient", factory
    )


def _token_handler(seen: list[str]):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "token-1"})
        if "sheets" not in request.url.path:
            return httpx.Response(200, json={"properties": {"title": "Book"}})
        return httpx.Response(200, json={"properties": {"title": "Book"}})

    return handler


async def test_validate_signs_and_exchanges_a_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []
    _patch_client(monkeypatch, _token_handler(seen))

    connector = GoogleSheetsConnector(config=CONFIG, credentials=CREDENTIALS)
    await connector.validate()

    assert seen[0].endswith("/token")
    assert any("spreadsheet-1" in url for url in seen)


async def test_validate_rejects_bad_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_client(
        monkeypatch,
        lambda _request: httpx.Response(401, json={"error": "invalid_grant"}),
    )
    connector = GoogleSheetsConnector(config=CONFIG, credentials=CREDENTIALS)

    with pytest.raises(ConnectorAuthError):
        await connector.validate()


async def test_validate_reports_missing_spreadsheet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connector = GoogleSheetsConnector(config={}, credentials=CREDENTIALS)
    with pytest.raises(ConnectorError):
        await connector.validate()


async def test_malformed_private_key_is_reported_cleanly() -> None:
    connector = GoogleSheetsConnector(
        config=CONFIG,
        credentials={"client_email": "svc@example.com", "private_key": "not-a-key"},
    )

    with pytest.raises(ConnectorAuthError) as error:
        await connector.validate()

    assert "not a valid PEM key" in str(error.value)


async def test_list_assets_maps_sheet_tabs(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "token-1"})
        return httpx.Response(
            200,
            json={
                "sheets": [
                    {"properties": {"title": "Sales", "sheetId": 0}},
                    {"properties": {"title": "HR", "sheetId": 42}},
                ]
            },
        )

    _patch_client(monkeypatch, handler)
    connector = GoogleSheetsConnector(config=CONFIG, credentials=CREDENTIALS)

    assets = await connector.list_assets()

    assert [asset.external_id for asset in assets] == ["0", "42"]
    assert [asset.name for asset in assets] == ["Sales", "HR"]
    assert assets[0].config == {"spreadsheet_id": "spreadsheet-1", "sheet_title": "Sales"}


async def test_fetch_parses_headers_rows_and_skips_empty_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "token-1"})
        return httpx.Response(
            200,
            json={
                "values": [
                    ["Name", "Amount", "Amount"],
                    ["Alpha", 100, 1],
                    ["", "", ""],
                    ["Beta", 250],
                ]
            },
        )

    _patch_client(monkeypatch, handler)
    connector = GoogleSheetsConnector(config=CONFIG, credentials=CREDENTIALS)

    table = await connector.fetch({"sheet_title": "Sales"})

    assert table.columns == ["Name", "Amount", "Amount_2"]
    assert len(table.rows) == 2
    assert table.rows[0] == {"Name": "Alpha", "Amount": 100, "Amount_2": 1}
    assert table.rows[1] == {"Name": "Beta", "Amount": 250, "Amount_2": None}


async def test_fetch_reports_upstream_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "token-1"})
        return httpx.Response(500, text="boom")

    _patch_client(monkeypatch, handler)
    connector = GoogleSheetsConnector(config=CONFIG, credentials=CREDENTIALS)

    with pytest.raises(ConnectorFetchError):
        await connector.fetch({"sheet_title": "Sales"})
