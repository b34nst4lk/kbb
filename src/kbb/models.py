from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from pathlib import Path


def slugify(text: str, max_length: int = 80) -> str:
    """Convert text to a URL-safe slug. Truncates to max_length.

    Replaces non-alphanumeric characters with hyphens, lowercases,
    strips leading/trailing hyphens, and truncates to max_length.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_length] if len(slug) > max_length else slug


class QuestionTopic(str, Enum):
    """Topics for knowledge extraction questions.

    Note: OPINION, DECISION, and PROCESS map to the "general" directory.
    When reading files, the topic is preserved via YAML frontmatter, so
    these values survive round-trips. The directory-based fallback
    (from_directory) maps "general" → GENERAL, losing the original value.
    """

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
        """Return the filesystem directory name for this topic."""
        _dirs: dict[str, str] = {
            "education": "education",
            "work_experience": "work",
            "life_experience": "life",
            "skill": "skills",
            "opinion": "general",
            "decision": "general",
            "process": "general",
            "general": "general",
        }
        return _dirs[self.value]

    @classmethod
    def from_directory(cls, dir_name: str) -> QuestionTopic:
        """Return the QuestionTopic for a filesystem directory name.

        Unknown directory names default to GENERAL.
        """
        _reverse: dict[str, QuestionTopic] = {
            "education": cls.EDUCATION,
            "work": cls.WORK_EXPERIENCE,
            "life": cls.LIFE_EXPERIENCE,
            "skills": cls.SKILL,
            "general": cls.GENERAL,
        }
        return _reverse.get(dir_name, cls.GENERAL)


class LLMProviderName(str, Enum):
    """Supported LLM providers."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OLLAMA = "ollama"


class TranscriptionProviderName(str, Enum):
    """Supported transcription providers."""

    FASTER_WHISPER = "faster-whisper"
    WHISPER = "whisper"
    OPENAI = "openai"


@dataclass
class UserProfile:
    """Structured representation of who the user is."""

    name: str = ""
    education: list[str] = field(default_factory=list)
    work_experience: list[str] = field(default_factory=list)
    life_experience: list[str] = field(default_factory=list)
    interests: list[str] = field(default_factory=list)
    raw_markdown: str = ""
    last_updated: datetime | None = None

    @property
    def summary(self) -> str:
        """Return a concise text summary for LLM context."""
        parts = []
        if self.name:
            parts.append(f"Name: {self.name}")
        if self.education:
            parts.append("Education: " + "; ".join(self.education))
        if self.work_experience:
            parts.append("Work: " + "; ".join(self.work_experience))
        if self.life_experience:
            parts.append("Life experience: " + "; ".join(self.life_experience))
        if self.interests:
            parts.append("Interests: " + "; ".join(self.interests))
        return "\n".join(parts) if parts else self.raw_markdown


@dataclass
class KnowledgeEntry:
    """A single piece of documented knowledge."""

    title: str
    content: str
    topic: QuestionTopic = QuestionTopic.GENERAL
    source: str = "daily_log"  # "daily_log" or "import"
    created_at: date | None = None
    tags: list[str] = field(default_factory=list)

    @property
    def slug(self) -> str:
        """URL-safe slug derived from the title.

        This is a computed property, not stored. The title is the
        canonical source; the slug is derived on access.
        """
        return slugify(self.title)


@dataclass
class DailyLog:
    """A log of one day's question-answer exchange."""

    log_timestamp: datetime
    question: str
    question_topic: QuestionTopic
    question_rationale: str
    response: str
    recorded_entry: str
    slug: str = ""

    def to_markdown(self) -> str:
        """Format contract: ``_parse_daily_log`` must parse this exact layout.

        YAML frontmatter (date, topic, slug), H1 heading, **Question** (topic),
        **Rationale**, ## Response, ## Recorded Knowledge.
        """
        from kbb.obsidian import format_frontmatter

        frontmatter = format_frontmatter(
            {
                "date": self.log_timestamp.strftime("%Y-%m-%d"),
                "topic": self.question_topic.value,
                "slug": self.slug or None,
            }
        )
        ts = self.log_timestamp.strftime("%Y-%m-%d %H:%M")
        return (
            f"{frontmatter}"
            f"# Daily Log — {ts}\n\n"
            f"**Question** ({self.question_topic.value}): {self.question}\n\n"
            f"**Rationale**: {self.question_rationale}\n\n"
            f"## Response\n\n{self.response}\n\n"
            f"## Recorded Knowledge\n\n{self.recorded_entry}\n"
        )


@dataclass
class Question:
    """A question generated by the system for the user."""

    text: str
    topic: QuestionTopic
    rationale: str


@dataclass
class KBBConfig:
    """Application configuration."""

    data_dir: Path | None = None  # Must be provided explicitly via --data-dir or KBB_DATA_DIR
    llm_provider: LLMProviderName = LLMProviderName.ANTHROPIC
    llm_model: str = "claude-sonnet-4-20250514"
    llm_api_key: str = ""
    llm_base_url: str = ""  # Custom endpoint (e.g. Ollama, Azure OpenAI)
    daily_log_time: str = "09:00"

    # Transcription settings
    transcription_provider: TranscriptionProviderName = TranscriptionProviderName.FASTER_WHISPER
    transcription_fallback: TranscriptionProviderName | None = None
    whisper_model: str = "base"
    whisper_device: str = "auto"
    whisper_compute_type: str = "auto"
