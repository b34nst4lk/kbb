"""Core business logic orchestrator for Knowledge Base Builder.

The engine is integration-agnostic — it never touches CLI I/O or
messaging APIs directly. Adapters (CLI, Telegram, Discord) call
engine methods and handle I/O themselves.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

from kbb.models import (
    DailyLog,
    KBBConfig,
    KnowledgeEntry,
    Question,
    QuestionTopic,
    UserProfile,
)
from kbb.llm.base import LLMClient, create_provider
from kbb.storage.markdown_store import MarkdownStore


class KBPEngine:
    """Core business logic orchestrator.

    No CLI, no Telegram, no Discord — pure domain logic.
    """

    def __init__(self, config: KBBConfig) -> None:
        self._config = config
        if config.data_dir is None:
            raise ValueError("Data directory is required. Set KBB_DATA_DIR or use --data-dir.")
        self._store = MarkdownStore(config.data_dir)
        provider = create_provider(
            config.llm_provider.value,
            api_key=config.llm_api_key,
            model=config.llm_model,
            base_url=config.llm_base_url,
        )
        self._llm = LLMClient(provider)

    # --- Workflow: Profile Setup ---

    async def setup_profile_from_text(self, raw_text: str) -> UserProfile:
        """Take freeform profile text, persist it, and use the LLM
        to extract structured information."""
        # Save raw profile (source of truth)
        self._store.write_profile(raw_text)

        # Use LLM to understand the profile
        structured_data = await self._llm.understand_profile(raw_text)

        profile = UserProfile(
            name=structured_data.get("name", ""),
            education=structured_data.get("education", []),
            work_experience=structured_data.get("work_experience", []),
            life_experience=structured_data.get("life_experience", []),
            interests=structured_data.get("interests", []),
            raw_markdown=raw_text,
            last_updated=datetime.now(),
        )

        # Save structured version (derived view)
        self._store.write_structured_profile(profile)
        return profile

    # --- Workflow: Knowledge Import ---

    async def import_knowledge(
        self,
        file_path: Path,
        topic: QuestionTopic = QuestionTopic.GENERAL,
    ) -> KnowledgeEntry:
        """Import an existing document as a knowledge entry."""
        entry = self._store.import_markdown_file(file_path, topic)
        return entry

    async def import_knowledge_from_text(
        self,
        title: str,
        content: str,
        topic: QuestionTopic = QuestionTopic.GENERAL,
    ) -> KnowledgeEntry:
        """Import knowledge from raw text."""
        entry = KnowledgeEntry(
            title=title,
            content=content,
            topic=topic,
            source="import",
            created_at=date.today(),
        )
        self._store.write_knowledge_entry(entry)
        return entry

    # --- Workflow: Daily Question Generation ---

    async def generate_daily_question(self) -> Question:
        """Generate a question based on the user's profile and existing knowledge,
        avoiding recently asked questions."""
        profile = self._store.read_structured_profile()
        if not profile or not profile.raw_markdown:
            raise ValueError(
                "No profile found. Run 'kbb profile-setup' first or edit data/profile.md directly."
            )

        knowledge_entries = self._store.list_knowledge_entries()
        recent_questions = self._store.get_recent_questions(limit=10)

        question = await self._llm.generate_question(
            profile=profile,
            knowledge_entries=knowledge_entries,
            recent_questions=recent_questions,
        )

        # Persist the question so it survives between commands
        self._store.write_pending_question(question)
        return question

    # --- Workflow: Response Recording ---

    async def record_response(
        self,
        question: Question,
        response: str,
    ) -> DailyLog:
        """Record a user's response to a daily question.

        The LLM reorganizes the response into a coherent knowledge entry,
        but adds NO outside information.
        """
        profile = self._store.read_structured_profile()

        # Generate the recorded entry and slug in parallel-ish
        recorded_entry = await self._llm.record_response(
            question=question.text,
            response=response,
            profile=profile,
        )
        slug = await self._llm.generate_slug(question.text, response)

        log = DailyLog(
            log_timestamp=datetime.now(),
            question=question.text,
            question_topic=question.topic,
            question_rationale=question.rationale,
            response=response,
            recorded_entry=recorded_entry,
            slug=slug,
        )

        self._store.write_daily_log(log)

        # Also write the recorded entry as a knowledge entry
        entry = KnowledgeEntry(
            title=slug,
            content=recorded_entry,
            topic=question.topic,
            source="daily_log",
            created_at=date.today(),
            tags=["daily-log", question.topic.value],
        )
        self._store.write_knowledge_entry(entry)

        # Clear the pending question since it's been answered
        self._store.clear_pending_question()

        return log

    # --- Workflow: Daily Batch (question + response) ---

    async def run_daily_batch(
        self,
        get_response: Callable[[Question], str],
    ) -> DailyLog:
        """Run the full daily cycle: generate question, get response, record it.

        The get_response callback is provided by the adapter layer
        (CLI, Telegram, etc.) — the engine stays integration-agnostic.
        """
        question = await self.generate_daily_question()
        response = get_response(question)
        return await self.record_response(question, response)

    # --- Read operations ---

    def get_profile(self) -> UserProfile:
        """Read the structured profile."""
        return self._store.read_structured_profile()

    def get_raw_profile(self) -> str:
        """Read the raw profile markdown."""
        return self._store.read_profile()

    def get_knowledge_entries(self) -> list[KnowledgeEntry]:
        """List all knowledge entries."""
        return self._store.list_knowledge_entries()

    def get_knowledge_entry(self, slug: str) -> KnowledgeEntry | None:
        """Find a single knowledge entry by slug."""
        return self._store.find_knowledge_entry(slug)

    def get_all_daily_logs(self) -> list[Path]:
        """List all daily log file paths."""
        return self._store.list_daily_logs()

    def find_daily_logs_by_date(self, d: date) -> list[DailyLog]:
        """Find all daily logs for a given date."""
        return self._store.find_daily_logs_by_date(d)

    async def refresh_profile(self) -> UserProfile:
        """Re-read the raw profile and re-structure it via LLM.

        Called after the user edits profile.md externally.
        """
        raw = self._store.read_profile()
        if not raw:
            raise ValueError("No profile found to refresh.")
        return await self.setup_profile_from_text(raw)

    def get_pending_question(self) -> Question | None:
        """Read the pending question, if any."""
        return self._store.read_pending_question()

    def sync_obsidian_vault(self) -> None:
        """Regenerate all daily notes and Obsidian config.

        Useful for one-time migration or manual resync after upgrading
        from the legacy format to frontmatter-based storage.
        """
        self._store.sync_obsidian_vault()
