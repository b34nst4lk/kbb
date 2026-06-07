"""Tests for data models."""

from datetime import date, datetime

from kbb.models import (
    DailyLog,
    KBBConfig,
    KnowledgeEntry,
    LLMProviderName,
    Question,
    QuestionTopic,
    UserProfile,
)
from kbb.models import slugify


class TestQuestionTopic:
    def test_values(self):
        assert QuestionTopic.EDUCATION.value == "education"
        assert QuestionTopic.WORK_EXPERIENCE.value == "work_experience"
        assert QuestionTopic.LIFE_EXPERIENCE.value == "life_experience"
        assert QuestionTopic.SKILL.value == "skill"
        assert QuestionTopic.OPINION.value == "opinion"
        assert QuestionTopic.DECISION.value == "decision"
        assert QuestionTopic.PROCESS.value == "process"
        assert QuestionTopic.GENERAL.value == "general"

    def test_from_string(self):
        assert QuestionTopic("education") == QuestionTopic.EDUCATION
        assert QuestionTopic("general") == QuestionTopic.GENERAL

    def test_directory_direct_topics(self):
        """Topics with their own directories map correctly."""
        assert QuestionTopic.EDUCATION.directory == "education"
        assert QuestionTopic.WORK_EXPERIENCE.directory == "work"
        assert QuestionTopic.LIFE_EXPERIENCE.directory == "life"
        assert QuestionTopic.SKILL.directory == "skills"
        assert QuestionTopic.GENERAL.directory == "general"

    def test_directory_collapsed_topics(self):
        """OPINION, DECISION, and PROCESS collapse to the 'general' directory."""
        assert QuestionTopic.OPINION.directory == "general"
        assert QuestionTopic.DECISION.directory == "general"
        assert QuestionTopic.PROCESS.directory == "general"

    def test_from_directory(self):
        """Directory names map back to the correct topics."""
        assert QuestionTopic.from_directory("education") == QuestionTopic.EDUCATION
        assert QuestionTopic.from_directory("work") == QuestionTopic.WORK_EXPERIENCE
        assert QuestionTopic.from_directory("life") == QuestionTopic.LIFE_EXPERIENCE
        assert QuestionTopic.from_directory("skills") == QuestionTopic.SKILL
        assert QuestionTopic.from_directory("general") == QuestionTopic.GENERAL

    def test_from_directory_unknown(self):
        """Unknown directory names default to GENERAL."""
        assert QuestionTopic.from_directory("unknown") == QuestionTopic.GENERAL
        assert QuestionTopic.from_directory("random") == QuestionTopic.GENERAL

    def test_directory_round_trip_lossy(self):
        """OPINION, DECISION, and PROCESS cannot round-trip through directory.

        These topics map to "general" but from_directory("general") returns GENERAL,
        not the original topic. This is intentional: the original topic is lost
        when the knowledge entry is stored in the "general" directory.
        """
        assert (
            QuestionTopic.from_directory(QuestionTopic.OPINION.directory) == QuestionTopic.GENERAL
        )
        assert (
            QuestionTopic.from_directory(QuestionTopic.DECISION.directory) == QuestionTopic.GENERAL
        )
        assert (
            QuestionTopic.from_directory(QuestionTopic.PROCESS.directory) == QuestionTopic.GENERAL
        )

    def test_directory_round_trip_direct(self):
        """Topics with their own directories round-trip correctly."""
        assert (
            QuestionTopic.from_directory(QuestionTopic.EDUCATION.directory)
            == QuestionTopic.EDUCATION
        )
        assert (
            QuestionTopic.from_directory(QuestionTopic.WORK_EXPERIENCE.directory)
            == QuestionTopic.WORK_EXPERIENCE
        )
        assert (
            QuestionTopic.from_directory(QuestionTopic.LIFE_EXPERIENCE.directory)
            == QuestionTopic.LIFE_EXPERIENCE
        )
        assert QuestionTopic.from_directory(QuestionTopic.SKILL.directory) == QuestionTopic.SKILL


class TestSlugify:
    def test_basic_slugify(self):
        assert slugify("My Testing Philosophy") == "my-testing-philosophy"

    def test_special_characters(self):
        result = slugify("What's the best approach? (2024)")
        assert "?" not in result
        assert "(" not in result

    def test_long_title_truncation(self):
        long_title = "A" * 200
        result = slugify(long_title)
        assert len(result) <= 80

    def test_custom_max_length(self):
        result = slugify("Hello World", max_length=5)
        assert len(result) <= 5

    def test_leading_trailing_hyphens_stripped(self):
        assert slugify("---hello---") == "hello"

    def test_knowledge_entry_slug_delegates(self):
        """KnowledgeEntry.slug delegates to slugify()."""
        entry = KnowledgeEntry(title="My Testing Philosophy", content="content")
        assert entry.slug == slugify("My Testing Philosophy")


class TestUserProfile:
    def test_defaults(self):
        profile = UserProfile()
        assert profile.name == ""
        assert profile.education == []
        assert profile.work_experience == []
        assert profile.life_experience == []
        assert profile.interests == []
        assert profile.raw_markdown == ""
        assert profile.last_updated is None

    def test_summary_with_data(self):
        profile = UserProfile(
            name="Jane",
            education=["BS CS"],
            work_experience=["Engineer at Co"],
            life_experience=["Lived abroad"],
            interests=["Python"],
        )
        summary = profile.summary
        assert "Jane" in summary
        assert "BS CS" in summary
        assert "Engineer at Co" in summary
        assert "Lived abroad" in summary
        assert "Python" in summary

    def test_summary_empty_falls_back_to_raw(self):
        profile = UserProfile(raw_markdown="Just some freeform text")
        assert profile.summary == "Just some freeform text"

    def test_summary_no_name(self):
        profile = UserProfile(education=["BS CS"])
        assert "Education: BS CS" in profile.summary


class TestKnowledgeEntry:
    def test_defaults(self):
        entry = KnowledgeEntry(title="Test", content="Content")
        assert entry.topic == QuestionTopic.GENERAL
        assert entry.source == "daily_log"
        assert entry.created_at is None
        assert entry.tags == []

    def test_custom_values(self):
        entry = KnowledgeEntry(
            title="My Testing Philosophy",
            content="I prefer pytest...",
            topic=QuestionTopic.SKILL,
            source="import",
            created_at=date(2026, 6, 5),
            tags=["testing", "python"],
        )
        assert entry.title == "My Testing Philosophy"
        assert entry.topic == QuestionTopic.SKILL
        assert entry.source == "import"


class TestDailyLog:
    def test_to_markdown(self):
        log = DailyLog(
            log_timestamp=datetime(2026, 6, 5, 14, 30),
            question="What testing framework do you prefer?",
            question_topic=QuestionTopic.SKILL,
            question_rationale="The user has software engineering experience",
            response="I prefer pytest because it's more Pythonic",
            recorded_entry="## Testing Preference\n\nI prefer pytest because it is more Pythonic.",
            slug="skill-testing-preference",
        )
        md = log.to_markdown()
        assert "# Daily Log — 2026-06-05 14:30" in md
        assert "**Question** (skill)" in md
        assert "What testing framework do you prefer?" in md
        assert "**Rationale**" in md
        assert "## Response" in md
        assert "I prefer pytest because it's more Pythonic" in md
        assert "## Recorded Knowledge" in md
        assert "I prefer pytest because it is more Pythonic." in md


class TestQuestion:
    def test_creation(self):
        q = Question(
            text="What testing strategy do you prefer?",
            topic=QuestionTopic.SKILL,
            rationale="The user has software engineering experience",
        )
        assert q.text == "What testing strategy do you prefer?"
        assert q.topic == QuestionTopic.SKILL


class TestKBBConfig:
    def test_defaults(self):
        config = KBBConfig()
        assert config.data_dir is None  # Must be provided explicitly
        assert config.llm_provider == LLMProviderName.ANTHROPIC
        assert config.llm_model == "claude-sonnet-4-20250514"
        assert config.llm_api_key == ""
        assert config.daily_log_time == "09:00"
