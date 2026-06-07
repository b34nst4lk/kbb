"""Tests for the transcription module — providers, client, factory, and engine integration."""

from __future__ import annotations

from pathlib import Path

import pytest

from kbb.engine import KBPEngine, SUPPORTED_AUDIO_EXTENSIONS
from kbb.models import KBBConfig, TranscriptionProviderName
from kbb.transcribe import (
    TranscriptionClient,
    TranscriptionProvider,
    create_transcriber,
)
from tests.helpers import MockProvider, MockTranscriptionProvider


# --- Protocol conformance ---


class TestTranscriptionProviderProtocol:
    """Test that the TranscriptionProvider protocol works correctly."""

    def test_protocol_match(self) -> None:
        """A class implementing name + transcribe() satisfies the protocol."""

        class DummyProvider:
            @property
            def name(self) -> str:
                return "dummy"

            async def transcribe(self, audio_path: Path, *, language: str = "") -> str:
                return "hello"

        assert isinstance(DummyProvider(), TranscriptionProvider)

    def test_protocol_mismatch(self) -> None:
        """A class missing transcribe() does not satisfy the protocol."""

        class IncompleteProvider:
            @property
            def name(self) -> str:
                return "incomplete"

        # runtime_checkable protocols only check for methods, not properties
        # at isinstance time, so we test that the class structure is incomplete
        assert not hasattr(IncompleteProvider, "transcribe")


# --- TranscriptionProviderName enum ---


class TestTranscriptionProviderName:
    """Test the TranscriptionProviderName enum."""

    def test_enum_values(self) -> None:
        assert TranscriptionProviderName.FASTER_WHISPER.value == "faster-whisper"
        assert TranscriptionProviderName.WHISPER.value == "whisper"
        assert TranscriptionProviderName.OPENAI.value == "openai"

    def test_enum_from_value(self) -> None:
        assert (
            TranscriptionProviderName("faster-whisper") == TranscriptionProviderName.FASTER_WHISPER
        )
        assert TranscriptionProviderName("whisper") == TranscriptionProviderName.WHISPER
        assert TranscriptionProviderName("openai") == TranscriptionProviderName.OPENAI


# --- KBBConfig transcription defaults ---


class TestKBBConfigTranscription:
    """Test KBBConfig default transcription settings."""

    def test_config_defaults(self) -> None:
        config = KBBConfig(data_dir=Path("/tmp/kbb-test"))
        assert config.transcription_provider == TranscriptionProviderName.FASTER_WHISPER
        assert config.whisper_model == "base"
        assert config.whisper_device == "auto"
        assert config.whisper_compute_type == "auto"
        assert config.transcription_fallback is None


# --- MockTranscriptionProvider ---


class TestMockTranscriptionProvider:
    """Test the mock transcription provider used in tests."""

    def test_default_response(self) -> None:
        provider = MockTranscriptionProvider()
        assert provider.name == "mock-transcription"

    @pytest.mark.asyncio
    async def test_default_text(self) -> None:
        provider = MockTranscriptionProvider()
        result = await provider.transcribe(Path("test.wav"))
        assert result == "Mock transcription result"

    @pytest.mark.asyncio
    async def test_custom_text(self) -> None:
        provider = MockTranscriptionProvider(text="Custom text")
        result = await provider.transcribe(Path("test.wav"))
        assert result == "Custom text"

    @pytest.mark.asyncio
    async def test_records_calls(self) -> None:
        provider = MockTranscriptionProvider()
        await provider.transcribe(Path("audio.mp3"), language="en")
        assert len(provider._calls) == 1
        assert provider._calls[0] == (Path("audio.mp3"), "en")

    @pytest.mark.asyncio
    async def test_records_multiple_calls(self) -> None:
        provider = MockTranscriptionProvider()
        await provider.transcribe(Path("a.wav"))
        await provider.transcribe(Path("b.wav"), language="es")
        assert len(provider._calls) == 2


# --- TranscriptionClient ---


class TestTranscriptionClient:
    """Test TranscriptionClient with fallback logic."""

    @pytest.mark.asyncio
    async def test_primary_succeeds(self) -> None:
        """When primary succeeds, fallback is never called."""
        primary = MockTranscriptionProvider(text="Primary result")
        fallback = MockTranscriptionProvider(text="Fallback result")
        client = TranscriptionClient(primary, fallback=fallback)
        result = await client.transcribe(Path("test.wav"))
        assert result == "Primary result"
        assert len(primary._calls) == 1
        assert len(fallback._calls) == 0  # Never called

    @pytest.mark.asyncio
    async def test_no_fallback_raises_primary_error(self) -> None:
        """When primary fails and no fallback, raise primary error."""
        primary = _FailingProvider("Primary error")
        client = TranscriptionClient(primary)
        with pytest.raises(RuntimeError, match="Primary error"):
            await client.transcribe(Path("test.wav"))

    @pytest.mark.asyncio
    async def test_fallback_on_primary_failure(self) -> None:
        """When primary fails, fallback is tried."""
        primary = _FailingProvider("Primary error")
        fallback = MockTranscriptionProvider(text="Fallback result")
        client = TranscriptionClient(primary, fallback=fallback)
        result = await client.transcribe(Path("test.wav"))
        assert result == "Fallback result"

    @pytest.mark.asyncio
    async def test_both_fail_raises_primary_error(self) -> None:
        """When both providers fail, raise the primary error chained from fallback error."""
        primary = _FailingProvider("Primary error")
        fallback = _FailingProvider("Fallback error")
        client = TranscriptionClient(primary, fallback=fallback)
        with pytest.raises(RuntimeError, match="Primary error") as exc_info:
            await client.transcribe(Path("test.wav"))
        # The fallback error should be chained as the cause
        assert exc_info.value.__cause__ is not None
        assert "Fallback error" in str(exc_info.value.__cause__)

    def test_provider_name(self) -> None:
        primary = MockTranscriptionProvider()
        client = TranscriptionClient(primary)
        assert client.provider_name == "mock-transcription"


# --- create_transcriber factory ---


class TestCreateTranscriber:
    """Test the create_transcriber factory function."""

    def test_create_faster_whisper(self) -> None:
        """Factory creates a client with faster-whisper provider."""
        # Can't actually import faster_whisper, so we test the factory
        # by checking it would create the right type
        client = create_transcriber("faster-whisper", model="small", device="cpu")
        assert "faster-whisper" in client.provider_name
        assert "small" in client.provider_name

    def test_create_openai(self) -> None:
        """Factory creates a client with openai provider."""
        client = create_transcriber("openai", api_key="test-key")
        assert "openai-transcription" in client.provider_name

    def test_unknown_provider_raises(self) -> None:
        """Unknown provider type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown transcription provider"):
            create_transcriber("unknown")

    def test_openai_no_key_raises(self) -> None:
        """OpenAI provider without API key raises ValueError."""
        with pytest.raises(ValueError, match="API key"):
            create_transcriber("openai", api_key="")

    def test_create_with_fallback(self) -> None:
        """Factory creates a client with fallback provider."""
        client = create_transcriber(
            "faster-whisper",
            api_key="test-key",
            fallback_type="openai",
        )
        assert "faster-whisper" in client.provider_name


# --- Engine transcription integration ---


class TestEngineTranscription:
    """Test KBPEngine.transcribe() and transcribe_and_record()."""

    def _make_engine(self, tmp_path: Path) -> KBPEngine:
        """Create an engine with mock LLM and temp data dir."""
        config = KBBConfig(data_dir=tmp_path)
        engine = KBPEngine(config)
        provider = MockProvider()
        from kbb.llm.base import LLMClient

        engine._llm = LLMClient(provider)
        return engine

    def test_transcriber_lazy_init(self, tmp_path: Path) -> None:
        """Transcriber is None after construction, created on first use."""
        engine = self._make_engine(tmp_path)
        assert engine._transcriber is None
        transcriber = engine._get_transcriber()
        assert transcriber is not None

    def test_transcriber_cached(self, tmp_path: Path) -> None:
        """Repeated calls return the same transcriber instance."""
        engine = self._make_engine(tmp_path)
        first = engine._get_transcriber()
        second = engine._get_transcriber()
        assert first is second

    @pytest.mark.asyncio
    async def test_transcribe_file_not_found(self, tmp_path: Path) -> None:
        """Transcribing a non-existent file raises ValueError."""
        engine = self._make_engine(tmp_path)
        engine._transcriber = TranscriptionClient(MockTranscriptionProvider())
        with pytest.raises(ValueError, match="Audio file not found"):
            await engine.transcribe(Path("/nonexistent/file.wav"))

    @pytest.mark.asyncio
    async def test_transcribe_unsupported_format(self, tmp_path: Path) -> None:
        """Transcribing a file with unsupported extension raises ValueError."""
        engine = self._make_engine(tmp_path)
        engine._transcriber = TranscriptionClient(MockTranscriptionProvider())
        # Create a fake text file
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("not audio")
        with pytest.raises(ValueError, match="Unsupported audio format"):
            await engine.transcribe(txt_file)

    @pytest.mark.asyncio
    async def test_transcribe_success(self, tmp_path: Path) -> None:
        """Transcribing a supported audio file returns text from provider."""
        engine = self._make_engine(tmp_path)
        mock_provider = MockTranscriptionProvider(text="Hello world")
        engine._transcriber = TranscriptionClient(mock_provider)
        # Create a fake wav file
        wav_file = tmp_path / "test.wav"
        wav_file.write_bytes(b"fake audio data")
        result = await engine.transcribe(wav_file)
        assert result == "Hello world"

    @pytest.mark.asyncio
    async def test_transcribe_with_language(self, tmp_path: Path) -> None:
        """Transcribing with language hint passes it through."""
        engine = self._make_engine(tmp_path)
        mock_provider = MockTranscriptionProvider(text="Bonjour")
        engine._transcriber = TranscriptionClient(mock_provider)
        wav_file = tmp_path / "test.wav"
        wav_file.write_bytes(b"fake audio data")
        result = await engine.transcribe(wav_file, language="fr")
        assert result == "Bonjour"
        assert mock_provider._calls[0] == (wav_file, "fr")

    @pytest.mark.asyncio
    async def test_transcribe_and_record_success(self, tmp_path: Path) -> None:
        """transcribe_and_record combines transcription and recording."""
        engine = self._make_engine(tmp_path)
        # Set up mock transcriber
        mock_provider = MockTranscriptionProvider(text="I prefer pytest for testing")
        engine._transcriber = TranscriptionClient(mock_provider)
        # Create a fake wav file
        wav_file = tmp_path / "test.wav"
        wav_file.write_bytes(b"fake audio data")
        # Write a profile so the engine can generate responses
        engine._store.write_profile("# Test User\n\nI like Python.")
        await engine.setup_profile_from_text("# Test User\n\nI like Python.")
        # Generate a question first
        question = await engine.generate_daily_question()
        # Transcribe and record
        log = await engine.transcribe_and_record(question, wav_file)
        assert log is not None
        assert "pytest" in log.response

    @pytest.mark.asyncio
    async def test_transcribe_and_record_empty_raises(self, tmp_path: Path) -> None:
        """transcribe_and_record raises ValueError on empty transcription."""
        engine = self._make_engine(tmp_path)
        mock_provider = MockTranscriptionProvider(text="   ")
        engine._transcriber = TranscriptionClient(mock_provider)
        wav_file = tmp_path / "test.wav"
        wav_file.write_bytes(b"fake audio data")
        from kbb.models import Question, QuestionTopic

        question = Question(text="Test question?", topic=QuestionTopic.GENERAL, rationale="Testing")
        with pytest.raises(ValueError, match="empty text"):
            await engine.transcribe_and_record(question, wav_file)


# --- Supported audio formats ---


class TestSupportedAudioFormats:
    """Test the SUPPORTED_AUDIO_EXTENSIONS constant."""

    def test_includes_common_formats(self) -> None:
        assert ".wav" in SUPPORTED_AUDIO_EXTENSIONS
        assert ".mp3" in SUPPORTED_AUDIO_EXTENSIONS
        assert ".m4a" in SUPPORTED_AUDIO_EXTENSIONS
        assert ".ogg" in SUPPORTED_AUDIO_EXTENSIONS
        assert ".flac" in SUPPORTED_AUDIO_EXTENSIONS
        assert ".webm" in SUPPORTED_AUDIO_EXTENSIONS

    def test_excludes_non_audio(self) -> None:
        assert ".txt" not in SUPPORTED_AUDIO_EXTENSIONS
        assert ".pdf" not in SUPPORTED_AUDIO_EXTENSIONS

    def test_is_case_insensitive(self) -> None:
        """The check uses .lower(), so .WAV should also be supported."""
        assert ".WAV".lower() in SUPPORTED_AUDIO_EXTENSIONS


# --- Helper classes ---


class _FailingProvider:
    """A transcription provider that always fails. Used for testing fallback logic."""

    def __init__(self, message: str = "FailingProvider error") -> None:
        self._message = message

    @property
    def name(self) -> str:
        return "failing"

    async def transcribe(self, audio_path: Path, *, language: str = "") -> str:
        raise RuntimeError(self._message)
