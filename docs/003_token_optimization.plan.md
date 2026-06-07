# LLM Context Token Optimization

## Context and Use Case

Claude Code auto-loads CLAUDE.md, README.md, and memory files every session (~600 lines total). Additionally, when an LLM explores the codebase, it reads source files, tests, docs, and config. Many of these contain redundant or low-signal content that wastes tokens without improving understanding. This plan reduces auto-loaded context by ~130 lines (17%) and eliminates major sources of on-demand token waste.

## Requirements

1. Reduce auto-loaded context (CLAUDE.md + README.md + memory) without losing essential coding guidance
2. Eliminate redundant content across CLAUDE.md, README.md, and memory files
3. Add `.claudeignore` to exclude files with zero coding context value (uv.lock, completed plans, data dirs)
4. Add missing type annotations on web route handlers so LLMs can infer return types from signatures
5. Trim docstrings that just restate the filename or method name
6. Fix stale references in CLAUDE.md (deleted models_web.py, wrong ruff check path)
7. Move deferred import in models.py to top-level (improves dependency visibility for LLMs)
8. Untrack `src/data/` runtime files from git
9. All existing tests must pass; new changes need test coverage where applicable

## Proposals

### Chosen: Incremental phased changes grouped by file impact

Each phase targets one concern and can be verified independently. Phases are ordered by impact and dependency.

### Rejected

- **Keep memory files as-is** — User confirmed both CLAUDE-md.md and ruff-format.md should be deleted. Their unique content merges into CLAUDE.md (Phase 2).

## Technical Solutions

### Phase 1: Add .claudeignore

Create `.claudeignore` at project root to exclude files that have zero coding context value:

```
uv.lock
data/
data2/
vault/
src/data/
.coverage
htmlcov/
docs/001_voice_transcription.plan.md
docs/002_maintainability_fixes.plan.md
docs/logo.svg
```

**Impact**: Prevents ~312KB lock file + 823 lines of completed plans from ever entering LLM context.

### Phase 2: Slim CLAUDE.md

Remove or condense these sections from CLAUDE.md (160 lines → ~100 lines):

1. **Remove Plan Convention template** (lines 131-160, ~30 lines) — Already covered by `memory/plan-convention.md` which adds rationale. Replace with a 2-line pointer: `Plans follow the convention in docs/plan-convention.md (see memory for details).`

2. **Remove Storage Format examples** (lines 58-73, ~16 lines) — The field names are already in the architecture section. Replace with: `All files use YAML frontmatter with fields: title, topic, source, date, tags (knowledge entries); date, topic, slug (daily logs); question, topic, rationale (pending questions).`

3. **Condense Product Requirements** (lines 113-122, ~10 lines) — Merge into Architecture section as a 3-line bullet list under "Key pattern".

4. **Fix stale references**: Remove `models_web.py` from architecture (deleted in Phase 13), change `ruff check src/` to `ruff check .`, add note about `ruff check .` including test files.

5. **Consolidate Development Commands + Coding Standards ruff note** — Add "run `uv run ruff format .`, `uv run ruff check .`, and `uv run ty check .` as the final step before considering the task done" to the dev commands section, removing the shorter version from Coding Standards.

### Phase 3: Restructure README.md

Reorder README.md to front-load developer-relevant content and move user setup to the bottom:

1. **Move Architecture section** (currently near the bottom) to directly after Features
2. **Move Configuration section** up (env vars are useful for coding)
3. **Move Data Storage section** up (directory layout is useful for coding)
4. **Move Setup, Voice Setup, CLI Commands, Ollama, Daily Automation, Obsidian Integration** to the end — these are user-facing and rarely needed for coding

No content deleted — just reordered. An LLM reading top-to-bottom hits useful info first.

### Phase 4: Add return type annotations to web route handlers

All 30 route handlers in `pages.py`, `partials.py`, and `api.py` lack return type annotations. This forces an LLM to read each handler's body to understand what it returns.

Add `-> HTMLResponse` to all page and partial handlers, and `-> <ResponseModel>` to API handlers:

**`pages.py`** (9 handlers): All return `-> HTMLResponse`
**`partials.py`** (11 handlers): All return `-> HTMLResponse`
**`api.py`** (10 handlers): Return typed response models (e.g., `-> StatusResponse`, `-> ProfileResponse`, `-> list[KnowledgeEntryResponse]`)

Tests: Existing web tests verify these return types implicitly. No new tests needed.

### Phase 5: Trim low-value docstrings

Remove or condense docstrings that just restate the filename or method name:

**Module-level** (just restate the filename):
- `kbb/models.py`: "Core data models for Knowledge Base Builder." → remove (file name is self-explanatory)
- `kbb/llm/__init__.py`: "LLM abstraction layer." → remove
- `kbb/llm/anthropic_provider.py`: "Anthropic (Claude) LLM provider." → remove
- `kbb/storage/__init__.py`: "Storage backends for knowledge base data." → remove
- `kbb_cli/__init__.py`: "CLI adapter for Knowledge Base Builder." → remove
- `kbb_web/routes/__init__.py`: "Route modules for the web adapter." → remove

**Method-level** (just paraphrase the method name — in `markdown_store.py`):
- `read_profile()`: "Read the raw profile markdown." → remove
- `write_profile()`: "Write the raw profile markdown." → remove
- `read_structured_profile()`: already has useful content (returns empty UserProfile if missing)
- `write_structured_profile()`: "Write the structured profile (auto-generated from LLM output)." → keep parenthetical
- Various others: remove if they just restate the name; keep if they add "why" or edge case info

**Condense verbose docstrings**:
- `DailyLog.to_markdown()` (22 lines → 8 lines): Remove the full format example block. Instead: "Format contract: `_parse_daily_log()` must parse this exact layout — YAML frontmatter (date, topic, slug), H1 heading, **Question** (topic), **Rationale**, ## Response, ## Recorded Knowledge."
- `MarkdownStore._parse_daily_log()` (11 lines → 4 lines): Remove format list that duplicates `to_markdown()`. Instead: "Parse a daily log. Expected format matches `DailyLog.to_markdown()` output. Logs a warning on missing frontmatter and uses defaults."

### Phase 6: Move deferred import in models.py

Move `from kbb.obsidian import format_frontmatter` from line 173 inside `DailyLog.to_markdown()` to the top-level imports of `models.py`. No circular dependency exists — `obsidian.py` only imports `json`, `Path`, and `yaml`.

### Phase 7: Untrack src/data/ and remove docs/logo.svg

1. Add `src/data/` to `.gitignore`
2. Run `git rm --cached -r src/data/`
3. Delete `docs/logo.svg` (duplicate of `src/kbb_web/static/icons/logo.svg`)

### Phase 8: Clean up memory files

1. Delete `memory/CLAUDE-md.md` — pure overhead, meta-description of a file that is always loaded
2. Delete `memory/ruff-format.md` — its content ("run ruff format/check/ty as final step", "use `ruff check .` not `src/`") is preserved in CLAUDE.md dev commands section (Phase 2)
3. Consolidate `memory/workflow-preferences.md`, `memory/stacked-pr-workflow.md`, and `memory/selective-git-add.md` into a single `memory/workflow-preferences.md` — all three contain workflow rules that are easier to find in one place
4. Update `memory/MEMORY.md` to reflect the changes (remove deleted entries, update consolidated entry)

## Task List and Test Cases

- [x] **Phase 1: Create .claudeignore** ✅
  - [x] Created `.claudeignore` with uv.lock, data dirs, completed plans, .coverage, htmlcov, docs/logo.svg

- [x] **Phase 2: Slim CLAUDE.md** ✅ (161 → 100 lines, 38% reduction)
  - [x] Removed Plan Convention template (replaced with 2-line pointer to memory/plan-convention.md)
  - [x] Removed Storage Format examples (condensed to 1-line field list)
  - [x] Condensed Product Requirements + Roadmap into 1-line "Product" under Key pattern
  - [x] Fixed stale `models_web.py` reference, changed `ruff check src/` → `ruff check .`
  - [x] Consolidated ruff/ty "final step" note into dev commands section
  - [x] All 178 tests pass

- [x] **Phase 3: Restructure README.md** ✅
  - [x] Moved Architecture, Configuration, Data Storage before Setup/CLI/Obsidian
  - [x] All 178 tests pass

- [x] **Phase 4: Return type annotations on route handlers** ✅
  - [x] `pages.py` (9 handlers): `-> HTMLResponse`
  - [x] `partials.py` (11 handlers): `-> HTMLResponse`
  - [x] `api.py` (10 handlers): `-> StatusResponse`, `-> ProfileResponse`, `-> list[KnowledgeEntryResponse]`, etc.
  - [x] `uv run ty check .` passes

- [x] **Phase 5: Trim low-value docstrings** ✅ (~54 lines removed)
  - [x] Removed 6 module docstrings (models, llm/__init__, anthropic_provider, storage/__init__, kbb_cli/__init__, routes/__init__)
  - [x] Removed markdown_store.py module docstring + 12 method docstrings that just restated the name
  - [x] Condensed `DailyLog.to_markdown()` (22 lines → 4 lines)
  - [x] Condensed `MarkdownStore._parse_daily_log()` (11 lines → 3 lines)
  - [x] All 178 tests pass

- [x] **Phase 6: Move deferred import in models.py** ✅
  - [x] Moved `from kbb.obsidian import format_frontmatter` to top-level
  - [x] No circular import — `uv run python -c "import kbb.models"` OK
  - [x] `uv run ty check .` passes

- [x] **Phase 7: Untrack src/data/** ✅ (deviation: kept docs/logo.svg)
  - [x] Added `src/data/` to `.gitignore`
  - [x] `git rm --cached -r src/data/` (5 files untracked)
  - [x] **Deviation**: Did not delete `docs/logo.svg` — it has different SVG comments than `src/kbb_web/static/icons/logo.svg` (not a true duplicate)

- [x] **Phase 8: Clean up memory files** ✅
  - [x] Deleted CLAUDE-md.md, ruff-format.md, stacked-pr-workflow.md, selective-git-add.md
  - [x] Consolidated all workflow preferences into single `memory/workflow-preferences.md`
  - [x] Updated `memory/MEMORY.md` (6 entries → 2 entries)

## Verification

1. `uv run ruff check .` — lint clean (including tests)
2. `uv run ruff format .` — format clean
3. `uv run ty check .` — type check clean
4. `uv run pytest tests/ -v` — all tests pass (178+)
5. Measure CLAUDE.md line count before and after (target: ~100 lines, down from 160)
6. Verify no circular imports after Phase 6: `python -c "import kbb.models"`