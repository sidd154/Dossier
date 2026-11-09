"""Ollama adapter used for mail-body generation."""

from collections.abc import Sequence

import httpx

from app.core.exceptions import UpstreamError
from app.llm.provider import ChatMessage


class OllamaProvider:
    def __init__(self, *, base_url: str, model: str, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> str:
        options: dict[str, object] = {"temperature": temperature}
        if max_tokens is not None:
            options["num_predict"] = max_tokens

        payload = {
            "model": self.model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in messages
            ],
            "stream": False,
            "options": options,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.base_url}/api/chat", json=payload)
        except httpx.HTTPError as exc:
            raise UpstreamError("The language model is unavailable") from exc

        if response.status_code != 200:
            raise UpstreamError(
                f"The language model returned {response.status_code}"
            )

        payload_json = response.json()
        message = payload_json.get("message") or {}
        content = str(message.get("content") or "").strip()
        if not content:
            raise UpstreamError("The language model returned an empty response")
        return content
