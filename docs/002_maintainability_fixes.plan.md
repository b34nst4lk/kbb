# Maintainability Fixes

## Context and Use Case

An LLM-focused code review identified 8 critical, 14 moderate, and 10 minor maintainability issues across the KBB codebase. These range from unhandled exceptions on user input (C6, C7) to data-loss round-trips (C3) to naming inconsistencies (C1) to duplicated logic (M8). The fixes improve the codebase's ability to be correctly understood and modified by both humans and LLMs.

## Requirements

1. Fix all critical issues — unhandled exceptions, data-loss bugs, naming mismatches
2. Fix all moderate issues that don't require architectural changes — exception chaining, missing docs, duplicated code, dead code, silent skips
3. Fix minor issues that are quick wins — import cleanup, assertion dedup, date shadowing, unused params
4. Defer architectural changes (renaming `KBPEngine` → `KBBEngine`, moving `to_markdown()` out of models, adding `json_schema` to `stream()`) to a future task
5. All existing tests must continue to pass; new tests should cover the behavioral changes
6. Follow CLAUDE.md coding standards: ruff, ty, type hints

## Proposals

### Chosen: Incremental fixes grouped by file, deferring large renames

Fix issues in-place within each file, grouping related changes. Defer the `KBPEngine` rename (C1) because it touches every adapter and every test — that's a separate task. Defer adding `json_schema` to `stream()` (C4) because it changes the `LLMProvider` protocol and all three providers. Defer moving `to_markdown()` out of `DailyLog` (M4) because it changes the public API of a data model.

### Deferred items (future task)

- **C1**: Rename `KBPEngine` → `KBBEngine` (touches every adapter, every test)
- **C4**: Add `json_schema` parameter to `LLMProvider.stream()` (protocol + 3 providers)
- **M4**: Move `DailyLog.to_markdown()` out of the models module (public API change)
- **M3**: Adopt or remove `models_web.py` (design decision about Pydantic form schemas)

## Technical Solutions

### Phase 1: Input validation (C6, C7) — `api.py`, `partials.py`, `pages.py`

**Problem**: `QuestionTopic()` and `date.fromisoformat()` called on raw user input crash with unhandled `ValueError`.

**Fix**: Add `try/except ValueError` with fallbacks.

In `api.py` and `partials.py`, wrap `QuestionTopic()` calls:
```python
try:
    topic_enum = QuestionTopic(topic_str)
except ValueError:
    topic_enum = QuestionTopic.GENERAL
```

In `api.py` and `pages.py`, wrap `date.fromisoformat()`:
```python
try:
    d = date.fromisoformat(date_str)
except ValueError:
    raise HTTPException(status_code=400, detail=f"Invalid date: {date_str}")
```
(pages.py returns an error page instead of HTTPException)

### Phase 2: Topic mapping consolidation (C3, M9) — `models.py`, `markdown_store.py`

**Problem**: `TOPIC_DIRS` (forward map) and `topic_reverse` (reverse map) are maintained separately. Three topics (`OPINION`, `DECISION`, `PROCESS`) map to `"general"` and round-trip to `GENERAL` — data is lost. Also `SKILL` maps to `"skills"` (with trailing 's') but `SKILL` enum value is `"skill"` (no 's').

**Fix**: Add a `directory` property to `QuestionTopic` and a `from_directory()` class method:

```python
class QuestionTopic(str, Enum):
    EDUCATION = "education"
    WORK_EXPERIENCE = "work_experience"
    LIFE_EXPERIENCE = "life_experience"
    SKILL = "skill"
    OPINION = "opinion"
    DECISION = "decision"
    PROCESS = "process"
    GENERAL = "general"

    @property
    def directory(self) -> str:
        dirs = {
            "education": "education",
            "work_experience": "work",
            "life_experience": "life",
            "skill": "skills",
            "opinion": "general",
            "decision": "general",
            "process": "general",
            "general": "general",
        }
        return dirs[self.value]

    @classmethod
    def from_directory(cls, dir_name: str) -> "QuestionTopic":
        reverse = {
            "education": cls.EDUCATION,
            "work": cls.WORK_EXPERIENCE,
            "life": cls.LIFE_EXPERIENCE,
            "skills": cls.SKILL,
            "general": cls.GENERAL,
        }
        return reverse.get(dir_name, cls.GENERAL)
```

Then remove `TOPIC_DIRS` and `topic_reverse` from `MarkdownStore`, using `topic.directory` and `QuestionTopic.from_directory()` instead.

Add a docstring noting the intentional collapse: topics `OPINION`, `DECISION`, and `PROCESS` map to the `"general"` directory and cannot round-trip back to their original value.

### Phase 3: Slug consolidation (M1 partial) — `models.py`, `markdown_store.py`

**Problem**: Slug logic is in three places — `KnowledgeEntry.slug` property, `MarkdownStore._slugify()`, and `LLMClient.generate_slug()`.

**Fix**: Keep all three (they serve different purposes: computed property, filename generation, LLM-generated). But:
1. Add a module-level `slugify()` utility function in `models.py` that both `KnowledgeEntry.slug` and `MarkdownStore._slugify` delegate to.
2. Add a docstring to `KnowledgeEntry.slug` noting it's a computed property, not stored.
3. Add a docstring to `MarkdownStore._slugify` noting it's for filenames and may pre-truncate.
4. Add a comment in `engine.py:162` noting that `title=slug` is intentional — the LLM-generated slug becomes the canonical title for daily-log entries.

```python
# In models.py, add at module level:
def slugify(text: str, max_length: int = 80) -> str:
    """Convert text to a URL-safe slug. Truncates to max_length."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_length] if len(slug) > max_length else slug
```

Then update `KnowledgeEntry.slug` to use `slugify(self.title)` and `MarkdownStore._slugify` to use `slugify(text)` (removing the duplicate regex).

### Phase 4: Exception chaining in TranscriptionClient (M7) — `transcribe.py`

**Problem**: `TranscriptionClient.transcribe()` does `raise primary_error from primary_error` (self-reference) and discards the fallback error.

**Fix**: Capture the fallback error and chain it:
```python
except Exception as fallback_error:
    raise primary_error from fallback_error
```

### Phase 5: Move SUPPORTED_AUDIO_EXTENSIONS to transcribe.py (M12) — `transcribe.py`, `engine.py`, `api.py`, `partials.py`

**Problem**: `SUPPORTED_AUDIO_EXTENSIONS` is defined in `engine.py` but semantically belongs in `transcribe.py`. Web routes import from `kbb.engine` just for this constant.

**Fix**: Move the constant to `transcribe.py` and re-export from `engine.py` for backward compatibility:
```python
# In transcribe.py:
SUPPORTED_AUDIO_EXTENSIONS = frozenset({".wav", ".mp3", ".m4a", ".ogg", ".flac", ".webm"})

# In engine.py:
from kbb.transcribe import SUPPORTED_AUDIO_EXTENSIONS  # re-export for convenience
```

### Phase 6: Add public accessor for transcriber state (C2 partial) — `engine.py`

**Problem**: `api.py:263` accesses `engine._transcriber` directly, bypassing lazy init.

**Fix**: Add a public property to `KBPEngine`:
```python
@property
def transcriber_provider_name(self) -> str:
    """Return the name of the active transcription provider, or 'unknown' if not initialized."""
    if self._transcriber is None:
        return "unknown"
    return self._transcriber.provider_name
```

Then update `api.py:263` to use `engine.transcriber_provider_name`.

Also add a public `data_dir` property:
```python
@property
def data_dir(self) -> Path:
    """Return the configured data directory."""
    assert self._config.data_dir is not None, "data_dir not set"
    return self._config.data_dir
```

Then replace `engine._config.data_dir` references in `app.py` with `engine.data_dir`.

### Phase 7: Fix CLI API key fallback (C8) — `app.py`

**Problem**: `_get_engine()` uses a provider-agnostic fallback chain `KBB_API_KEY` → `ANTHROPIC_API_KEY` → `OPENAI_API_KEY`, which silently passes wrong-provider keys.

**Fix**: Make the CLI fallback provider-aware, matching `WebConfig._resolve_api_key()`:
```python
def _resolve_api_key(provider: str, explicit_key: str = "") -> str:
    if explicit_key:
        return explicit_key
    env_keys = {
        "anthropic": ["ANTHROPIC_API_KEY"],
        "openai": ["OPENAI_API_KEY"],
        "ollama": [],
    }
    for key in env_keys.get(provider, []):
        val = os.getenv(key, "")
        if val:
            return val
    return os.getenv("KBB_API_KEY", "")
```

Use this in `_get_engine()` instead of the current cascading fallback.

### Phase 8: Logging for silent skips (M5) — `markdown_store.py`

**Problem**: `list_knowledge_entries` and other methods silently skip malformed files.

**Fix**: Add `logging.warning()` calls before `continue`:
```python
import logging

logger = logging.getLogger(__name__)

# In list_knowledge_entries:
except Exception as e:
    logger.warning("Skipping malformed knowledge file %s: %s", md_file, e)
    continue
```

Same pattern for `_parse_daily_log` returning `None`.

### Phase 9: Document format contracts (M6) — `models.py`, `markdown_store.py`

**Problem**: `DailyLog.to_markdown()` and `_parse_daily_log()` have an implicit format contract with no documentation.

**Fix**: Add docstrings:
- `DailyLog.to_markdown()`: Document the exact markdown format produced (sections, headers, bold syntax).
- `_parse_daily_log()`: Document the expected format and its coupling to `to_markdown()`.
- `format_frontmatter()`: Document which falsy values are kept vs omitted.

### Phase 10: Document LLM provider contracts (M10, M11, C4 partial) — `llm/base.py`, `prompts.py`

**Problem**: Several implicit contracts around the LLM provider are undocumented.

**Fix**:
1. Add docstring to `LLMProvider.stream()` noting: "Does not accept `json_schema`. Callers needing structured output must use `complete()`."
2. Add comment to `create_provider()` noting that `api_key` is not forwarded for the `"ollama"` provider.
3. Add comments in `prompts.py` noting that inline schema descriptions must be kept in sync with `schemas.py`.

### Phase 11: Extract question-generation helper (M8) — `app.py`

**Problem**: Near-identical question-generation blocks appear three times.

**Fix**: Extract a helper:
```python
def _get_question(engine: KBPEngine) -> Question:
    """Get a pending question or generate a new one."""
    pending = engine.get_pending_question()
    if pending:
        console.print("[dim]Using previously generated question.[/dim]")
        return pending
    with console.status("[bold green]Generating today's question...[/bold green]"):
        return asyncio.run(engine.generate_daily_question())
```

Replace the three blocks with `question = _get_question(engine)`, with `try/except` at the call sites.

### Phase 12: Fix date import shadowing (minor) — `partials.py`

**Problem**: `date` parameter shadows `datetime.date` import, forcing `from datetime import date as date_type`.

**Fix**: Rename the parameter from `date: str` to `date_str: str` (matching `api.py` convention), remove the local import.

### Phase 13: Remove dead code (M3 partial) — `models_web.py`

**Problem**: `models_web.py` is entirely unused.

**Fix**: Delete the file. If Pydantic form schemas are needed later, they can be recreated from the inline schemas in `api.py`.

### Phase 14: Move local import to module level (minor) — `api.py`

**Problem**: `Question` is imported inside a function body.

**Fix**: Move `from kbb.models import Question` to the module-level imports at the top of `api.py`.

### Phase 15: Remove unused `request: Request` params (minor) — `pages.py`, `partials.py`

**Problem**: Every handler in `partials.py` and most in `pages.py` accept `request: Request` but never use it.

**Fix**: Remove unused `request: Request` parameters. FastAPI/Starlette route handlers only need `Request` if they use it.

### Phase 16: Fix `save_settings` missing fields (M14) — `partials.py`, `settings.html`

**Problem**: `save_settings` doesn't save `transcription_*` fields, `host`, or `debug`.

**Fix**: Add transcription fields to the settings form and handler. Defer `host` and `debug` (rarely changed). Update `save_settings` to include `transcription_provider`, `transcription_fallback`, `whisper_model`, `whisper_device`, `whisper_compute_type`.

### Phase 17: Remove duplicate assertion (minor) — `test_models.py`

**Fix**: Remove the duplicate `assert config.llm_provider == LLMProviderName.ANTHROPIC` line.

### Phase 18: Add `_parse_json_response` error to engine docs (C5 partial) — `engine.py`

**Problem**: `_parse_json_response` can raise `ValueError` but no caller documents this.

**Fix**: Add docstrings to `understand_profile`, `generate_question`, and `record_response` noting they can raise `ValueError` on malformed LLM responses.

### Phase 19: Fix cross-module self-imports in transcribe.py (minor) — `transcribe.py`

**Problem**: `_create_provider()` uses `from kbb.transcribe import ...` for classes defined in the same module.

**Fix**: Use direct class references (`FasterWhisperProvider(...)`, etc.) instead of `from kbb.transcribe import ...`.

### Phase 20: Clean up `profile.name` null handling (minor) — `pages.py`

**Problem**: `profile.name if profile else None` is dead code — `read_structured_profile()` always returns a `UserProfile`, never `None`.

**Fix**: Replace with `profile.name or ""` for consistency with `api.py`.

## Task List and Test Cases

- [ ] **Phase 1: Input validation in web routes**
  - [ ] `test_api_transcribe_invalid_topic`: POST with invalid topic → 200 with GENERAL fallback
  - [ ] `test_api_transcribe_invalid_date`: GET logs with invalid date → 400
  - [ ] `test_partial_transcribe_invalid_topic`: POST with invalid topic → falls back to GENERAL
  - [ ] `test_pages_invalid_date`: GET `/daily/logs/invalid-date` → error page (not 500)

- [ ] **Phase 2: Topic mapping consolidation**
  - [ ] `test_topic_directory_property`: `QuestionTopic.EDUCATION.directory == "education"`, `QuestionTopic.OPINION.directory == "general"`
  - [ ] `test_topic_from_directory`: `QuestionTopic.from_directory("work") == QuestionTopic.WORK_EXPERIENCE`
  - [ ] `test_topic_from_directory_unknown`: `QuestionTopic.from_directory("nonexistent") == QuestionTopic.GENERAL`
  - [ ] `test_knowledge_write_read_roundtrip`: Write entry with `OPINION` topic, read it back, topic is `GENERAL` (documented data loss)

- [ ] **Phase 3: Slug consolidation**
  - [ ] `test_slugify_utility`: `slugify("Hello World!") == "hello-world"`, `slugify("a" * 100) == "a" * 80`
  - [ ] `test_knowledge_entry_slug_uses_slugify`: Verify `KnowledgeEntry.slug` delegates to `slugify()`
  - [ ] `test_markdown_store_slugify_uses_slugify`: Verify `_slugify` delegates to `slugify()`

- [ ] **Phase 4: Exception chaining**
  - [ ] `test_transcription_client_fallback_error_chained`: Both fail → exception chain includes fallback error

- [ ] **Phase 5: Move SUPPORTED_AUDIO_EXTENSIONS**
  - [ ] `test_supported_extensions_in_transcribe_module`: `from kbb.transcribe import SUPPORTED_AUDIO_EXTENSIONS` works
  - [ ] `test_supported_extensions_re_exported_from_engine`: `from kbb.engine import SUPPORTED_AUDIO_EXTENSIONS` still works

- [ ] **Phase 6: Public accessors**
  - [ ] `test_transcriber_provider_name_none`: Before init, returns `"unknown"`
  - [ ] `test_transcriber_provider_name_initialized`: After init, returns provider name
  - [ ] `test_engine_data_dir_property`: `engine.data_dir` returns configured path

- [ ] **Phase 7: CLI API key fallback**
  - [ ] `test_resolve_api_key_anthropic`: With ANTHROPIC_API_KEY set and provider=anthropic, returns that key
  - [ ] `test_resolve_api_key_openai`: With OPENAI_API_KEY set and provider=openai, returns that key
  - [ ] `test_resolve_api_key_wrong_provider`: With ANTHROPIC_API_KEY set but provider=openai, does NOT return Anthropic key

- [ ] **Phase 8: Logging for silent skips**
  - [ ] `test_malformed_knowledge_entry_logged`: Malformed file triggers warning log (caplog)

- [ ] **Phase 12: Date import shadowing**
  - [ ] `test_partial_logs_by_date`: Existing test passes with renamed parameter

- [ ] **Phase 13: Remove models_web.py**
  - [ ] Verify no imports exist (grep)
  - [ ] All existing tests pass

- [ ] **Phase 14: Move local import**
  - [ ] `test_api_record_response`: Existing test passes

- [ ] **Phase 15: Remove unused request params**
  - [ ] All existing tests pass

- [ ] **Phase 16: Transcription settings form**
  - [ ] `test_settings_page_has_transcription_fields`: Settings page includes transcription provider, model, device, compute type
  - [ ] `test_save_settings_transcription`: POST settings with transcription fields → persisted

- [ ] **Phase 17: Remove duplicate assertion**
  - [ ] Existing test passes

- [ ] **Phase 19: Fix cross-module self-imports**
  - [ ] `test_create_transcriber_faster_whisper`: Existing test passes
  - [ ] `test_create_transcriber_whisper`: Existing test passes

- [ ] **Phase 20: Fix profile.name handling**
  - [ ] `test_profile_page_no_profile`: Page renders with empty name

## Verification

1. `uv run ruff check src/` — lint clean
2. `uv run ruff format .` — format clean
3. `uv run ty check .` — type check clean
4. `uv run pytest tests/ -v` — all tests pass (133 existing + new)
5. Manual: start web app, submit form with invalid topic → falls back gracefully
6. Manual: start web app, navigate to `/daily/logs/invalid` → error page (not 500)
7. Manual: `uv run kbb status` — confirm no regressions