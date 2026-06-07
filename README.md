# Knowledge Base Builder

A personal knowledge base that grows through daily questions. It understands who you are, reviews what you've already documented, and prompts you with targeted questions to extract your knowledge.

## Features

- **Profile-based**: Tell the system about your education, work experience, and life background
- **Knowledge-aware**: Questions are derived from what's already known about you, avoiding repetition
- **Daily prompts**: Generates one targeted question per day to extract knowledge
- **Faithful recording**: Responses are recorded coherently without adding outside information
- **Pluggable LLM**: Works with Claude (Anthropic), GPT (OpenAI), or local models (Ollama)
- **Voice-to-text**: Record audio in the browser or upload files; transcribed locally via faster-whisper (default), openai-whisper (MPS), or OpenAI Whisper API
- **Markdown storage**: All data stored as human-readable, editable markdown files
- **Multiple interfaces**: CLI, web app, and desktop wrapper

## Interface Coverage

| Feature | CLI | Web | Desktop | Telegram | Discord |
|---|:---:|:---:|:---:|:---:|:---:|
| Initialize data directory | ✅ | — | — | 🔜 | 🔜 |
| Profile setup / edit | ✅ | ✅ | ✅ | 🔜 | 🔜 |
| Profile view | ✅ | ✅ | ✅ | 🔜 | 🔜 |
| Profile refresh | ✅ | ✅ | ✅ | 🔜 | 🔜 |
| Generate daily question | ✅ | ✅ | ✅ | 🔜 | 🔜 |
| Record response | ✅ | ✅ | ✅ | 🔜 | 🔜 |
| Voice recording (browser) | — | ✅ | ✅ | 🔜 | 🔜 |
| Transcribe audio file | ✅ | ✅ | ✅ | 🔜 | 🔜 |
| Transcribe + respond | ✅ | ✅ | ✅ | 🔜 | 🔜 |
| Knowledge list | ✅ | ✅ | ✅ | 🔜 | 🔜 |
| Knowledge detail view | — | ✅ | ✅ | 🔜 | 🔜 |
| Import knowledge (file) | ✅ | — | — | 🔜 | 🔜 |
| Import knowledge (text) | — | ✅ | ✅ | 🔜 | 🔜 |
| Daily logs list | — | ✅ | ✅ | 🔜 | 🔜 |
| View log by date | ✅ | ✅ | ✅ | 🔜 | 🔜 |
| Status overview | ✅ | ✅ | ✅ | 🔜 | 🔜 |
| Settings / configuration | — | ✅ | ✅ | 🔜 | 🔜 |
| JSON API | — | ✅ | ✅ | 🔜 | 🔜 |
| Sync Obsidian vault | ✅ | — | — | 🔜 | 🔜 |

✅ = implemented · 🔜 = upcoming · — = not applicable

## Setup

```bash
# Install with web support
pip install -e ".[web]"

# Or with all interfaces
pip install -e ".[all]"

# Set your API key
export ANTHROPIC_API_KEY="your-key-here"
# or: export KBB_API_KEY="your-key-here"

# Initialize the knowledge base
kbb init

# Set up your profile
kbb profile-setup

# Answer today's question
kbb daily-respond

# Or launch the web app
uvicorn kbb_web.app:app --port 8199
```

### Voice Transcription Setup

```bash
# Install with local transcription support (faster-whisper, recommended)
pip install -e ".[transcription]"

# Or with openai-whisper (for Apple Silicon MPS/GPU acceleration)
pip install -e ".[transcription-whisper]"

# Or use OpenAI Whisper API (no local model needed, costs $0.006/min)
# Just set your API key — no extra install required
```

| Provider | Install | Speed | Memory | GPU |
|----------|---------|-------|--------|-----|
| faster-whisper | `.[transcription]` | 4–6× faster | 4× less | CUDA only |
| openai-whisper | `.[transcription-whisper]` | Baseline | Higher | CUDA + MPS |
| OpenAI API | (included) | Fastest (cloud) | None | N/A |

## CLI Commands

| Command | Description |
|---|---|
| `kbb init` | Initialize data directory |
| `kbb profile-setup` | Create your profile (opens editor) |
| `kbb profile-show` | Display your profile |
| `kbb profile-refresh` | Re-parse profile after manual edits |
| `kbb knowledge-list` | List all knowledge entries |
| `kbb knowledge-import <file>` | Import a markdown file as knowledge |
| `kbb daily-question` | Generate and display today's question |
| `kbb daily-respond` | Answer today's question (opens editor) |
| `kbb daily-respond-voice <audio>` | Transcribe audio file and record as response |
| `kbb daily-log [date]` | View a daily log |
| `kbb transcribe <audio>` | Transcribe an audio file to text |
| `kbb status` | Show knowledge base status |
| `kbb sync-vault` | Regenerate Obsidian vault config and daily notes |

## Configuration

| Environment Variable | Default | Description |
|---|---|---|
| `KBB_API_KEY` | — | API key for the LLM provider |
| `KBB_LLM_PROVIDER` | `anthropic` | LLM provider (`anthropic`, `openai`, or `ollama`) |
| `KBB_LLM_MODEL` | Provider-specific | Model to use |
| `KBB_LLM_BASE_URL` | — | Custom endpoint URL (for OpenAI-compatible APIs) |
| `KBB_DATA_DIR` | `data` | Path to data directory |
| `KBB_TRANSCRIPTION_PROVIDER` | `faster-whisper` | Transcription provider (`faster-whisper`, `whisper`, or `openai`) |
| `KBB_WHISPER_MODEL` | `base` | Whisper model size (`tiny`, `base`, `small`, `medium`, `large-v3`) |
| `KBB_WHISPER_DEVICE` | `auto` | Device for local models (`auto`, `cpu`, `cuda`, `mps`) |
| `KBB_WHISPER_COMPUTE_TYPE` | `auto` | Compute type for faster-whisper (`auto`, `int8`, `float16`, `float32`) |

Config file search order: `KBB_CONFIG_FILE` env → `./kbb.yaml` → `~/.config/kbb/kbb.yaml` → `~/.kbb.yaml`

### YAML Configuration

```yaml
llm:
  provider: anthropic
  model: claude-sonnet-4-20250514
  api_key: ""           # or set ANTHROPIC_API_KEY / KBB_API_KEY
  base_url: ""

transcription:
  provider: faster-whisper   # faster-whisper | whisper | openai
  fallback: openai            # optional: fall back if primary fails
  whisper_model: base         # tiny/base/small/medium/large-v3
  whisper_device: auto        # auto/cpu/cuda/mps
  whisper_compute_type: auto  # auto/int8/float16/float32 (faster-whisper only)
```

### Using with Ollama

```bash
# Make sure Ollama is running locally
ollama serve

# Pull a model
ollama pull llama3

# Run KBB with Ollama
export KBB_LLM_PROVIDER=ollama
export KBB_LLM_MODEL=llama3
kbb profile-setup
```

Ollama's default endpoint is `http://localhost:11434`. To use a different host, set `KBB_LLM_BASE_URL`:

```bash
export KBB_LLM_BASE_URL=http://my-server:11434
```

## Daily Automation

Add to your crontab for daily question prompts:

```bash
# Generate a question every morning at 9am
0 9 * * * cd /path/to/project && kbb daily-question >> /tmp/kbb-question.log 2>&1
```

## Architecture

The core library (`src/kbb/`) is integration-agnostic — it never touches I/O directly. Adapters (CLI, web, desktop, upcoming Telegram/Discord) call engine methods and handle presentation.

```python
from kbb.engine import KBPEngine
from kbb.models import KBBConfig

engine = KBPEngine(KBBConfig(llm_api_key="..."))
question = await engine.generate_daily_question()
log = await engine.record_response(question, user_response)

# Voice transcription
text = await engine.transcribe(Path("recording.webm"))
log = await engine.transcribe_and_record(question, Path("recording.webm"))
```

## Obsidian Integration

The data directory is Obsidian-compatible — open it directly as an Obsidian vault. Knowledge entries and daily logs use YAML frontmatter for metadata, and aggregate daily notes link to individual logs with `[[wikilinks]]`.

```bash
# Open your KBB data directory in Obsidian
# File → Open Vault → choose your data/ folder
```

All files use frontmatter for metadata that Obsidian can index:

```markdown
---
title: project-stakeholder-management
topic: process
source: daily_log
date: 2026-06-06
tags: [daily-log, process]
---

# project-stakeholder-management
...
```

Daily notes aggregate all logs for a given date:

```markdown
---
date: 2026-06-06
---

# Daily Note — 2026-06-06

## How do you prioritize stakeholder expectations?

![[2026-06-06T21-53-project-stakeholder-management]]
```

To regenerate all daily notes and Obsidian config (e.g., after upgrading from a legacy format):

```bash
kbb sync-vault
```

## Data Storage

All data is stored as markdown files in the `data/` directory:

```
data/
├── .obsidian/               # Obsidian vault config
│   ├── app.json
│   └── daily-notes.json
├── profile.md              # Your profile (edit this directly)
├── profile_structured.md   # Auto-generated structured view
├── knowledge/
│   ├── education/
│   ├── work/
│   ├── life/
│   ├── skill/
│   ├── opinion/
│   ├── decision/
│   ├── process/
│   └── general/
└── logs/
    ├── 2026-06-06.md                            # Aggregate daily note (Obsidian)
    └── 2026-06-06T21-53-project-stakeholder-management.md
```