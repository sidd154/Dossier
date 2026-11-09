"""Deterministic stand-ins for external systems."""

from collections.abc import Sequence
from typing import Any

from app.connectors.base import BaseConnector, ConnectorAsset, FetchedTable
from app.llm.provider import ChatMessage


class FakeConnector(BaseConnector):
    def __init__(
        self,
        *,
        table: FetchedTable | None = None,
        assets: list[ConnectorAsset] | None = None,
        error: Exception | None = None,
        validate_error: Exception | None = None,
    ) -> None:
        super().__init__(config={}, credentials={})
        self.table = table or FetchedTable(
            columns=["id", "name", "amount"],
            rows=[
                {"id": "1", "name": "Alpha", "amount": 100},
                {"id": "2", "name": "Beta", "amount": 250},
            ],
        )
        self.assets = assets or [
            ConnectorAsset(
                external_id="asset-1",
                name="Sheet One",
                kind="sheet",
                config={"sheet_title": "Sheet One"},
            )
        ]
        self.error = error
        self.validate_error = validate_error

    async def validate(self) -> None:
        if self.validate_error is not None:
            raise self.validate_error

    async def list_assets(self) -> list[ConnectorAsset]:
        if self.error is not None:
            raise self.error
        return self.assets

    async def fetch(self, source_config: dict[str, Any]) -> FetchedTable:
        if self.error is not None:
            raise self.error
        return self.table


class FakeLLM:
    """Records every prompt so tests can assert what the model was allowed to see."""

    def __init__(
        self, reply: str = "Generated summary body.", error: Exception | None = None
    ) -> None:
        self.reply = reply
        self.error = error
        self.calls: list[list[ChatMessage]] = []

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> str:
        self.calls.append(list(messages))
        if self.error is not None:
            raise self.error
        return self.reply

    @property
    def prompts(self) -> list[str]:
        return [
            "\n".join(message.content for message in call) for call in self.calls
        ]
