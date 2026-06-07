"""LLM abstraction layer — provider protocol, client, and factory."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncGenerator
from typing import Protocol, runtime_checkable

from kbb.models import KnowledgeEntry, Question, UserProfile
from kbb.llm.schemas import ProfileSchema, QuestionSchema, PROFILE_JSON_SCHEMA, QUESTION_JSON_SCHEMA
from kbb.llm.prompts import (
    GENERATE_QUESTION_PROMPT,
    GENERATE_QUESTION_SYSTEM,
    GENERATE_SLUG_PROMPT,
    GENERATE_SLUG_SYSTEM,
    RECORD_RESPONSE_PROMPT,
    RECORD_RESPONSE_SYSTEM,
    UNDERSTAND_PROFILE_PROMPT,
    UNDERSTAND_PROFILE_SYSTEM,
)


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol that all LLM backends must implement."""

    @property
    def name(self) -> str: ...

    async def complete(
        self, prompt: str, *, system: str = "", json_schema: dict | None = None
    ) -> str: ...

    def stream(self, prompt: str, *, system: str = "") -> AsyncGenerator[str, None]:
        """Stream text tokens. Does not accept json_schema — callers needing
        structured output must use ``complete()`` instead."""
        ...


class LLMClient:
    """High-level client that owns a provider and exposes domain-specific operations.

    This is what the engine calls — it never interacts with the raw provider
    or prompt templates directly.
    """

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    @property
    def provider_name(self) -> str:
        return self._provider.name

    async def understand_profile(self, raw_profile_markdown: str) -> dict:
        """Parse freeform profile text into structured fields.

        Returns a dict matching UserProfile fields.
        """
        prompt = UNDERSTAND_PROFILE_PROMPT.format(profile_text=raw_profile_markdown)
        response = await self._provider.complete(
            prompt,
            system=UNDERSTAND_PROFILE_SYSTEM,
            json_schema=PROFILE_JSON_SCHEMA,
        )
        data = self._parse_json_response(response)
        # Validate with Pydantic — defaults fill in missing fields
        profile = ProfileSchema.model_validate(data)
        return profile.model_dump()

    async def generate_question(
        self,
        profile: UserProfile,
        knowledge_entries: list[KnowledgeEntry],
        recent_questions: list[str],
    ) -> Question:
        """Generate a question tailored to what we don't yet know about this user."""
        profile_summary = profile.summary or "No profile information yet."
        knowledge_topics = (
            "\n".join(f"- {e.title} [{e.topic.value}]" for e in knowledge_entries)
            if knowledge_entries
            else "No knowledge documented yet."
        )
        recent = (
            "\n".join(f"- {q}" for q in recent_questions)
            if recent_questions
            else "No recent questions."
        )

        prompt = GENERATE_QUESTION_PROMPT.format(
            profile_summary=profile_summary,
            knowledge_topics=knowledge_topics,
            recent_questions=recent,
        )
        response = await self._provider.complete(
            prompt,
            system=GENERATE_QUESTION_SYSTEM,
            json_schema=QUESTION_JSON_SCHEMA,
        )
        data = self._parse_json_response(response)
        # Validate with Pydantic — handles enum conversion and defaults
        question = QuestionSchema.model_validate(data)
        return Question(
            text=question.text,
            topic=question.topic,
            rationale=question.rationale,
        )

    async def record_response(
        self,
        question: str,
        response: str,
        profile: UserProfile,
    ) -> str:
        """Record the user's response into a coherent knowledge entry.

        CRITICAL: Adds NO outside information. Only reorganizes,
        clarifies, and formats what the user actually said.
        """
        prompt = RECORD_RESPONSE_PROMPT.format(
            question=question,
            response=response,
            profile_summary=profile.summary or "No profile information available.",
        )
        recorded = await self._provider.complete(prompt, system=RECORD_RESPONSE_SYSTEM)
        return recorded.strip()

    async def generate_slug(self, question: str, response: str) -> str:
        """Generate a short descriptive slug for a log file name.

        Returns a lowercase hyphenated slug, 3-5 words.
        """
        # Use first 200 chars of response to keep the prompt short
        response_summary = response[:200] if len(response) > 200 else response
        prompt = GENERATE_SLUG_PROMPT.format(question=question, response=response_summary)
        result = await self._provider.complete(prompt, system=GENERATE_SLUG_SYSTEM)
        # Clean up: strip quotes, whitespace, and ensure lowercase hyphenated
        slug = result.strip().strip("\"'").lower()
        # Remove any non-alphanumeric characters except hyphens
        slug = re.sub(r"[^a-z0-9-]", "", slug)
        slug = re.sub(r"-+", "-", slug).strip("-")
        # Fallback if slug is empty
        if not slug:
            slug = "daily-log"
        return slug

    @staticmethod
    def _parse_json_response(text: str) -> dict:
        """Parse a JSON response from the LLM.

        With provider-native structured output, responses are guaranteed
        to be valid JSON. A parse failure here indicates a provider bug
        or a model that doesn't support structured output.
        """
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            raise ValueError(
                f"LLM returned invalid JSON (provider should guarantee valid JSON): {text[:200]}"
            )


def create_provider(
    provider_type: str,
    *,
    api_key: str,
    model: str,
    base_url: str = "",
) -> LLMProvider:
    """Factory function to instantiate a provider by name.

    Note: ``api_key`` is not forwarded to the Ollama provider, which
    runs locally and does not require authentication.
    """
    match provider_type:
        case "anthropic":
            from kbb.llm.anthropic_provider import AnthropicProvider

            return AnthropicProvider(api_key=api_key, model=model)
        case "openai":
            from kbb.llm.openai_provider import OpenAIProvider

            return OpenAIProvider(
                api_key=api_key,
                model=model,
                base_url=base_url or None,
            )
        case "ollama":
            from kbb.llm.ollama_provider import OllamaProvider

            host = base_url if base_url else "http://localhost:11434"
            # Strip /v1 suffix if present (from old OpenAI-compatible config)
            if host.endswith("/v1"):
                host = host[:-3]
            return OllamaProvider(model=model, host=host)
        case _:
            raise ValueError(
                f"Unknown LLM provider: {provider_type}. Supported: anthropic, openai, ollama"
            )
