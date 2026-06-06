"""LLM abstraction layer — provider protocol, client, and factory."""

from __future__ import annotations

import json
import re
from typing import AsyncIterator, Protocol, runtime_checkable

from kbb.models import KnowledgeEntry, Question, QuestionTopic, UserProfile
from kbb.llm.prompts import (
    GENERATE_QUESTION_PROMPT,
    GENERATE_QUESTION_SYSTEM,
    GENERATE_SLUG_PROMPT,
    GENERATE_SLUG_SYSTEM,
    PROFILE_SCHEMA,
    QUESTION_SCHEMA,
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

    async def stream(self, prompt: str, *, system: str = "") -> AsyncIterator[str]: ...


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
            json_schema=PROFILE_SCHEMA,
        )
        return self._parse_json_response(response)

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
            json_schema=QUESTION_SCHEMA,
        )
        data = self._parse_json_response(response)
        return Question(
            text=data["text"],
            topic=QuestionTopic(data.get("topic", "general")),
            rationale=data.get("rationale", ""),
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
        slug = result.strip().strip('"\'').lower()
        # Remove any non-alphanumeric characters except hyphens
        slug = re.sub(r"[^a-z0-9-]", "", slug)
        slug = re.sub(r"-+", "-", slug).strip("-")
        # Fallback if slug is empty
        if not slug:
            slug = "daily-log"
        return slug

    @staticmethod
    def _parse_json_response(text: str) -> dict:
        """Parse a JSON response from the LLM, handling common issues.

        Handles: markdown code fences, embedded JSON in conversational text,
        and truncated JSON with unclosed brackets.
        """
        # Strip markdown code fences if present
        text = text.strip()
        if text.startswith("```"):
            # Remove opening fence (and language tag like ```json)
            first_newline = text.index("\n")
            text = text[first_newline + 1 :]
            # Remove closing fence
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to find JSON object in the text
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and start < end:
            candidate = text[start : end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                # Try to auto-close truncated JSON
                closed = LLMClient._try_close_json(candidate)
                if closed:
                    try:
                        return json.loads(closed)
                    except json.JSONDecodeError:
                        pass

        # Last resort: try auto-closing on the full text
        closed = LLMClient._try_close_json(text)
        if closed:
            try:
                return json.loads(closed)
            except json.JSONDecodeError:
                pass

        raise ValueError(f"Failed to parse LLM response as JSON: {text[:200]}")

    @staticmethod
    def _try_close_json(text: str) -> str | None:
        """Attempt to close unclosed brackets in truncated JSON.

        Counts unclosed { and [ and appends matching } and ].
        Returns the closed string, or None if no fix was needed/possible.
        """
        open_braces = 0
        open_brackets = 0
        in_string = False
        escape_next = False

        for char in text:
            if escape_next:
                escape_next = False
                continue
            if char == "\\":
                escape_next = True
                continue
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == "{":
                open_braces += 1
            elif char == "}":
                open_braces -= 1
            elif char == "[":
                open_brackets += 1
            elif char == "]":
                open_brackets -= 1

        if open_braces <= 0 and open_brackets <= 0:
            return None  # already balanced

        # Append closing brackets in reverse order
        suffix = "]" * max(0, open_brackets) + "}" * max(0, open_braces)
        return text + suffix


def create_provider(
    provider_type: str,
    *,
    api_key: str,
    model: str,
    base_url: str = "",
) -> LLMProvider:
    """Factory function to instantiate a provider by name."""
    match provider_type:
        case "anthropic":
            from kbb.llm.anthropic_provider import AnthropicProvider

            return AnthropicProvider(api_key=api_key, model=model)
        case "openai":
            from kbb.llm.openai_provider import OpenAIProvider

            return OpenAIProvider(
                api_key=api_key, model=model,
                base_url=base_url or None,
            )
        case "ollama":
            from kbb.llm.ollama_provider import OllamaProvider

            # Native Ollama provider supports JSON schema-guided decoding
            host = base_url if base_url else "http://localhost:11434"
            # Strip /v1 suffix if present (from old OpenAI-compatible config)
            if host.endswith("/v1"):
                host = host[:-3]
            return OllamaProvider(model=model, host=host)
        case _:
            raise ValueError(
                f"Unknown LLM provider: {provider_type}. "
                f"Supported: anthropic, openai, ollama"
            )