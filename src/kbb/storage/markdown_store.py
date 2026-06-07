"""Markdown file storage for knowledge base data.

All files use YAML frontmatter for Obsidian compatibility.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

from kbb.models import DailyLog, KnowledgeEntry, Question, QuestionTopic, UserProfile
from kbb.obsidian import format_frontmatter, generate_obsidian_config, parse_frontmatter


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
        # Ensure Obsidian config exists
        generate_obsidian_config(self._data_dir)

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
        """Return all daily log file paths sorted chronologically.

        Excludes aggregate daily notes (YYYY-MM-DD.md without a timestamp).
        """
        logs_dir = self._data_dir / "logs"
        if not logs_dir.exists():
            return []
        return sorted(
            p
            for p in logs_dir.glob("*.md")
            # Skip aggregate daily notes: they match YYYY-MM-DD.md (no T in stem)
            if "T" in p.stem
        )

    def read_daily_log(self, path: Path) -> DailyLog | None:
        """Read a daily log by file path."""
        if not path.exists():
            return None
        return self._parse_daily_log(path)

    def find_daily_logs_by_date(self, d: date) -> list[DailyLog]:
        """Find all daily logs for a given date.

        Excludes aggregate daily notes (YYYY-MM-DD.md without a timestamp).
        """
        logs_dir = self._data_dir / "logs"
        if not logs_dir.exists():
            return []
        prefix = d.isoformat()
        results = []
        for f in sorted(logs_dir.glob(f"{prefix}*.md")):
            # Skip aggregate daily notes (no T in stem = YYYY-MM-DD.md)
            if "T" not in f.stem:
                continue
            log = self._parse_daily_log(f)
            if log:
                results.append(log)
        return results

    def write_daily_log(self, log: DailyLog) -> Path:
        """Write a daily log to disk. Uses timestamp + slug for filename.

        Also updates the aggregate daily note for Obsidian.
        """
        ts = log.log_timestamp.strftime("%Y-%m-%dT%H-%M")
        slug = log.slug or self._slugify(log.question)[:40]
        filename = f"{ts}-{slug}.md"
        path = self._data_dir / "logs" / filename
        path.write_text(log.to_markdown())
        # Update the aggregate daily note for Obsidian
        self.write_daily_note(log.log_timestamp.date())
        return path

    def write_daily_note(self, d: date) -> Path:
        """Write or update an aggregate daily note for Obsidian.

        Creates a `logs/YYYY-MM-DD.md` file that links to all individual
        logs for that date using Obsidian wikilinks.
        """
        logs = self.find_daily_logs_by_date(d)
        date_str = d.isoformat()
        frontmatter = format_frontmatter({"date": date_str})

        lines = [frontmatter, f"# Daily Note — {date_str}\n"]
        for log in logs:
            log_slug = log.slug or self._slugify(log.question)[:40]
            ts = log.log_timestamp.strftime("%Y-%m-%dT%H-%M")
            link = f"{ts}-{log_slug}"
            lines.append(f"## {log.question}\n")
            lines.append(f"![[{link}]]\n")

        path = self._data_dir / "logs" / f"{date_str}.md"
        path.write_text("\n".join(lines))
        return path

    def sync_obsidian_vault(self) -> None:
        """Regenerate all daily notes and Obsidian config."""
        generate_obsidian_config(self._data_dir)
        # Collect all unique dates from daily logs
        logs_dir = self._data_dir / "logs"
        if not logs_dir.exists():
            return
        dates: set[date] = set()
        for md_file in logs_dir.glob("*.md"):
            # Skip aggregate daily notes (YYYY-MM-DD.md without T)
            if re.match(r"\d{4}-\d{2}-\d{2}\.md$", md_file.name):
                continue
            stem = md_file.stem
            # Extract date from timestamp format: YYYY-MM-DDTHH-MM-slug
            date_match = re.match(r"(\d{4}-\d{2}-\d{2})T", stem)
            if date_match:
                try:
                    dates.add(date.fromisoformat(date_match.group(1)))
                except ValueError:
                    continue
        for d in sorted(dates):
            self.write_daily_note(d)

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

        metadata, _ = parse_frontmatter(text)
        if not metadata:
            return None

        question = metadata.get("question", "")
        topic = QuestionTopic.GENERAL
        if "topic" in metadata:
            try:
                topic = QuestionTopic(metadata["topic"])
            except ValueError:
                pass  # Unknown topic value — keep default GENERAL
        rationale = metadata.get("rationale", "")

        if not question:
            return None
        return Question(text=question, topic=topic, rationale=rationale)

    def write_pending_question(self, question: Question) -> None:
        """Persist a generated question so it survives between commands."""
        path = self._data_dir / "pending_question.md"
        frontmatter = format_frontmatter(
            {
                "question": question.text,
                "topic": question.topic.value,
                "rationale": question.rationale,
            }
        )
        path.write_text(f"{frontmatter}\n# Pending Question\n")

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
                    pass  # Malformed date — leave last_updated as None
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
        """Parse a knowledge entry from markdown with YAML frontmatter."""
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

        metadata, body = parse_frontmatter(text)
        if not metadata:
            raise ValueError(f"Knowledge entry missing frontmatter: {path}")

        title = metadata.get("title", path.stem.replace("-", " ").replace("_", " ").title())
        topic_str = metadata.get("topic", topic_name)
        try:
            topic = QuestionTopic(topic_str)
        except ValueError:
            topic = topic_reverse.get(topic_str, QuestionTopic.GENERAL)
        source = metadata.get("source", "import")
        created_at = None
        date_str = metadata.get("date")
        if date_str:
            created_at = date.fromisoformat(str(date_str))
        raw_tags = metadata.get("tags", [])
        tags = raw_tags if isinstance(raw_tags, list) else [raw_tags]
        content = body.strip()
        return KnowledgeEntry(
            title=title,
            content=content,
            topic=topic,
            source=source,
            created_at=created_at,
            tags=tags,
        )

    def _format_knowledge_entry(self, entry: KnowledgeEntry) -> str:
        """Format a knowledge entry as markdown with Obsidian-compatible frontmatter."""
        frontmatter = format_frontmatter(
            {
                "title": entry.title,
                "topic": entry.topic.value,
                "source": entry.source,
                "date": entry.created_at.isoformat() if entry.created_at else None,
                "tags": entry.tags if entry.tags else None,
            }
        )
        lines = [frontmatter, f"# {entry.title}\n", entry.content]
        return "\n".join(lines)

    def _parse_daily_log(self, path: Path) -> DailyLog:
        """Parse a daily log from markdown with YAML frontmatter."""
        text = path.read_text()

        # Strip frontmatter if present
        metadata, body = parse_frontmatter(text)

        # Parse timestamp from title: "# Daily Log — 2026-06-06 14:30"
        log_timestamp = datetime.now()
        if metadata and "date" in metadata:
            # Use frontmatter date, default to midnight if no time
            date_str = str(metadata["date"])
            log_timestamp = datetime.strptime(date_str, "%Y-%m-%d")

        for line in body.split("\n"):
            if line.startswith("# ") and "—" in line:
                ts_str = line.split("—")[1].strip()
                try:
                    log_timestamp = datetime.strptime(ts_str, "%Y-%m-%d %H:%M")
                except ValueError:
                    try:
                        log_timestamp = datetime.strptime(ts_str, "%Y-%m-%d")
                    except ValueError:
                        pass  # Neither format matched — keep frontmatter-derived timestamp
                break

        # Parse slug from filename: "2026-06-06T14-30-skill-testing.md"
        # Also check frontmatter for slug
        slug = ""
        if metadata and "slug" in metadata:
            slug = str(metadata["slug"])
        else:
            stem = path.stem
            slug_match = re.match(r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-(.+)", stem)
            if slug_match:
                slug = slug_match.group(1)

        # Parse question line: **Question** (topic): text
        question = ""
        question_topic = QuestionTopic.GENERAL
        for line in body.split("\n"):
            if line.startswith("**Question**"):
                topic_match = re.search(r"\((\w+)\)", line)
                if topic_match:
                    try:
                        question_topic = QuestionTopic(topic_match.group(1))
                    except ValueError:
                        pass  # Unknown topic — keep default GENERAL
                colon_idx = line.find(":")
                if colon_idx >= 0:
                    question = line[colon_idx + 1 :].strip()
                break

        # Parse rationale
        rationale = ""
        for line in body.split("\n"):
            if line.startswith("**Rationale**"):
                colon_idx = line.find(":")
                if colon_idx >= 0:
                    rationale = line[colon_idx + 1 :].strip()
                break

        # Parse response and recorded knowledge sections
        response = ""
        recorded_entry = ""
        sections = body.split("## ")
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
