"""OpenAI LLM provider.

Also serves as the base for any OpenAI-compatible endpoint
(Ollama, Azure OpenAI, etc.) via the base_url parameter.
"""

from __future__ import annotations

from typing import AsyncIterator

from openai import AsyncOpenAI


class OpenAIProvider:
    """OpenAI implementation of LLMProvider.

    Supports any OpenAI-compatible API by passing a custom base_url.
    This includes Ollama, Azure OpenAI, LM Studio, etc.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gpt-4o",
        base_url: str | None = None,
    ) -> None:
        kwargs: dict = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = AsyncOpenAI(**kwargs)
        self._model = model
        self._base_url = base_url

    @property
    def name(self) -> str:
        if self._base_url:
            return f"openai-compatible/{self._model} ({self._base_url})"
        return f"openai/{self._model}"

    async def complete(
        self, prompt: str, *, system: str = "", json_schema: dict | None = None
    ) -> str:
        """Single completion. Returns the full response text.

        When json_schema is provided, uses response_format to request
        JSON output (OpenAI doesn't support schema-guided decoding,
        but json_object mode improves reliability).
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict = {
            "model": self._model,
            "max_tokens": 4096,
            "messages": messages,
        }
        if json_schema:
            kwargs["response_format"] = {"type": "json_object"}

        response = await self._client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    async def stream(self, prompt: str, *, system: str = "") -> AsyncIterator[str]:
        """Streaming completion. Yields response chunks."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=4096,
            messages=messages,
            stream=True,
        )
        async for chunk in response:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content
