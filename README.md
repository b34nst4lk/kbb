# Knowledge Base Builder

A personal knowledge base that grows through daily questions. It understands who you are, reviews what you've already documented, and prompts you with targeted questions to extract your knowledge.

## Features

- **Profile-based**: Tell the system about your education, work experience, and life background
- **Knowledge-aware**: Questions are derived from what's already known about you, avoiding repetition
- **Daily prompts**: Generates one targeted question per day to extract knowledge
- **Faithful recording**: Responses are recorded coherently without adding outside information
- **Pluggable LLM**: Works with Claude (Anthropic), GPT (OpenAI), or local models (Ollama)
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
| Knowledge list | ✅ | ✅ | ✅ | 🔜 | 🔜 |
| Knowledge detail view | — | ✅ | ✅ | 🔜 | 🔜 |
| Import knowledge (file) | ✅ | — | — | 🔜 | 🔜 |
| Import knowledge (text) | — | ✅ | ✅ | 🔜 | 🔜 |
| Daily logs list | — | ✅ | ✅ | 🔜 | 🔜 |
| View log by date | ✅ | ✅ | ✅ | 🔜 | 🔜 |
| Status overview | ✅ | ✅ | ✅ | 🔜 | 🔜 |
| Settings / configuration | — | ✅ | ✅ | 🔜 | 🔜 |
| JSON API | — | ✅ | ✅ | 🔜 | 🔜 |

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
| `kbb daily-log [date]` | View a daily log |
| `kbb status` | Show knowledge base status |

## Configuration

| Environment Variable | Default | Description |
|---|---|---|
| `KBB_API_KEY` | — | API key for the LLM provider |
| `KBB_LLM_PROVIDER` | `anthropic` | LLM provider (`anthropic`, `openai`, or `ollama`) |
| `KBB_LLM_MODEL` | Provider-specific | Model to use |
| `KBB_LLM_BASE_URL` | — | Custom endpoint URL (for OpenAI-compatible APIs) |
| `KBB_DATA_DIR` | `data` | Path to data directory |

Config file search order: `KBB_CONFIG_FILE` env → `./kbb.yaml` → `~/.config/kbb/kbb.yaml` → `~/.kbb.yaml`

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
```

## Data Storage

All data is stored as markdown files in the `data/` directory:

```
data/
├── profile.md              # Your profile (edit this directly)
├── profile_structured.md   # Auto-generated structured view
├── knowledge/
│   ├── education/
│   ├── work/
│   ├── life/
│   ├── skills/
│   └── general/
└── logs/
    └── 2026-06-06.md       # Daily question + response logs
```