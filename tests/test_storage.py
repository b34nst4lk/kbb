"""Tests for MarkdownStore."""

from datetime import date, datetime
from pathlib import Path

import pytest

from kbb.models import DailyLog, KnowledgeEntry, Question, QuestionTopic, UserProfile
from kbb.storage.markdown_store import MarkdownStore


class TestProfile:
    def test_read_write_profile(self, mock_store: MarkdownStore):
        profile_text = "# About Me\n\nI'm a software engineer with 10 years of experience."
        mock_store.write_profile(profile_text)
        result = mock_store.read_profile()
        assert result == profile_text

    def test_read_nonexistent_profile(self, mock_store: MarkdownStore):
        result = mock_store.read_profile()
        assert result == ""

    def test_write_and_read_structured_profile(
        self, mock_store: MarkdownStore, sample_profile: UserProfile
    ):
        mock_store.write_structured_profile(sample_profile)
        result = mock_store.read_structured_profile()
        assert result.name == sample_profile.name
        assert result.education == sample_profile.education
        assert result.work_experience == sample_profile.work_experience

    def test_round_trip_structured_profile(self, mock_store: MarkdownStore):
        profile = UserProfile(
            name="Alice",
            education=["BS Physics"],
            work_experience=["Data Scientist"],
            life_experience=[],
            interests=["Reading"],
            last_updated=datetime(2026, 6, 6, 12, 0, 0),
        )
        mock_store.write_structured_profile(profile)
        result = mock_store.read_structured_profile()
        assert result.name == "Alice"
        assert result.education == ["BS Physics"]


class TestKnowledgeEntries:
    def test_write_and_list_entry(self, mock_store: MarkdownStore):
        entry = KnowledgeEntry(
            title="My Testing Philosophy",
            content="I prefer pytest over unittest...",
            topic=QuestionTopic.SKILL,
            source="daily_log",
            created_at=date(2026, 6, 5),
        )
        path = mock_store.write_knowledge_entry(entry)
        assert path.exists()

        entries = mock_store.list_knowledge_entries()
        assert len(entries) == 1
        assert entries[0].title == "My Testing Philosophy"
        assert entries[0].topic == QuestionTopic.SKILL

    def test_knowledge_topics_summary_empty(self, mock_store: MarkdownStore):
        summary = mock_store.get_knowledge_topics_summary()
        assert summary == "No knowledge documented yet."

    def test_knowledge_topics_summary_with_entries(self, mock_store: MarkdownStore):
        entry = KnowledgeEntry(
            title="Testing Tips",
            content="Use pytest fixtures...",
            topic=QuestionTopic.SKILL,
        )
        mock_store.write_knowledge_entry(entry)
        summary = mock_store.get_knowledge_topics_summary()
        assert "Testing Tips" in summary
        assert "skill" in summary

    def test_import_markdown_file(self, mock_store: MarkdownStore, tmp_path: Path):
        # Create a temporary markdown file to import
        source = tmp_path / "my-notes.md"
        source.write_text("# My Notes\n\nSome important knowledge here.")

        entry = mock_store.import_markdown_file(source, QuestionTopic.GENERAL)
        assert entry.title == "My Notes"
        assert entry.source == "import"
        assert entry.topic == QuestionTopic.GENERAL

        # Verify it's persisted
        entries = mock_store.list_knowledge_entries()
        assert len(entries) == 1

    def test_parse_knowledge_entry_missing_frontmatter_raises(self, mock_store: MarkdownStore):
        """A knowledge entry file without frontmatter should raise ValueError."""
        # Manually write a file without frontmatter
        topic_dir = mock_store._data_dir / "knowledge" / "general"
        topic_dir.mkdir(parents=True, exist_ok=True)
        (topic_dir / "no-frontmatter.md").write_text("# No Frontmatter\n\nJust plain markdown.\n")

        with pytest.raises(ValueError, match="missing frontmatter"):
            mock_store._parse_knowledge_entry(topic_dir / "no-frontmatter.md")

    def test_knowledge_entry_collapsed_topic_preserved_via_frontmatter(
        self, mock_store: MarkdownStore
    ):
        """OPINION, DECISION, PROCESS are written to 'general' directory but
        the original topic IS preserved through YAML frontmatter."""
        entry = KnowledgeEntry(
            title="Opinion on Testing",
            content="I think pytest is great",
            topic=QuestionTopic.OPINION,
            source="daily_log",
            created_at=date(2026, 6, 7),
        )
        path = mock_store.write_knowledge_entry(entry)
        # Written to 'general' directory (collapsed topic directory)
        assert "general" in str(path)

        entries = mock_store.list_knowledge_entries()
        assert len(entries) == 1
        # Topic is preserved via frontmatter — OPINION survives the round-trip
        assert entries[0].topic == QuestionTopic.OPINION
        assert entries[0].title == "Opinion on Testing"

    def test_knowledge_entry_direct_topic_round_trips(self, mock_store: MarkdownStore):
        """Topics with their own directories round-trip correctly."""
        entry = KnowledgeEntry(
            title="Education Notes",
            content="I studied CS",
            topic=QuestionTopic.EDUCATION,
            source="import",
            created_at=date(2026, 6, 7),
        )
        mock_store.write_knowledge_entry(entry)

        entries = mock_store.list_knowledge_entries()
        assert len(entries) == 1
        assert entries[0].topic == QuestionTopic.EDUCATION

    def test_knowledge_entry_topic_fallback_to_directory(self, mock_store: MarkdownStore):
        """When frontmatter topic is invalid, falls back to directory-based lookup."""
        entry = KnowledgeEntry(
            title="Education Notes",
            content="I studied CS",
            topic=QuestionTopic.EDUCATION,
            source="import",
            created_at=date(2026, 6, 7),
        )
        mock_store.write_knowledge_entry(entry)
        entries = mock_store.list_knowledge_entries()
        assert len(entries) == 1
        assert entries[0].topic == QuestionTopic.EDUCATION


class TestDailyLogs:
    def test_write_and_read_daily_log(self, mock_store: MarkdownStore, sample_daily_log: DailyLog):
        path = mock_store.write_daily_log(sample_daily_log)
        assert path.exists()
        # Filename should contain timestamp and slug
        assert "2026-06-05" in path.name
        assert "skill-testing-preference" in path.name

        result = mock_store.read_daily_log(path)
        assert result is not None
        assert result.question == sample_daily_log.question
        assert result.question_topic == sample_daily_log.question_topic
        assert result.response == sample_daily_log.response

    def test_write_daily_log_uses_slug(self, mock_store: MarkdownStore):
        log = DailyLog(
            log_timestamp=datetime(2026, 6, 5, 14, 30),
            question="What is your approach to testing?",
            question_topic=QuestionTopic.SKILL,
            question_rationale="Testing",
            response="I use pytest",
            recorded_entry="Recorded",
            slug="skill-testing-approach",
        )
        path = mock_store.write_daily_log(log)
        assert "skill-testing-approach" in path.name

    def test_multiple_logs_per_day(self, mock_store: MarkdownStore):
        log1 = DailyLog(
            log_timestamp=datetime(2026, 6, 5, 9, 0),
            question="Q1",
            question_topic=QuestionTopic.SKILL,
            question_rationale="R1",
            response="A1",
            recorded_entry="R1",
            slug="skill-testing",
        )
        log2 = DailyLog(
            log_timestamp=datetime(2026, 6, 5, 14, 30),
            question="Q2",
            question_topic=QuestionTopic.EDUCATION,
            question_rationale="R2",
            response="A2",
            recorded_entry="R2",
            slug="education-phd",
        )
        path1 = mock_store.write_daily_log(log1)
        path2 = mock_store.write_daily_log(log2)
        assert path1 != path2  # Different filenames
        assert path1.exists()
        assert path2.exists()

        # find_daily_logs_by_date should return both
        logs = mock_store.find_daily_logs_by_date(date(2026, 6, 5))
        assert len(logs) == 2

    def test_find_daily_logs_by_date_empty(self, mock_store: MarkdownStore):
        logs = mock_store.find_daily_logs_by_date(date(2020, 1, 1))
        assert logs == []

    def test_list_daily_logs(self, mock_store: MarkdownStore):
        log1 = DailyLog(
            log_timestamp=datetime(2026, 6, 5, 9, 0),
            question="Q1",
            question_topic=QuestionTopic.SKILL,
            question_rationale="R1",
            response="A1",
            recorded_entry="R1",
            slug="skill-testing",
        )
        log2 = DailyLog(
            log_timestamp=datetime(2026, 6, 6, 14, 30),
            question="Q2",
            question_topic=QuestionTopic.EDUCATION,
            question_rationale="R2",
            response="A2",
            recorded_entry="R2",
            slug="education-phd",
        )
        mock_store.write_daily_log(log1)
        mock_store.write_daily_log(log2)

        paths = mock_store.list_daily_logs()
        assert len(paths) == 2

    def test_get_recent_questions(self, mock_store: MarkdownStore):
        for i in range(3):
            log = DailyLog(
                log_timestamp=datetime(2026, 6, i + 1, 9, 0),
                question=f"Question {i}",
                question_topic=QuestionTopic.GENERAL,
                question_rationale="Test",
                response=f"Response {i}",
                recorded_entry=f"Recorded {i}",
                slug=f"general-question-{i}",
            )
            mock_store.write_daily_log(log)

        questions = mock_store.get_recent_questions(limit=2)
        assert len(questions) == 2
        # Most recent first
        assert "Question 2" in questions[0]


class TestPendingQuestion:
    def test_write_and_read_pending_question(self, mock_store: MarkdownStore):
        question = Question(
            text="What testing strategy do you prefer?",
            topic=QuestionTopic.SKILL,
            rationale="The user has software engineering experience",
        )
        mock_store.write_pending_question(question)

        result = mock_store.read_pending_question()
        assert result is not None
        assert result.text == "What testing strategy do you prefer?"
        assert result.topic == QuestionTopic.SKILL
        assert result.rationale == "The user has software engineering experience"

    def test_read_pending_question_none(self, mock_store: MarkdownStore):
        result = mock_store.read_pending_question()
        assert result is None

    def test_clear_pending_question(self, mock_store: MarkdownStore):
        question = Question(
            text="What is your approach?",
            topic=QuestionTopic.PROCESS,
            rationale="Test",
        )
        mock_store.write_pending_question(question)
        assert mock_store.read_pending_question() is not None

        mock_store.clear_pending_question()
        assert mock_store.read_pending_question() is None

    def test_clear_pending_question_idempotent(self, mock_store: MarkdownStore):
        # Clearing when there's no pending question should be a no-op
        mock_store.clear_pending_question()
        assert mock_store.read_pending_question() is None

    def test_pending_question_uses_frontmatter(self, mock_store: MarkdownStore):
        """Verify pending question file uses YAML frontmatter format."""
        question = Question(
            text="What is your approach?",
            topic=QuestionTopic.PROCESS,
            rationale="Test rationale",
        )
        mock_store.write_pending_question(question)
        path = mock_store._data_dir / "pending_question.md"
        content = path.read_text()
        assert content.startswith("---")
        assert "question:" in content
        assert "topic: process" in content
        assert "rationale:" in content


class TestSlugify:
    def test_basic_slugify(self):
        result = MarkdownStore._slugify("My Testing Philosophy")
        assert result == "my-testing-philosophy"

    def test_special_characters(self):
        result = MarkdownStore._slugify("What's the best approach? (2024)")
        assert "?" not in result
        assert "(" not in result

    def test_long_title_truncation(self):
        long_title = "A" * 200
        result = MarkdownStore._slugify(long_title)
        assert len(result) <= 80
