"""Voice-to-text transcription — provider protocol, client, and factory.

Supports three providers:
  - faster-whisper (default): CTranslate2-based, 4–6× faster than openai-whisper
  - whisper: PyTorch-based, supports Apple Silicon MPS acceleration
  - openai: OpenAI Whisper API (cloud, no local model needed)
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

SUPPORTED_AUDIO_EXTENSIONS = frozenset({".wav", ".mp3", ".m4a", ".ogg", ".flac", ".webm"})


@runtime_checkable
class TranscriptionProvider(Protocol):
    """Protocol that all transcription backends must implement."""

    @property
    def name(self) -> str: ...

    async def transcribe(self, audio_path: Path, *, language: str = "") -> str: ...


class FasterWhisperProvider:
    """Local transcription via faster-whisper (CTranslate2 backend).

    4–6× faster than openai-whisper with 4× less memory usage.
    Models are lazily loaded on first call and cached in ~/.cache/huggingface/.

    Does NOT support Apple Silicon MPS — use WhisperProvider for that.
    """

    def __init__(
        self,
        *,
        model: str = "base",
        device: str = "auto",
        compute_type: str = "auto",
    ) -> None:
        self._model_name = model
        self._device_name = device
        self._compute_type = compute_type
        self._model: Any = None

    @property
    def name(self) -> str:
        return f"faster-whisper/{self._model_name}"

    async def transcribe(self, audio_path: Path, *, language: str = "") -> str:
        model = self._load_model()
        return await asyncio.to_thread(self._transcribe_sync, model, audio_path, language)

    def _load_model(self) -> Any:
        """Lazily load the faster-whisper model on first use."""
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as e:
                raise ImportError(
                    "faster-whisper is not installed. "
                    "Install it with: uv pip install -e '.[transcription]' "
                    "or: uv pip install faster-whisper"
                ) from e
            device = self._resolve_device()
            compute_type = self._resolve_compute_type(device)
            self._model = WhisperModel(self._model_name, device=device, compute_type=compute_type)
        return self._model

    def _resolve_device(self) -> str:
        """Resolve device: auto-detect CUDA > CPU, or use explicit value."""
        if self._device_name != "auto":
            return self._device_name
        # faster-whisper doesn't support MPS, only CUDA and CPU
        try:
            import torch  # ty: ignore[unresolved-import]  # noqa: F401

            if torch.cuda.is_available():
                return "cuda"
        except ImportError:
            pass
        return "cpu"

    def _resolve_compute_type(self, device: str) -> str:
        """Resolve compute type: int8 for CPU, float16 for CUDA, or explicit value."""
        if self._compute_type != "auto":
            return self._compute_type
        return "float16" if device == "cuda" else "int8"

    @staticmethod
    def _transcribe_sync(model: Any, audio_path: Path, language: str) -> str:
        kwargs: dict[str, Any] = {}
        if language:
            kwargs["language"] = language
        segments, _ = model.transcribe(str(audio_path), **kwargs)
        return " ".join(seg.text for seg in segments).strip()


class WhisperProvider:
    """Local transcription via openai-whisper (PyTorch backend).

    Slower than faster-whisper but supports Apple Silicon MPS acceleration.
    Use this provider when you want GPU acceleration on macOS.
    """

    def __init__(self, *, model: str = "base", device: str = "auto") -> None:
        self._model_name = model
        self._device_name = device
        self._model: Any = None

    @property
    def name(self) -> str:
        return f"whisper/{self._model_name}"

    async def transcribe(self, audio_path: Path, *, language: str = "") -> str:
        model = self._load_model()
        return await asyncio.to_thread(self._transcribe_sync, model, audio_path, language)

    def _load_model(self) -> Any:
        """Lazily load the Whisper model on first use."""
        if self._model is None:
            try:
                import whisper  # ty: ignore[unresolved-import]
            except ImportError as e:
                raise ImportError(
                    "openai-whisper is not installed. "
                    "Install it with: uv pip install -e '.[transcription-whisper]' "
                    "or: uv pip install openai-whisper"
                ) from e
            device = self._resolve_device()
            self._model = whisper.load_model(self._model_name, device=device)
        return self._model

    def _resolve_device(self) -> str:
        """Resolve device: auto-detect CUDA > MPS > CPU, or use explicit value."""
        if self._device_name != "auto":
            return self._device_name
        try:
            import torch  # ty: ignore[unresolved-import]

            if torch.cuda.is_available():
                return "cuda"
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
        except ImportError:
            pass
        return "cpu"

    @staticmethod
    def _transcribe_sync(model: Any, audio_path: Path, language: str) -> str:
        kwargs: dict[str, Any] = {"fp16": False}  # Safe default for CPU
        if language:
            kwargs["language"] = language
        result = model.transcribe(str(audio_path), **kwargs)
        return result["text"].strip()


class OpenAITranscriptionProvider:
    """OpenAI Whisper API transcription provider.

    Uses the openai package (already a required dependency) for cloud-based
    transcription. No local model needed — just an API key.
    """

    def __init__(self, *, api_key: str, model: str = "whisper-1") -> None:
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    @property
    def name(self) -> str:
        return f"openai-transcription/{self._model}"

    async def transcribe(self, audio_path: Path, *, language: str = "") -> str:
        with open(audio_path, "rb") as audio_file:
            kwargs: dict[str, Any] = {"model": self._model, "file": audio_file}
            if language:
                kwargs["language"] = language
            response = await self._client.audio.transcriptions.create(**kwargs)
        return response.text.strip()


class TranscriptionClient:
    """High-level client that owns a provider and exposes transcription operations.

    Handles fallback logic: if the primary provider fails,
    tries the fallback provider (if configured).
    """

    def __init__(
        self,
        provider: TranscriptionProvider,
        fallback: TranscriptionProvider | None = None,
    ) -> None:
        self._provider = provider
        self._fallback = fallback

    @property
    def provider_name(self) -> str:
        return self._provider.name

    async def transcribe(self, audio_path: Path, *, language: str = "") -> str:
        """Transcribe an audio file, with automatic fallback on failure."""
        try:
            return await self._provider.transcribe(audio_path, language=language)
        except Exception as primary_error:
            if self._fallback is None:
                raise
            try:
                return await self._fallback.transcribe(audio_path, language=language)
            except Exception as fallback_error:
                raise primary_error from fallback_error


def _create_provider(
    provider_type: str,
    *,
    api_key: str = "",
    model: str = "base",
    device: str = "auto",
    compute_type: str = "auto",
) -> TranscriptionProvider:
    """Create a single transcription provider by type name.

    Lazy-imports the required package only when needed.
    """
    match provider_type:
        case "faster-whisper":
            return FasterWhisperProvider(model=model, device=device, compute_type=compute_type)
        case "whisper":
            return WhisperProvider(model=model, device=device)
        case "openai":
            if not api_key:
                raise ValueError("OpenAI transcription requires an API key.")
            return OpenAITranscriptionProvider(api_key=api_key, model=model)
        case _:
            raise ValueError(
                f"Unknown transcription provider: {provider_type}. "
                "Supported: faster-whisper, whisper, openai"
            )


def create_transcriber(
    provider_type: str,
    *,
    api_key: str = "",
    model: str = "base",
    device: str = "auto",
    compute_type: str = "auto",
    fallback_type: str = "",
) -> TranscriptionClient:
    """Factory function to instantiate a TranscriptionClient by provider name.

    Args:
        provider_type: "faster-whisper", "whisper", or "openai"
        api_key: OpenAI API key (required for openai provider and fallback)
        model: Model name (whisper model size or openai model)
        device: Device for local providers ("auto", "cpu", "cuda", "mps")
        compute_type: Compute type for faster-whisper ("auto", "int8", "float16", "float32")
        fallback_type: Optional fallback provider ("faster-whisper", "whisper", or "openai")
    """
    provider = _create_provider(
        provider_type, api_key=api_key, model=model, device=device, compute_type=compute_type
    )
    fallback = None
    if fallback_type:
        # OpenAI fallback uses "whisper-1" as model, local providers use the configured model
        fallback_model = model if fallback_type != "openai" else "whisper-1"
        fallback = _create_provider(
            fallback_type,
            api_key=api_key,
            model=fallback_model,
            device=device,
            compute_type=compute_type,
        )
    return TranscriptionClient(provider, fallback=fallback)
