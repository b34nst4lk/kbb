# Knowledge Base Builder (KBB)

## Project Overview

KBB builds a personal knowledge base through daily question-answer interactions. It learns who you are via a profile, generates targeted questions based on your background and existing knowledge, and records your responses as structured knowledge entries. All data is stored as human-readable, Obsidian-compatible markdown with YAML frontmatter.

**Version**: 0.2.0

## Architecture

```
src/kbb/                    # Core library — integration-agnostic
  engine.py                 # KBPEngine: orchestrator (no I/O)
  models.py                 # Data models (QuestionTopic, UserProfile, KnowledgeEntry, DailyLog, Question, KBBConfig, TranscriptionProviderName)
  obsidian.py               # YAML frontmatter helpers, vault config generation
  transcribe.py             # TranscriptionProvider protocol, FasterWhisperProvider, WhisperProvider, OpenAITranscriptionProvider, TranscriptionClient, create_transcriber()
  llm/
    base.py                 # LLMProvider protocol, LLMClient, create_provider() factory
    schemas.py              # Pydantic schemas (ProfileSchema, QuestionSchema) + strict_json_schema()
    prompts.py              # All prompt templates
    anthropic_provider.py    # Anthropic/Claude — output_config structured output
    openai_provider.py       # OpenAI — ResponseFormatJSONSchema structured output
    ollama_provider.py       # Ollama native — format parameter guided decoding
  storage/
    markdown_store.py        # All file I/O: profile, knowledge, daily logs, pending questions, Obsidian sync
src/kbb_cli/                # CLI adapter (Typer + Rich)
src/kbb_web/                # Web adapter (FastAPI + HTMX + Jinja2)
  app.py                    # create_app(), markdown filter, global error handler
  config.py                 # WebConfig, YAML config loading
  dependencies.py           # FastAPI Depends() for engine, config, templates
  desktop.py                # pywebview wrapper
  routes/
    pages.py                # Full-page HTML routes
    partials.py              # HTMX partial routes (HTML fragments)
    api.py                  # JSON API routes
  static/css/kbb.css
  static/icons/favicon.svg, logo.svg
  static/js/kbb.js          # Ctrl+Enter, auto-focus, error display, VoiceRecorder, transcribeAudio()
  templates/                # Jinja2 templates (base, pages, partials)
```

**Key pattern**: Core library (`src/kbb/`) never touches I/O directly. Adapters (CLI, web, desktop, upcoming Telegram/Discord) call engine methods and handle presentation.

**Product**: Profile-based Q&A that learns who you are, avoids repeating questions, faithfully records responses (LLM reorganizes but never adds outside info), supports Claude/GPT/Ollama, stores all data as Obsidian-compatible markdown, offers CLI/Web/Desktop interfaces, and supports voice-to-text transcription.

## LLM Provider Pattern

All three providers implement the `LLMProvider` protocol:
- `complete(prompt, *, system, json_schema)` → `str` (structured output via native provider APIs)
- `stream(prompt, *, system)` → `AsyncGenerator[str, None]`
- `name` → `str` (e.g. `"anthropic/claude-sonnet-4-20250514"`)

Structured output uses Pydantic schemas (`ProfileSchema`, `QuestionSchema`) converted to strict-compatible JSON schemas via `strict_json_schema()`. This ensures all providers guarantee schema-conformant JSON — no fragile brace-matching or auto-closing needed.

## Storage Format

All markdown files use YAML frontmatter (Obsidian-compatible). No legacy format support. Fields: title, topic, source, date, tags (knowledge entries); date, topic, slug (daily logs); question, topic, rationale (pending questions).

## Development Commands

```bash
uv run pytest tests/ -v           # Run all tests
uv run ruff check .               # Lint (entire codebase including tests)
uv run ruff format .               # Format
uv run ty check .                  # Type check
uv run kbb --data-dir data init    # Initialize data directory
uv run kbb --data-dir data status  # Show status
```

Always run `uv run ruff format .`, `uv run ruff check .`, and `uv run ty check .` as the final step before considering a task done.

## Coding Standards

- **Python 3.13+** with `from __future__ import annotations` in all files
- **Type hints** on all public functions; ty checks must pass
- **Ruff** for linting (line-length 100) and formatting
- **Pydantic v2** for structured LLM output validation
- **YAML frontmatter** for all markdown metadata (via `kbb.obsidian.format_frontmatter` / `parse_frontmatter`)
- **No `try/except ... pass`** without an inline comment explaining why the exception is safe to ignore
- **Provider-native structured output** for all JSON responses — no manual JSON extraction or auto-closing
- **`LLMProvider` protocol** with `stream` returning `AsyncGenerator[str, None]` (not `AsyncIterator`)
- **`TranscriptionProvider` protocol** with `transcribe(audio_path, *, language)` → `str`; `TranscriptionClient` wraps primary + fallback
- **`MarkdownStore`** raises `ValueError` on missing frontmatter (no legacy fallback)
- **Error messages** should be clear about what went wrong and what the user should do

## Testing Standards

- **pytest** with `asyncio_mode = "auto"`, `testpaths = ["tests"]`
- **MockProvider** in `tests/helpers.py` returns canned responses based on system prompt content matching
- **MockTranscriptionProvider** in `tests/helpers.py` returns canned transcription text, records calls
- Engine tests inject MockProvider by replacing `engine._llm`
- Storage tests use `tmp_path` for filesystem isolation
- Web tests use Starlette TestClient with mock-backed engine
- Provider factory tests gracefully skip with `pytest.skip()` if provider packages aren't installed
- All tests must pass before considering a task complete: `uv run pytest tests/ -v`
- Test file naming: `test_<module>.py` matching `src/<package>/<module>.py`
- `ty: ignore[too-many-positional-arguments]` on `pytest.skip()` calls (known ty false positive)

## Plan Convention

Plans are saved in `docs/` as `NNN_<descriptive_name>.plan.md`. See `memory/plan-convention.md` for the required section structure and TDD task list format.