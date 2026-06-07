"""Obsidian vault integration helpers.

Provides YAML frontmatter formatting/parsing and vault configuration
generation so that a KBB data directory works as a native Obsidian vault.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml


def format_frontmatter(metadata: dict) -> str:
    """Format a dict as YAML frontmatter for Obsidian-compatible markdown.

    Returns a string like:
        ---
        title: my-entry
        topic: skill
        date: 2026-06-06
        tags: [daily-log, skill]
        ---

    Falsy values that are **omitted**: ``None``, empty string ``""``,
    and empty list ``[]``.  All other values are kept — including ``0``,
    ``False``, and non-empty strings/collections.  This means ``date: 0``
    would be written, but ``slug: None`` would not.
    """
    filtered = {k: v for k, v in metadata.items() if v is not None and v != "" and v != []}
    if not filtered:
        return ""
    return f"---\n{yaml.dump(filtered, default_flow_style=False).strip()}\n---\n"


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from a markdown string.

    Returns (metadata_dict, body_text).
    If no frontmatter is found, returns ({}, text).
    """
    text = text.strip()
    if not text.startswith("---"):
        return {}, text

    # Find closing ---
    rest = text[3:].lstrip("\n")
    end = rest.find("\n---")
    if end == -1:
        return {}, text

    yaml_block = rest[:end]
    body = rest[end + 4 :].lstrip("\n")

    try:
        metadata = yaml.safe_load(yaml_block) or {}
    except yaml.YAMLError:
        return {}, text

    if not isinstance(metadata, dict):
        return {}, text

    return metadata, body


def generate_obsidian_config(data_dir: Path) -> None:
    """Write Obsidian vault configuration files to the data directory.

    Creates .obsidian/ with sensible defaults for daily notes,
    templates, and other settings.
    """
    obsidian_dir = data_dir / ".obsidian"
    obsidian_dir.mkdir(parents=True, exist_ok=True)

    # Main app config
    app_config = {
        "legacyEditor": False,
        "promptDelete": False,
        "showUnsupportedFiles": True,
        "attachmentFolderPath": "attachments",
    }
    (obsidian_dir / "app.json").write_text(json.dumps(app_config, indent=2) + "\n")

    # Daily notes config
    daily_notes_config = {
        "folder": "logs",
        "template": None,
        "format": "YYYY-MM-DD",
        "extension": ".md",
    }
    (obsidian_dir / "daily-notes.json").write_text(json.dumps(daily_notes_config, indent=2) + "\n")
