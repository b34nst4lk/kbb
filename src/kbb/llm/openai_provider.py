"""OpenAI LLM provider.

Also serves as the base for any OpenAI-compatible endpoint
(Ollama, Azure OpenAI, etc.) via the base_url parameter.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from openai.types.chat.completion_create_params import ResponseFormatJSONSchema


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

        When json_schema is provided, uses OpenAI's structured output
        (response_format with json_schema type) to guarantee the response
        conforms to the schema with strict validation.
        """
        messages: list[ChatCompletionMessageParam] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict = {
            "model": self._model,
            "max_tokens": 4096,
            "messages": messages,
        }
        if json_schema:
            kwargs["response_format"] = ResponseFormatJSONSchema(
                type="json_schema",
                json_schema={
                    "name": "response",
                    "strict": True,
                    "schema": json_schema,
                },
            )

        response = await self._client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    async def stream(self, prompt: str, *, system: str = "") -> AsyncGenerator[str, None]:
        """Streaming completion. Yields response chunks."""
        messages: list[ChatCompletionMessageParam] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        async with self._client.chat.completions.stream(
            model=self._model,
            max_tokens=4096,
            messages=messages,
        ) as stream:
            async for event in stream:
                if event.type == "content.delta.delta" and event.delta:
                    yield event.delta
