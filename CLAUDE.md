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
  models_web.py             # Pydantic form schemas
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

## LLM Provider Pattern

All three providers implement the `LLMProvider` protocol:
- `complete(prompt, *, system, json_schema)` → `str` (structured output via native provider APIs)
- `stream(prompt, *, system)` → `AsyncGenerator[str, None]`
- `name` → `str` (e.g. `"anthropic/claude-sonnet-4-20250514"`)

Structured output uses Pydantic schemas (`ProfileSchema`, `QuestionSchema`) converted to strict-compatible JSON schemas via `strict_json_schema()`. This ensures all providers guarantee schema-conformant JSON — no fragile brace-matching or auto-closing needed.

## Storage Format

All markdown files use YAML frontmatter (Obsidian-compatible). No legacy format support — zero users, no migration needed.

**Knowledge entry** (`knowledge/general/slug.md`):
```yaml
---
title: project-stakeholder-management
topic: process
source: daily_log
date: 2026-06-06
tags: [daily-log, process]
---
```

**Daily log** (`logs/2026-06-06T21-53-slug.md`): frontmatter with date, topic, slug.

**Aggregate daily note** (`logs/2026-06-06.md`): frontmatter with date, wikilinks to individual logs.

**Pending question** (`pending_question.md`): frontmatter with question, topic, rationale.

## Development Commands

```bash
uv run pytest tests/ -v           # Run all tests
uv run ruff check src/             # Lint
uv run ruff format .               # Format (ALWAYS run after changes)
uv run ty check .                  # Type check
uv run kbb --data-dir data init    # Initialize data directory
uv run kbb --data-dir data status  # Show status
```

## Coding Standards

- **Python 3.13+** with `from __future__ import annotations` in all files
- **Type hints** on all public functions; ty checks must pass
- **Ruff** for linting (line-length 100) and formatting — always run `uv run ruff format .` after changes
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

## Product Requirements

- **Profile-based**: Learns who you are, tailors questions accordingly
- **Knowledge-aware**: Avoids repeating questions, builds on existing knowledge
- **Faithful recording**: LLM reorganizes but NEVER adds outside information to responses
- **Pluggable LLM**: Claude, GPT, or local models via Ollama
- **Markdown storage**: All data as human-readable files, Obsidian-compatible
- **Multiple interfaces**: CLI (Typer), Web (FastAPI+HTMX), Desktop (pywebview), upcoming: Telegram, Discord
- **Voice-to-text**: Implemented — faster-whisper (default), openai-whisper (MPS), OpenAI API; browser mic recording

## Upcoming Features (Roadmap)

1. ~~**Voice-to-text transcription**~~ — ✅ Implemented in `src/kbb/transcribe.py`
2. **Telegram bot** (`src/kbb_telegram/`) — push questions, receive text/voice responses
3. **Discord bot** (`src/kbb_discord/`) — same as Telegram but via DMs

See plan files in `docs/` for detailed implementation plans.

## Plan Convention

Plans are saved in `docs/` as `NNN_<descriptive_name>.plan.md` where `NNN` is a zero-padded sequence number. Every plan must follow this structure:

```markdown
# <Title>

## Context and Use Case
<!-- Why this change is needed, what problem it solves, who it serves -->

## Requirements
<!-- What the implementation must satisfy — functional and non-functional -->

## Proposals
<!-- One or more approaches considered, with tradeoffs -->

## Technical Solutions
<!-- Chosen approach with detailed design: new modules, classes, data flow, API changes -->

## Task List and Test Cases
<!-- TDD-format checklist. Each item names the class/function, its signature,
     expected behavior, and a test describing initial conditions + assertions.
     Use markdown checkboxes. -->

- [ ] **`module.Class.method(self, arg: type) -> RetType`**
  Expected behavior: …
  - [ ] `test_method_does_x_when_y`: Given …, asserts …
  - [ ] `test_method_raises_on_bad_z`: Given …, asserts …
```

All sections are required. Task items must include function signatures and test cases with explicit initial conditions and assertions.