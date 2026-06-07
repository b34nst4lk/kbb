"""Tests for KBPEngine."""

from datetime import date
from pathlib import Path

import pytest

from kbb.engine import KBPEngine
from kbb.llm.base import LLMClient
from kbb.models import KBBConfig, Question, QuestionTopic
from tests.helpers import MockProvider


class TestEngineProfileSetup:
    @pytest.mark.asyncio
    async def test_setup_profile_from_text(self, temp_data_dir: Path):
        provider = MockProvider()
        llm_client = LLMClient(provider)
        config = KBBConfig(data_dir=temp_data_dir, llm_api_key="test")
        engine = KBPEngine(config)
        engine._llm = llm_client

        profile = await engine.setup_profile_from_text("I'm a software engineer")
        assert profile.name == "Test User"
        assert "BS Computer Science" in profile.education

        # Verify profile was saved
        raw = engine.get_raw_profile()
        assert "software engineer" in raw

    @pytest.mark.asyncio
    async def test_refresh_profile(self, temp_data_dir: Path):
        provider = MockProvider()
        llm_client = LLMClient(provider)
        config = KBBConfig(data_dir=temp_data_dir, llm_api_key="test")
        engine = KBPEngine(config)
        engine._llm = llm_client

        # Initial setup
        await engine.setup_profile_from_text("I'm a software engineer")

        # Refresh
        profile = await engine.refresh_profile()
        assert profile.name == "Test User"


class TestEngineKnowledgeImport:
    @pytest.mark.asyncio
    async def test_import_file(self, temp_data_dir: Path, tmp_path: Path):
        config = KBBConfig(data_dir=temp_data_dir, llm_api_key="test")
        engine = KBPEngine(config)

        # Create a temp file to import
        source = tmp_path / "notes.md"
        source.write_text("# My Notes\n\nImportant knowledge here.")

        entry = await engine.import_knowledge(source, QuestionTopic.GENERAL)
        assert entry.title == "Notes"  # .stem of "notes.md" title-cased
        assert entry.source == "import"

        # Verify it shows up in listings
        entries = engine.get_knowledge_entries()
        assert len(entries) == 1

    @pytest.mark.asyncio
    async def test_import_from_text(self, temp_data_dir: Path):
        config = KBBConfig(data_dir=temp_data_dir, llm_api_key="test")
        engine = KBPEngine(config)

        entry = await engine.import_knowledge_from_text(
            title="Quick Note",
            content="Some knowledge",
            topic=QuestionTopic.SKILL,
        )
        assert entry.title == "Quick Note"
        assert entry.source == "import"


class TestEngineDailyWorkflow:
    @pytest.mark.asyncio
    async def test_generate_daily_question(self, temp_data_dir: Path):
        provider = MockProvider()
        llm_client = LLMClient(provider)
        config = KBBConfig(data_dir=temp_data_dir, llm_api_key="test")
        engine = KBPEngine(config)
        engine._llm = llm_client

        # Need a profile first
        await engine.setup_profile_from_text("I'm a software engineer")

        question = await engine.generate_daily_question()
        assert isinstance(question, Question)
        assert question.text

    @pytest.mark.asyncio
    async def test_generate_question_without_profile_raises(self, temp_data_dir: Path):
        config = KBBConfig(data_dir=temp_data_dir, llm_api_key="test")
        engine = KBPEngine(config)

        with pytest.raises(ValueError, match="No profile found"):
            await engine.generate_daily_question()

    @pytest.mark.asyncio
    async def test_record_response(self, temp_data_dir: Path):
        provider = MockProvider()
        llm_client = LLMClient(provider)
        config = KBBConfig(data_dir=temp_data_dir, llm_api_key="test")
        engine = KBPEngine(config)
        engine._llm = llm_client

        # Setup profile first
        await engine.setup_profile_from_text("I'm a software engineer")

        question = Question(
            text="What testing framework?",
            topic=QuestionTopic.SKILL,
            rationale="Testing experience",
        )
        log = await engine.record_response(question, "I prefer pytest")
        assert log.question == "What testing framework?"
        assert log.response == "I prefer pytest"
        assert log.log_timestamp.date() == date.today()
        assert log.slug  # Slug should be generated

        # Verify knowledge entry was created
        entries = engine.get_knowledge_entries()
        assert len(entries) >= 1

    @pytest.mark.asyncio
    async def test_daily_batch(self, temp_data_dir: Path):
        provider = MockProvider()
        llm_client = LLMClient(provider)
        config = KBBConfig(data_dir=temp_data_dir, llm_api_key="test")
        engine = KBPEngine(config)
        engine._llm = llm_client

        # Setup profile
        await engine.setup_profile_from_text("I'm a software engineer")

        # Run daily batch with a mock response callback
        def get_response(question: Question) -> str:
            return "My response to the question"

        log = await engine.run_daily_batch(get_response)
        assert log.log_timestamp.date() == date.today()
        assert log.response == "My response to the question"


class TestEngineReadOperations:
    def test_get_profile_empty(self, temp_data_dir: Path):
        config = KBBConfig(data_dir=temp_data_dir, llm_api_key="test")
        engine = KBPEngine(config)
        profile = engine.get_profile()
        assert profile.name == ""  # Empty profile

    def test_get_knowledge_entries_empty(self, temp_data_dir: Path):
        config = KBBConfig(data_dir=temp_data_dir, llm_api_key="test")
        engine = KBPEngine(config)
        entries = engine.get_knowledge_entries()
        assert entries == []

    def test_get_all_daily_logs_empty(self, temp_data_dir: Path):
        config = KBBConfig(data_dir=temp_data_dir, llm_api_key="test")
        engine = KBPEngine(config)
        logs = engine.get_all_daily_logs()
        assert logs == []

    def test_data_dir_required(self):
        config = KBBConfig(data_dir=None, llm_api_key="test")
        with pytest.raises(ValueError, match="Data directory is required"):
            KBPEngine(config)


class TestEngineTranscriberProperty:
    def test_transcriber_provider_name_before_init(self, temp_data_dir: Path):
        """Before any transcription, provider_name returns 'unknown'."""
        config = KBBConfig(data_dir=temp_data_dir, llm_api_key="test")
        engine = KBPEngine(config)
        assert engine.transcriber_provider_name == "unknown"

    def test_transcriber_provider_name_after_init(self, temp_data_dir: Path):
        """After _get_transcriber(), provider_name returns the provider name."""
        config = KBBConfig(data_dir=temp_data_dir, llm_api_key="test")
        engine = KBPEngine(config)
        engine._get_transcriber()  # noqa: SLF001
        assert engine.transcriber_provider_name != "unknown"
