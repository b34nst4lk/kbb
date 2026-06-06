"""Native Ollama LLM provider.

Uses the ollama Python SDK directly (not the OpenAI-compatible API)
to access Ollama's native features like JSON schema-guided decoding
via the `format` parameter.
"""

from __future__ import annotations

from typing import AsyncIterator

import ollama


class OllamaProvider:
    """Ollama implementation of LLMProvider.

    Uses the native Ollama API, which supports the `format` parameter
    for JSON schema-guided decoding. When a json_schema is provided,
    Ollama constrains the output to match the schema, guaranteeing
    structurally valid JSON.
    """

    def __init__(
        self,
        *,
        model: str = "llama3",
        host: str = "http://localhost:11434",
    ) -> None:
        self._client = ollama.AsyncClient(host=host)
        self._model = model
        self._host = host

    @property
    def name(self) -> str:
        return f"ollama/{self._model} ({self._host})"

    async def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        json_schema: dict | None = None,
    ) -> str:
        """Single completion. Returns the full response text.

        When json_schema is provided, Ollama uses guided decoding
        to force the output to match the schema as valid JSON.
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict = {
            "model": self._model,
            "messages": messages,
        }
        if json_schema:
            kwargs["format"] = json_schema

        response = await self._client.chat(**kwargs)
        return response.message.content or ""

    async def stream(
        self,
        prompt: str,
        *,
        system: str = "",
    ) -> AsyncIterator[str]:
        """Streaming completion. Yields response chunks."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = await self._client.chat(
            model=self._model,
            messages=messages,
            stream=True,
        )
        async for chunk in response:
            if chunk.message.content:
                yield chunk.message.content