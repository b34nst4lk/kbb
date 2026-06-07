# Voice-to-Text Transcription ✅ IMPLEMENTED

## Context and Use Case

KBB builds a personal knowledge base through daily question-answer interactions. Currently, users must type responses via CLI editor or web textarea. Speaking a response is far faster and more natural, especially for reflective answers. The upcoming Telegram and Discord adapters also need voice message support.

**Core flow**: audio → transcription → existing `record_response(question, text)` pipeline unchanged.

**CLAUDE.md constraint**: Module goes in `src/kbb/transcribe.py`, following the Protocol-based provider pattern from `LLMProvider`.

## Requirements

### Functional
1. Accept audio input (file path) and return transcribed text
2. **faster-whisper** (CTranslate2) as default local provider — 4–6× faster than openai-whisper, 4× less memory
3. **openai-whisper** (PyTorch) as alternative local provider — MPS/Apple Silicon GPU support
4. **OpenAI Whisper API** as cloud fallback provider
5. Automatic fallback: primary fails → fallback (if configured)
6. Support common audio formats: WAV, MP3, M4A, OGG, FLAC, WEBM
7. Configurable model size (tiny/base/small/medium/large-v3) and device (auto/cpu/cuda)
8. CLI commands: `kbb transcribe <file>` and `kbb daily-respond-voice <file>`
9. Web API: `POST /api/transcribe` and HTMX partial for audio upload
10. Browser-based voice recording via `MediaRecorder` API on the daily question page

### Non-Functional
1. Follow `LLMProvider` Protocol pattern: `TranscriptionProvider` protocol, `TranscriptionClient` wrapper, `create_transcriber()` factory
2. Core library stays integration-agnostic
3. `faster-whisper` and `openai-whisper` are **optional** dependencies — graceful failure if not installed
4. `openai` package already required, so OpenAI API transcription adds no new required deps
5. Python 3.13+, type hints, ruff/ty clean
6. Local transcription is sync/CPU-bound → wrap in `asyncio.to_thread()`
7. All tests use `MockTranscriptionProvider`

## Proposals

### Chosen: Single-file `transcribe.py` with Protocol pattern, three providers

One module `src/kbb/transcribe.py` containing `TranscriptionProvider` protocol, `FasterWhisperProvider`, `WhisperProvider`, `OpenAITranscriptionProvider`, `TranscriptionClient`, and `create_transcriber()` factory.

**Why not a directory like `llm/`?** The LLM module has 5+ files because it handles prompts, schemas, structured output, and 3 providers. Transcription has one method (`transcribe`) and three simple providers. A single file is simpler, more discoverable, and matches the CLAUDE.md-specified path.

**Why engine-owned `transcribe()` method?** Every adapter would independently implement "transcribe then record" with fallback logic, error handling, and config resolution. Centralizing in the engine matches how `run_daily_batch()` works.

**Why faster-whisper as default?** 4–6× faster and 4× less memory than openai-whisper. Only downside is no MPS, but faster-whisper on CPU still beats openai-whisper on CPU. Apple Silicon users wanting GPU can explicitly choose the `whisper` provider.

### Rejected: Transcription outside the engine

Duplicates fallback logic across adapters and complicates config resolution.

## Technical Solutions

### 1. TranscriptionProvider Protocol (`src/kbb/transcribe.py`)

```python
@runtime_checkable
class TranscriptionProvider(Protocol):
    @property
    def name(self) -> str: ...
    async def transcribe(self, audio_path: Path, *, language: str = "") -> str: ...
```

- `audio_path: Path` — all providers accept file paths
- `language: str = ""` — optional language hint, empty = auto-detect
- Returns plain `str` — no timestamps/segments for v1

### 2. FasterWhisperProvider (default local)

- Lazy model loading on first call (models cached in `~/.cache/huggingface/hub/`)
- `asyncio.to_thread()` wraps sync CTranslate2 calls
- `_resolve_device()`: auto-detects CUDA > CPU (no MPS support in CTranslate2)
- `_resolve_compute_type()`: `int8` for CPU (fast + small), `float16` for CUDA
- Segment joining: `faster_whisper` returns segment iterator, we join with spaces
- `ImportError` with install instructions if `faster-whisper` not installed
- `name` returns `"faster-whisper/{model}"`

### 3. WhisperProvider (alternative local — PyTorch/MPS)

- Lazy model loading, `asyncio.to_thread()`, `_resolve_device()`: CUDA > MPS > CPU
- `fp16=False` safe default for CPU
- Returns `result["text"].strip()` (openai-whisper returns dict, not segments)
- `ImportError` with install instructions if `openai-whisper` not installed
- `name` returns `"whisper/{model}"`

### 4. OpenAITranscriptionProvider (cloud fallback)

- Uses existing `openai` dependency, `AsyncOpenAI` client
- `client.audio.transcriptions.create()`, `model="whisper-1"`
- `name` returns `"openai-transcription/{model}"`

### 5. TranscriptionClient

- Wraps primary provider + optional fallback
- `transcribe()`: try primary, fall back on failure, raise primary error if both fail
- Mirrors `LLMClient` pattern

### 6. create_transcriber() Factory

- `create_transcriber(provider_type, *, api_key, model, device, compute_type, fallback_type)` → `TranscriptionClient`
- Provider type mapping: `"faster-whisper"` → FasterWhisperProvider, `"whisper"` → WhisperProvider, `"openai"` → OpenAITranscriptionProvider
- Lazy imports per `create_provider()` pattern

### 7. Config (`src/kbb/models.py`)

```python
class TranscriptionProviderName(str, Enum):
    FASTER_WHISPER = "faster-whisper"
    WHISPER = "whisper"
    OPENAI = "openai"

# Added to KBBConfig:
transcription_provider: TranscriptionProviderName = TranscriptionProviderName.FASTER_WHISPER
transcription_fallback: TranscriptionProviderName | None = None
whisper_model: str = "base"
whisper_device: str = "auto"
whisper_compute_type: str = "auto"  # faster-whisper specific
```

### 8. Engine (`src/kbb/engine.py`)

- `_transcriber: TranscriptionClient | None` — lazily initialized
- `transcribe(audio_path, *, language="") -> str` — validates file/format, delegates
- `transcribe_and_record(question, audio_path, *, language="") -> DailyLog` — convenience method
- `SUPPORTED_AUDIO_EXTENSIONS = frozenset({".wav", ".mp3", ".m4a", ".ogg", ".flac", ".webm"})`

### 9. CLI (`src/kbb_cli/app.py`)

- `kbb transcribe <audio_file> [--language]`
- `kbb daily-respond-voice <audio_file> [--language]`

### 10. Web

- `POST /api/transcribe` — multipart upload → JSON `{text, provider}`
- `POST /partials/transcribe` — HTMX partial, auto-fills textarea
- `templates/partials/transcription_result.html`
- Browser `MediaRecorder` in `kbb.js`: mic capture → WebM blob → upload → fill textarea

### 11. WebConfig (`src/kbb_web/config.py`)

```yaml
transcription:
  provider: faster-whisper
  fallback: openai
  whisper_model: base
  whisper_device: auto
  whisper_compute_type: auto
```

### 12. Dependencies (`pyproject.toml`)

```toml
transcription = ["faster-whisper>=1.0,<2.0"]
transcription-whisper = ["openai-whisper>=20231117,<2025.0"]
all = ["knowledge-base-builder[cli,web,desktop,transcription]"]
```

## Task List and Test Cases

### Task 1: TranscriptionProvider Protocol and Data Models

- [x] **`TranscriptionProvider` protocol in `src/kbb/transcribe.py`**
  Expected: `@runtime_checkable` Protocol with `name: str` property and `async def transcribe(self, audio_path: Path, *, language: str = "") -> str`
  - [ ] `test_protocol_match`: Class with `name` + `transcribe()` → `isinstance` is `True`
  - [ ] `test_protocol_mismatch`: Class missing `transcribe()` → `isinstance` is `False`

- [x] **`TranscriptionProviderName` enum in `src/kbb/models.py`**
  Expected: `FASTER_WHISPER = "faster-whisper"`, `WHISPER = "whisper"`, `OPENAI = "openai"`
  - [ ] `test_enum_values`: Assert all three values match

- [x] **Transcription config fields in `KBBConfig`**
  Expected: `transcription_provider`, `transcription_fallback`, `whisper_model`, `whisper_device`, `whisper_compute_type` with defaults
  - [ ] `test_config_defaults`: Assert default config has `transcription_provider == FASTER_WHISPER`, `whisper_model == "base"`, `whisper_device == "auto"`, `whisper_compute_type == "auto"`, `transcription_fallback is None`

### Task 2: FasterWhisperProvider (default)

- [x] **`FasterWhisperProvider.__init__(*, model="base", device="auto", compute_type="auto")`**
  - [ ] `test_init_name`: Assert `FasterWhisperProvider(model="small").name == "faster-whisper/small"`
  - [ ] `test_init_default`: Assert `FasterWhisperProvider().name == "faster-whisper/base"`

- [x] **`FasterWhisperProvider.transcribe(audio_path, *, language="") -> str`**
  - [ ] `test_transcribe`: Mock faster_whisper model returning segments, assert joined text
  - [ ] `test_transcribe_with_language`: Assert `language` kwarg passed through
  - [ ] `test_transcribe_strips_whitespace`: Assert leading/trailing spaces stripped
  - [ ] `test_transcribe_import_error`: Assert `ImportError` with install message if `faster-whisper` missing

- [x] **`FasterWhisperProvider._resolve_device()` and `_resolve_compute_type()`**
  - [ ] `test_resolve_device_auto_cuda`: Returns `"cuda"` when CUDA available
  - [ ] `test_resolve_device_auto_cpu`: Returns `"cpu"` when no CUDA
  - [ ] `test_resolve_device_explicit`: Returns explicit value
  - [ ] `test_resolve_compute_type_auto_cuda`: Returns `"float16"`
  - [ ] `test_resolve_compute_type_auto_cpu`: Returns `"int8"`
  - [ ] `test_resolve_compute_type_explicit`: Returns explicit value

### Task 3: WhisperProvider (alternative — PyTorch/MPS)

- [x] **`WhisperProvider.__init__(*, model="base", device="auto")`**
  - [ ] `test_init_name`: Assert `WhisperProvider(model="small").name == "whisper/small"`
  - [ ] `test_init_default`: Assert `WhisperProvider().name == "whisper/base"`

- [x] **`WhisperProvider.transcribe(audio_path, *, language="") -> str`**
  - [ ] `test_transcribe`: Mock returning `{"text": "Hello world"}`
  - [ ] `test_transcribe_with_language`: Assert language passed through
  - [ ] `test_transcribe_import_error`: Assert `ImportError` if `openai-whisper` missing

- [x] **`WhisperProvider._resolve_device()`**
  - [ ] `test_resolve_device_auto_cuda`: Returns `"cuda"`
  - [ ] `test_resolve_device_auto_mps`: Returns `"mps"`
  - [ ] `test_resolve_device_explicit_cpu`: Returns `"cpu"`

### Task 4: OpenAITranscriptionProvider

- [x] **`OpenAITranscriptionProvider.__init__(*, api_key, model="whisper-1")`**
  - [ ] `test_init_name`: Assert name format
  - [ ] `test_init_custom_model`: Assert name with custom model

- [x] **`OpenAITranscriptionProvider.transcribe(audio_path, *, language="") -> str`**
  - [ ] `test_transcribe`: Mock client, assert returns transcribed text
  - [ ] `test_transcribe_with_language`: Assert language passed to API
  - [ ] `test_transcribe_file_not_found`: Non-existent path → raises error

### Task 5: TranscriptionClient and Factory

- [x] **`TranscriptionClient(provider, fallback=None)`**
  - [ ] `test_primary_succeeds`: No fallback call
  - [ ] `test_fallback_on_primary_failure`: Primary fails → fallback succeeds
  - [ ] `test_both_fail_raises_primary`: Both fail → primary error
  - [ ] `test_no_fallback_raises_primary`: No fallback → primary error

- [x] **`create_transcriber(provider_type, *, ...)`**
  - [ ] `test_create_faster_whisper`: Returns client with `"faster-whisper"` provider
  - [ ] `test_create_whisper`: Returns client with `"whisper/"` provider
  - [ ] `test_create_openai`: Returns client with `"openai-transcription"` provider
  - [ ] `test_create_with_fallback`: Both primary and fallback configured
  - [ ] `test_unknown_provider_raises`: `ValueError` for unknown type
  - [ ] `test_openai_no_key_raises`: `ValueError` for OpenAI without API key

### Task 6: Engine Integration

- [x] **`KBPEngine._get_transcriber()`**
  - [ ] `test_lazy_init`: `_transcriber` is `None` after construction, created on first call
  - [ ] `test_cached`: Repeated calls return same instance

- [x] **`KBPEngine.transcribe(audio_path, *, language="") -> str`**
  - [ ] `test_file_not_found`: `ValueError("Audio file not found")`
  - [ ] `test_unsupported_format`: `ValueError("Unsupported audio format")`
  - [ ] `test_success`: Returns transcribed text via MockTranscriptionProvider

- [x] **`KBPEngine.transcribe_and_record(question, audio_path, *, language="") -> DailyLog`**
  - [ ] `test_success`: Mock transcriber + mock LLM → `DailyLog` created
  - [ ] `test_empty_transcription_raises`: Empty transcription → `ValueError("empty text")`

### Task 7: CLI Commands

- [x] **`kbb transcribe <audio_file>` command**
  - [ ] `test_transcribe_success`: Prints transcribed text
  - [ ] `test_transcribe_failure`: Prints error message

- [x] **`kbb daily-respond-voice <audio_file>` command**
  - [ ] `test_respond_voice_success`: Full workflow succeeds
  - [ ] `test_respond_voice_empty`: Empty transcription → error message

### Task 8: Web API, HTMX, and Browser Recording

- [x] **`POST /api/transcribe`**
  - [ ] `test_api_transcribe_success`: Returns 200 + JSON
  - [ ] `test_api_transcribe_unsupported_format`: Returns 400

- [x] **`POST /partials/transcribe`**
  - [ ] `test_partial_transcribe_success`: Returns HTML with text
  - [ ] `test_partial_transcribe_failure`: Returns error alert HTML

- [x] **Browser voice recording in `kbb.js`**
  - [ ] `test_record_button_exists`: Daily question page includes record button
  - [ ] `test_js_recorder_module`: `VoiceRecorder` class with `start()`, `stop()`, `isRecording`
  - [ ] `test_record_button_html`: Correct HTMX attributes

### Task 9: WebConfig Updates

- [x] **Transcription fields in `WebConfig`**
  - [ ] `test_defaults`: Default `WebConfig` has `transcription_provider == FASTER_WHISPER`
  - [ ] `test_from_yaml`: Parse YAML with `transcription:` section
  - [ ] `test_to_dict`: Serialize includes transcription section

### Task 10: MockTranscriptionProvider

- [x] **`MockTranscriptionProvider` in `tests/helpers.py`**
  - [ ] `test_default_response`: Returns non-empty string
  - [ ] `test_custom_response`: Returns configured text
  - [ ] `test_records_calls`: `calls` list has `(audio_path, language)` tuples

### Task 11: Dependencies

- [x] **`pyproject.toml` optional dependency groups**
  - [ ] `test_pyproject_has_transcription_extras`: Assert `transcription` and `transcription-whisper` sections exist

## Deviations from Plan

What changed between the plan and the actual implementation:

### 1. `ty: ignore` comments instead of `type: ignore`
The plan didn't specify which inline suppression syntax to use. The project uses `ty` (Astral's type checker) rather than mypy, so `ty: ignore[unresolved-import]` is the correct syntax. Three were needed for optional imports (`faster_whisper`, `whisper`, `torch`) — though `ty` later reported that the `faster_whisper` one was unnecessary inside a `try/except ImportError`, so only two remain (`whisper` and `torch`).

### 2. Web UI: dual input (Record + Upload)
The plan described only a browser `MediaRecorder` recording button. The implementation added **two** audio input methods on the response form:
- **🎤 Record** — uses `VoiceRecorder` class with `navigator.mediaDevices.getUserMedia()` + `MediaRecorder` (WebM/Opus), auto-uploads on stop
- **📁 Upload** — file picker filtered to supported audio formats (`.wav,.mp3,.m4a,.ogg,.flac,.webm`), auto-uploads on selection

Both paths POST to `/partials/transcribe` and fill the response textarea with the transcription result. The upload button was added because microphone access isn't always available (desktop browsers without mic, permissions denied, etc.), and users may have pre-recorded audio files.

### 3. `response_form.html` template updated
The plan mentioned adding a record button to the daily question page. In practice, the button was added to `partials/response_form.html` (the existing response form partial), which is included inside `partials/question_card.html`. This means both the daily question page and any future page that shows a response form will automatically get voice transcription support.

### 4. `id="response"` → `id="response-textarea"`
The textarea `id` was changed from `response` to `response-textarea` so the `VoiceRecorder` JavaScript and the upload script can reliably target it. The `name="response"` attribute (used for form submission) was kept unchanged so the existing `record_response` partial continues to work.

### 5. Transcription result auto-fills textarea — no inline `<script>`
The plan described using an inline `<script>` tag in `transcription_result.html` to auto-fill the textarea. This doesn't work because setting `innerHTML` or `outerHTML` via JavaScript does **not** execute `<script>` tags — the browser security model strips scripts when inserting HTML this way.

**Bug fix**: The `transcription_result.html` template now renders only the text in a `<div class="transcription-text">` with no inline script. Instead, the `fillTextareaWithTranscription()` function in `kbb.js` reads `.textContent` from this div after it's inserted into the DOM and sets `textarea.value` directly. This function is called by both `VoiceRecorder.upload()` (mic recording) and the file upload handler after `transcribeAudio()` completes.

This also means the user sees the transcription text displayed above the textarea *and* it's filled into the textarea, so they can edit before submitting.

### 6. `openai-whisper` version constraint relaxed
The plan specified `openai-whisper>=20231117,<2025.0`, but the package uses date-based versioning (latest is `20250625`). The constraint was relaxed to `openai-whisper>=20231117` (no upper bound) since the older upper bound would exclude the current version.

### 7. All tasks implemented in fewer files than planned
The plan listed separate tasks for FasterWhisperProvider, WhisperProvider, OpenAITranscriptionProvider, TranscriptionClient, and create_transcriber. All were implemented together in a single `src/kbb/transcribe.py` file (as the plan specified), so the task numbering in the plan file doesn't exactly match the git history — tasks 1–4 were done as one commit.