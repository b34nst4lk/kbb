"""Anthropic (Claude) LLM provider."""

from __future__ import annotations

from typing import AsyncIterator

import anthropic


class AnthropicProvider:
    """Anthropic/Claude implementation of LLMProvider."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
    ) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    @property
    def name(self) -> str:
        return f"anthropic/{self._model}"

    async def complete(
        self, prompt: str, *, system: str = "", json_schema: dict | None = None
    ) -> str:
        """Single completion. Returns the full response text.

        json_schema is accepted for API compatibility but not used
        — Anthropic's API doesn't support guided decoding.
        """
        kwargs: dict = {
            "model": self._model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        response = await self._client.messages.create(**kwargs)
        return response.content[0].text

    async def stream(self, prompt: str, *, system: str = "") -> AsyncIterator[str]:
        """Streaming completion. Yields response chunks."""
        kwargs: dict = {
            "model": self._model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        async with self._client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text
