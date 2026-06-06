"""Shared test fixtures for Knowledge Base Builder tests."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from kbb.llm.base import LLMClient
from kbb.models import (
    DailyLog,
    KBBConfig,
    KnowledgeEntry,
    LLMProviderName,
    Question,
    QuestionTopic,
    UserProfile,
)
from kbb.storage.markdown_store import MarkdownStore
from tests.helpers import MockProvider


@pytest.fixture
def mock_llm_client() -> tuple[LLMClient, MockProvider]:
    """Provide an LLMClient backed by MockProvider."""
    provider = MockProvider()
    return LLMClient(provider), provider


@pytest.fixture
def temp_data_dir(tmp_path: Path) -> Path:
    """Provide a temporary data directory for storage tests."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def mock_store(temp_data_dir: Path) -> MarkdownStore:
    """Provide a MarkdownStore with a temp directory."""
    return MarkdownStore(temp_data_dir)


@pytest.fixture
def sample_profile() -> UserProfile:
    """Provide a sample UserProfile for testing."""
    return UserProfile(
        name="Jane Doe",
        education=["BS Computer Science, MIT", "MS AI, Stanford"],
        work_experience=["Software Engineer at Google", "ML Engineer at OpenAI"],
        life_experience=["Lived in Japan for 2 years", "Volunteered at animal shelter"],
        interests=["Python", "Machine Learning", "Hiking"],
        raw_markdown="# About Me\n\nI'm Jane...",
        last_updated=datetime(2026, 6, 6, 12, 0, 0),
    )


@pytest.fixture
def sample_entry() -> KnowledgeEntry:
    """Provide a sample KnowledgeEntry for testing."""
    return KnowledgeEntry(
        title="My Testing Philosophy",
        content="I prefer pytest over unittest...",
        topic=QuestionTopic.SKILL,
        source="daily_log",
        created_at=date(2026, 6, 5),
        tags=["daily-log", "skill"],
    )


@pytest.fixture
def sample_daily_log() -> DailyLog:
    """Provide a sample DailyLog for testing."""
    return DailyLog(
        log_timestamp=datetime(2026, 6, 5, 14, 30),
        question="What testing framework do you prefer?",
        question_topic=QuestionTopic.SKILL,
        question_rationale="The user has software engineering experience",
        response="I prefer pytest because it's more Pythonic",
        recorded_entry="## Testing Preference\n\nI prefer pytest because it is more Pythonic.",
        slug="skill-testing-preference",
    )


@pytest.fixture
def sample_question() -> Question:
    """Provide a sample Question for testing."""
    return Question(
        text="What testing strategy do you prefer?",
        topic=QuestionTopic.SKILL,
        rationale="The user has software engineering experience",
    )