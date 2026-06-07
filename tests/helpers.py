"""Shared test helpers — reusable across test files."""

from __future__ import annotations

from collections.abc import AsyncGenerator


class MockProvider:
    """In-memory LLM provider that returns canned responses for testing.

    Matches on unique phrases from each system prompt to avoid
    false positives (e.g. "Profile" appearing in question prompts).
    """

    def __init__(self, responses: dict[str, str] | None = None) -> None:
        self._responses = responses or {}
        self._calls: list[tuple[str, str]] = []  # (system, prompt)

    @property
    def name(self) -> str:
        return "mock"

    async def complete(
        self, prompt: str, *, system: str = "", json_schema: dict | None = None
    ) -> str:
        self._calls.append((system, prompt))
        # Match on unique phrases from system prompts to avoid false positives.
        # Both profile and question prompts start with "precise JSON generator",
        # so we match on the distinguishing second phrase.
        if "self-description" in system.lower() or "profile analyst" in system.lower():
            return self._responses.get(
                "profile",
                '{"name": "Test User", "education": ["BS Computer Science"], '
                '"work_experience": ["Software Engineer at TestCo"], '
                '"life_experience": [], "interests": ["Python", "AI"]}',
            )
        if (
            "knowledge extraction" in system.lower()
            or "knowledge extraction coach" in system.lower()
        ):
            return self._responses.get(
                "question",
                '{"text": "What testing strategy do you prefer?", '
                '"topic": "skill", "rationale": "Testing prompt"}',
            )
        if "knowledge recorder" in system.lower():
            return self._responses.get(
                "record",
                "## Recorded Knowledge\n\nThe user prefers pytest for testing.",
            )
        if "descriptive file slugs" in system.lower():
            return self._responses.get(
                "slug",
                "skill-testing-approach",
            )
        return self._responses.get("default", "Mock response")

    async def stream(self, prompt: str, *, system: str = "") -> AsyncGenerator[str, None]:
        response = await self.complete(prompt, system=system)
        yield response
