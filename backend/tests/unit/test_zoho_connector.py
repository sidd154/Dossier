import httpx
import pytest

from app.connectors.base import ConnectorAuthError, ConnectorFetchError
from app.connectors.zoho_crm import ZohoCrmConnector

CREDENTIALS = {
    "client_id": "client",
    "client_secret": "secret",
    "refresh_token": "refresh",
}
CONFIG = {"api_domain": "https://www.zohoapis.com"}


_REAL_CLIENT = httpx.AsyncClient


def _patch_client(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    transport = httpx.MockTransport(handler)

    def factory(*_args: object, **_kwargs: object) -> httpx.AsyncClient:
        return _REAL_CLIENT(transport=transport)

    monkeypatch.setattr("app.connectors.zoho_crm.httpx.AsyncClient", factory)


async def test_validate_exchanges_refresh_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == "/oauth/v2/token":
            return httpx.Response(200, json={"access_token": "zoho-token"})
        return httpx.Response(200, json={"modules": []})

    _patch_client(monkeypatch, handler)
    connector = ZohoCrmConnector(config=CONFIG, credentials=CREDENTIALS)

    await connector.validate()

    assert paths == ["/oauth/v2/token", "/crm/v8/settings/modules"]


async def test_validate_rejects_bad_refresh_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_client(
        monkeypatch,
        lambda _request: httpx.Response(400, json={"error": "invalid_code"}),
    )
    connector = ZohoCrmConnector(config=CONFIG, credentials=CREDENTIALS)

    with pytest.raises(ConnectorAuthError):
        await connector.validate()


async def test_list_assets_skips_unsupported_modules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth/v2/token":
            return httpx.Response(200, json={"access_token": "zoho-token"})
        return httpx.Response(
            200,
            json={
                "modules": [
                    {"api_name": "Leads", "plural_label": "Leads", "api_supported": True},
                    {"api_name": "Notes", "api_supported": False},
                ]
            },
        )

    _patch_client(monkeypatch, handler)
    connector = ZohoCrmConnector(config=CONFIG, credentials=CREDENTIALS)

    assets = await connector.list_assets()

    assert [asset.external_id for asset in assets] == ["Leads"]
    assert assets[0].kind == "crm_module"
    assert assets[0].config == {"module": "Leads"}


async def test_fetch_paginates_and_normalises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth/v2/token":
            return httpx.Response(200, json={"access_token": "zoho-token"})
        page = request.url.params.get("page")
        if page == "1":
            return httpx.Response(
                200,
                json={
                    "data": [{"id": "1", "Last_Name": "Alpha", "Owner": {"name": "Sam"}}],
                    "info": {"more_records": True},
                },
            )
        return httpx.Response(
            200,
            json={
                "data": [{"id": "2", "Last_Name": "Beta"}],
                "info": {"more_records": False},
            },
        )

    _patch_client(monkeypatch, handler)
    connector = ZohoCrmConnector(config=CONFIG, credentials=CREDENTIALS)

    table = await connector.fetch({"module": "Leads"})

    assert len(table.rows) == 2
    assert table.rows[0]["Owner"] == {"name": "Sam"}
    assert table.columns == ["id", "Last_Name", "Owner"]
    assert table.partial is False
    assert table.metadata["pages"] == 2


async def test_fetch_reports_upstream_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth/v2/token":
            return httpx.Response(200, json={"access_token": "zoho-token"})
        return httpx.Response(500, text="boom")

    _patch_client(monkeypatch, handler)
    connector = ZohoCrmConnector(config=CONFIG, credentials=CREDENTIALS)

    with pytest.raises(ConnectorFetchError):
        await connector.fetch({"module": "Leads"})
