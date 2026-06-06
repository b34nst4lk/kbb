# Knowledge Base Builder

A CLI tool that builds a personal knowledge base through daily questions. It understands who you are, reviews what you've already documented, and prompts you with targeted questions to extract your knowledge.

## Features

- **Profile-based**: Tell the system about your education, work experience, and life background
- **Knowledge-aware**: Questions are derived from what's already known about you, avoiding repetition
- **Daily prompts**: Generates one targeted question per day to extract knowledge
- **Faithful recording**: Responses are recorded coherently without adding outside information
- **Pluggable LLM**: Works with Claude (Anthropic) or GPT (OpenAI)
- **Markdown storage**: All data stored as human-readable, editable markdown files

## Setup

```bash
# Install dependencies
pip install -e ".[dev]"

# Set your API key
export ANTHROPIC_API_KEY="your-key-here"
# or: export KBB_API_KEY="your-key-here"

# Initialize the knowledge base
kbb init

# Set up your profile
kbb profile-setup

# Answer today's question
kbb daily-respond
```

## Commands

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

Ollama's default endpoint is `http://localhost:11434/v1`. To use a different host, set `KBB_LLM_BASE_URL`:

```bash
export KBB_LLM_BASE_URL=http://my-server:11434/v1
```

## Daily Automation

Add to your crontab for daily question prompts:

```bash
# Generate a question every morning at 9am
0 9 * * * cd /path/to/project && kbb daily-question >> /tmp/kbb-question.log 2>&1
```

## Architecture

The core library (`src/kbb/`) is fully importable and integration-agnostic. The CLI (`src/kbb_cli/`) is a thin adapter. This design makes it straightforward to build integrations like Telegram bots or Discord bots that reuse the same engine.

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