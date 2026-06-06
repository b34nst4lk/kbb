"""Markdown file storage for knowledge base data."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from datetime import datetime

from kbb.models import DailyLog, KnowledgeEntry, Question, QuestionTopic, UserProfile


class MarkdownStore:
    """Reads and writes all data as markdown files on disk."""

    TOPIC_DIRS: dict[QuestionTopic, str] = {
        QuestionTopic.EDUCATION: "education",
        QuestionTopic.WORK_EXPERIENCE: "work",
        QuestionTopic.LIFE_EXPERIENCE: "life",
        QuestionTopic.SKILL: "skills",
        QuestionTopic.OPINION: "general",
        QuestionTopic.DECISION: "general",
        QuestionTopic.PROCESS: "general",
        QuestionTopic.GENERAL: "general",
    }

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """Create directory structure if it doesn't exist."""
        for subdir in [
            "knowledge/education",
            "knowledge/work",
            "knowledge/life",
            "knowledge/skills",
            "knowledge/general",
            "logs",
        ]:
            (self._data_dir / subdir).mkdir(parents=True, exist_ok=True)

    # --- Profile ---

    def read_profile(self) -> str:
        """Read the raw profile markdown."""
        path = self._data_dir / "profile.md"
        if not path.exists():
            return ""
        return path.read_text()

    def write_profile(self, content: str) -> None:
        """Write the raw profile markdown."""
        path = self._data_dir / "profile.md"
        path.write_text(content)

    def read_structured_profile(self) -> UserProfile:
        """Read the auto-generated structured profile."""
        path = self._data_dir / "profile_structured.md"
        if not path.exists():
            return UserProfile()
        text = path.read_text()
        return self._parse_structured_profile(text)

    def write_structured_profile(self, profile: UserProfile) -> None:
        """Write the structured profile (auto-generated from LLM output)."""
        path = self._data_dir / "profile_structured.md"
        path.write_text(self._format_structured_profile(profile))

    # --- Knowledge ---

    def list_knowledge_entries(self) -> list[KnowledgeEntry]:
        """Scan all knowledge markdown files and return entries."""
        entries: list[KnowledgeEntry] = []
        knowledge_dir = self._data_dir / "knowledge"
        if not knowledge_dir.exists():
            return entries
        for topic_dir in knowledge_dir.iterdir():
            if not topic_dir.is_dir():
                continue
            for md_file in sorted(topic_dir.glob("*.md")):
                try:
                    entries.append(self._parse_knowledge_entry(md_file))
                except Exception:
                    continue  # Skip malformed files
        return entries

    def find_knowledge_entry(self, slug: str) -> KnowledgeEntry | None:
        """Find a knowledge entry by its filename slug.

        Searches across all topic directories. Matches exact slug first,
        then falls back to date-suffixed variants (e.g. slug-2026-06-07.md).
        Returns the most recent match.
        """
        knowledge_dir = self._data_dir / "knowledge"
        if not knowledge_dir.exists():
            return None
        # Try exact match first
        for topic_dir in knowledge_dir.iterdir():
            if not topic_dir.is_dir():
                continue
            path = topic_dir / f"{slug}.md"
            if path.exists():
                return self._parse_knowledge_entry(path)
        # Try date-suffixed match (most recent first)
        for topic_dir in knowledge_dir.iterdir():
            if not topic_dir.is_dir():
                continue
            matches = sorted(topic_dir.glob(f"{slug}-*.md"), reverse=True)
            if matches:
                return self._parse_knowledge_entry(matches[0])
        return None

    def write_knowledge_entry(self, entry: KnowledgeEntry) -> Path:
        """Write a knowledge entry to disk. Returns the file path.

        If a file with the same slug already exists, appends a date suffix.
        If that also exists, appends a counter.
        """
        topic_dir_name = self.TOPIC_DIRS.get(entry.topic, "general")
        topic_dir = self._data_dir / "knowledge" / topic_dir_name
        topic_dir.mkdir(parents=True, exist_ok=True)
        slug = self._slugify(entry.title)
        filepath = self._unique_path(topic_dir, slug)
        filepath.write_text(self._format_knowledge_entry(entry))
        return filepath

    def _unique_path(self, directory: Path, slug: str) -> Path:
        """Generate a unique filepath, appending date suffix on clash, then counter."""
        path = directory / f"{slug}.md"
        if not path.exists():
            return path
        date_suffix = date.today().isoformat()
        path = directory / f"{slug}-{date_suffix}.md"
        if not path.exists():
            return path
        counter = 2
        while True:
            path = directory / f"{slug}-{date_suffix}-{counter}.md"
            if not path.exists():
                return path
            counter += 1

    def get_knowledge_topics_summary(self) -> str:
        """Return a concise summary of what's already documented."""
        entries = self.list_knowledge_entries()
        if not entries:
            return "No knowledge documented yet."
        lines = [f"- {e.title} [{e.topic.value}]" for e in entries]
        return "\n".join(lines)

    # --- Daily Logs ---

    def list_daily_logs(self) -> list[Path]:
        """Return all daily log file paths sorted chronologically."""
        logs_dir = self._data_dir / "logs"
        if not logs_dir.exists():
            return []
        return sorted(logs_dir.glob("*.md"))

    def read_daily_log(self, path: Path) -> DailyLog | None:
        """Read a daily log by file path."""
        if not path.exists():
            return None
        return self._parse_daily_log(path)

    def find_daily_logs_by_date(self, d: date) -> list[DailyLog]:
        """Find all daily logs for a given date."""
        logs_dir = self._data_dir / "logs"
        if not logs_dir.exists():
            return []
        prefix = d.isoformat()
        results = []
        for f in sorted(logs_dir.glob(f"{prefix}*.md")):
            log = self._parse_daily_log(f)
            if log:
                results.append(log)
        return results

    def write_daily_log(self, log: DailyLog) -> Path:
        """Write a daily log to disk. Uses timestamp + slug for filename."""
        ts = log.log_timestamp.strftime("%Y-%m-%dT%H-%M")
        slug = log.slug or self._slugify(log.question)[:40]
        filename = f"{ts}-{slug}.md"
        path = self._data_dir / "logs" / filename
        path.write_text(log.to_markdown())
        return path

    def get_recent_questions(self, limit: int = 10) -> list[str]:
        """Return recent question texts (to avoid repetition)."""
        logs_dir = self._data_dir / "logs"
        if not logs_dir.exists():
            return []
        files = sorted(logs_dir.glob("*.md"), reverse=True)
        questions = []
        for f in files[:limit]:
            log = self._parse_daily_log(f)
            if log:
                questions.append(log.question)
        return questions

    # --- Pending Question ---

    def read_pending_question(self) -> Question | None:
        """Read the pending question, if any. Returns None if no question is pending."""
        path = self._data_dir / "pending_question.md"
        if not path.exists():
            return None
        text = path.read_text()
        if not text.strip():
            return None

        question = ""
        topic = QuestionTopic.GENERAL
        rationale = ""

        for line in text.split("\n"):
            if line.startswith("**Question**:"):
                question = line.split("**Question**:", 1)[1].strip()
            elif line.startswith("**Topic**:"):
                topic_str = line.split("**Topic**:", 1)[1].strip()
                try:
                    topic = QuestionTopic(topic_str)
                except ValueError:
                    pass
            elif line.startswith("**Rationale**:"):
                rationale = line.split("**Rationale**:", 1)[1].strip()

        if not question:
            return None
        return Question(text=question, topic=topic, rationale=rationale)

    def write_pending_question(self, question: Question) -> None:
        """Persist a generated question so it survives between commands."""
        path = self._data_dir / "pending_question.md"
        lines = [
            "# Pending Question\n",
            f"**Question**: {question.text}",
            f"**Topic**: {question.topic.value}",
            f"**Rationale**: {question.rationale}",
        ]
        path.write_text("\n".join(lines))

    def clear_pending_question(self) -> None:
        """Remove the pending question file after it's been answered."""
        path = self._data_dir / "pending_question.md"
        if path.exists():
            path.unlink()

    # --- Knowledge Import ---

    def import_markdown_file(self, source_path: Path, topic: QuestionTopic) -> KnowledgeEntry:
        """Import an external markdown file as a knowledge entry."""
        content = source_path.read_text()
        entry = KnowledgeEntry(
            title=source_path.stem.replace("-", " ").replace("_", " ").title(),
            content=content,
            topic=topic,
            source="import",
            created_at=date.today(),
        )
        self.write_knowledge_entry(entry)
        return entry

    # --- Private helpers ---

    @staticmethod
    def _slugify(text: str) -> str:
        """Convert text to a URL-safe slug for filenames."""
        slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
        # Limit length to avoid excessively long filenames
        return slug[:80] if len(slug) > 80 else slug

    def _parse_structured_profile(self, text: str) -> UserProfile:
        """Parse structured profile markdown into UserProfile."""
        profile = UserProfile(raw_markdown=text)

        current_section: str | None = None
        section_map = {
            "education": "education",
            "work experience": "work_experience",
            "life experience": "life_experience",
            "interests": "interests",
        }

        for line in text.split("\n"):
            # Parse name from title line
            if line.startswith("# ") and "Profile" in line:
                name = line.replace("#", "").replace("Profile:", "").strip()
                # Remove colon suffix if present
                name = name.rstrip(":").strip()
                if name:
                    profile.name = name
                continue

            # Parse section headers
            if line.startswith("## "):
                header = line.lstrip("#").strip().lower()
                current_section = section_map.get(header)
                continue

            # Parse list items
            if line.strip().startswith("- ") and current_section:
                value = line.strip().lstrip("- ").strip()
                if value:
                    getattr(profile, current_section).append(value)

        # Set last_updated from footer
        for line in reversed(text.split("\n")):
            if "Last updated:" in line:
                # Extract date from footer
                date_str = line.split("Last updated:")[1].strip().rstrip("*").strip()
                try:
                    profile.last_updated = datetime.fromisoformat(date_str)
                except (ValueError, IndexError):
                    pass
                break

        return profile

    def _format_structured_profile(self, profile: UserProfile) -> str:
        """Format UserProfile as markdown."""
        lines: list[str] = []
        if profile.name:
            lines.append(f"# Profile: {profile.name}\n")
        if profile.education:
            lines.append("## Education")
            for e in profile.education:
                lines.append(f"- {e}")
            lines.append("")
        if profile.work_experience:
            lines.append("## Work Experience")
            for w in profile.work_experience:
                lines.append(f"- {w}")
            lines.append("")
        if profile.life_experience:
            lines.append("## Life Experience")
            for le in profile.life_experience:
                lines.append(f"- {le}")
            lines.append("")
        if profile.interests:
            lines.append("## Interests")
            for i in profile.interests:
                lines.append(f"- {i}")
            lines.append("")
        if profile.last_updated:
            lines.append(f"*Last updated: {profile.last_updated.isoformat()}*")
        return "\n".join(lines)

    def _parse_knowledge_entry(self, path: Path) -> KnowledgeEntry:
        """Parse a knowledge entry from markdown."""
        text = path.read_text()
        topic_name = path.parent.name
        # Map directory names back to QuestionTopic
        topic_reverse = {
            "education": QuestionTopic.EDUCATION,
            "work": QuestionTopic.WORK_EXPERIENCE,
            "life": QuestionTopic.LIFE_EXPERIENCE,
            "skills": QuestionTopic.SKILL,
            "general": QuestionTopic.GENERAL,
        }
        topic = topic_reverse.get(topic_name, QuestionTopic.GENERAL)

        # Parse title from first heading
        title = path.stem.replace("-", " ").replace("_", " ").title()
        for line in text.split("\n"):
            if line.startswith("# "):
                title = line.lstrip("#").strip()
                break

        # Parse metadata line
        source = "import"
        created_at: date | None = None
        tags: list[str] = []
        for line in text.split("\n"):
            if line.startswith("*") and "Topic:" in line:
                # Parse: *Topic: education | Source: import | Date: 2026-06-06*
                meta = line.strip("*").strip()
                for part in meta.split("|"):
                    part = part.strip()
                    if part.startswith("Source:"):
                        source = part.split(":", 1)[1].strip()
                    elif part.startswith("Date:"):
                        date_str = part.split(":", 1)[1].strip()
                        try:
                            created_at = date.fromisoformat(date_str)
                        except ValueError:
                            pass
                    elif part.startswith("Tags:"):
                        tags = [
                            t.strip() for t in part.split(":", 1)[1].strip().split(",") if t.strip()
                        ]
                break

        # Content is everything after the metadata
        content_lines: list[str] = []
        in_content = False
        for line in text.split("\n"):
            if in_content:
                content_lines.append(line)
            elif line.startswith("*") and "Topic:" in line:
                # Skip the metadata line and any blank line after it
                in_content = True
                continue

        content = "\n".join(content_lines).strip() if content_lines else text.strip()

        return KnowledgeEntry(
            title=title,
            content=content,
            topic=topic,
            source=source,
            created_at=created_at,
            tags=tags,
        )

    def _format_knowledge_entry(self, entry: KnowledgeEntry) -> str:
        """Format a knowledge entry as markdown."""
        meta_parts = [f"Topic: {entry.topic.value}", f"Source: {entry.source}"]
        if entry.created_at:
            meta_parts.append(f"Date: {entry.created_at.isoformat()}")
        meta_line = " | ".join(meta_parts)

        lines: list[str] = [
            f"# {entry.title}\n",
            f"*{meta_line}*\n",
        ]
        if entry.tags:
            lines.append(f"*Tags: {', '.join(entry.tags)}*\n")
        lines.append(entry.content)
        return "\n".join(lines)

    def _parse_daily_log(self, path: Path) -> DailyLog:
        """Parse a daily log from markdown."""
        text = path.read_text()

        # Parse timestamp from title: "# Daily Log — 2026-06-06 14:30"
        log_timestamp = datetime.now()
        for line in text.split("\n"):
            if line.startswith("# ") and "—" in line:
                ts_str = line.split("—")[1].strip()
                # Try parsing "2026-06-06 14:30" format
                try:
                    log_timestamp = datetime.strptime(ts_str, "%Y-%m-%d %H:%M")
                except ValueError:
                    # Fallback: try date-only format for backwards compat
                    try:
                        log_timestamp = datetime.strptime(ts_str, "%Y-%m-%d")
                    except ValueError:
                        pass
                break

        # Parse slug from filename: "2026-06-06T14-30-skill-testing.md"
        slug = ""
        stem = path.stem
        # Extract everything after the timestamp prefix (YYYY-MM-DDTHH-MM-)
        slug_match = re.match(r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-(.+)", stem)
        if slug_match:
            slug = slug_match.group(1)

        # Parse question line: **Question** (topic): text
        question = ""
        question_topic = QuestionTopic.GENERAL
        for line in text.split("\n"):
            if line.startswith("**Question**"):
                # Extract topic from parentheses
                topic_match = re.search(r"\((\w+)\)", line)
                if topic_match:
                    try:
                        question_topic = QuestionTopic(topic_match.group(1))
                    except ValueError:
                        pass
                # Extract question text after the colon
                colon_idx = line.find(":")
                if colon_idx >= 0:
                    question = line[colon_idx + 1 :].strip()
                break

        # Parse rationale
        rationale = ""
        for line in text.split("\n"):
            if line.startswith("**Rationale**"):
                colon_idx = line.find(":")
                if colon_idx >= 0:
                    rationale = line[colon_idx + 1 :].strip()
                break

        # Parse response and recorded knowledge sections
        response = ""
        recorded_entry = ""
        sections = text.split("## ")
        for section in sections:
            if section.startswith("Response"):
                response = section.replace("Response", "", 1).strip()
            elif section.startswith("Recorded Knowledge"):
                recorded_entry = section.replace("Recorded Knowledge", "", 1).strip()

        return DailyLog(
            log_timestamp=log_timestamp,
            question=question,
            question_topic=question_topic,
            question_rationale=rationale,
            response=response,
            recorded_entry=recorded_entry,
            slug=slug,
        )
