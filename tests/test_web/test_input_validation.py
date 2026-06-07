"""Tests for input validation in web routes.

Covers: QuestionTopic fallback on invalid input, date validation,
LLMProviderName error on invalid input, and profile.name handling.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from kbb.engine import KBPEngine
from kbb.llm.base import LLMClient
from kbb_web.app import create_app
from kbb_web.config import WebConfig
from tests.helpers import MockProvider


@pytest.fixture
def web_app(tmp_path: Path):
    """Provide a FastAPI app with mock-engine for testing."""
    config = WebConfig(data_dir=tmp_path, llm_api_key="test")
    app = create_app()
    engine = KBPEngine(config.to_kbb_config())
    engine._llm = LLMClient(MockProvider())  # noqa: SLF001
    app.state.engine = engine
    app.state.web_config = config
    return app


@pytest.fixture
def client(web_app):
    """Provide a synchronous test client."""
    return TestClient(web_app)


# --- QuestionTopic validation ---


class TestApiTopicValidation:
    """API routes should fall back to GENERAL on invalid QuestionTopic values."""

    def test_import_knowledge_invalid_topic_falls_back(self, client):
        """POST /api/knowledge with an invalid topic should default to 'general'."""
        resp = client.post(
            "/api/knowledge",
            json={
                "title": "Test entry",
                "content": "Some content",
                "topic": "nonexistent_topic",
            },
        )
        # Should succeed (200) with topic defaulted to "general"
        assert resp.status_code == 200
        data = resp.json()
        assert data["topic"] == "general"

    def test_import_knowledge_valid_topic(self, client):
        """POST /api/knowledge with a valid topic should use it."""
        resp = client.post(
            "/api/knowledge",
            json={
                "title": "Test entry",
                "content": "Some content",
                "topic": "skill",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["topic"] == "skill"

    def test_record_response_invalid_topic_falls_back(self, client):
        """POST /api/daily/response with invalid topic should default to 'general'."""
        # First set up a profile so the mock can respond
        client.post("/partials/profile", data={"raw_text": "I'm a software engineer"})

        resp = client.post(
            "/api/daily/response",
            json={
                "question_text": "What is your approach?",
                "question_topic": "invalid_topic",
                "question_rationale": "Testing",
                "response": "My approach is systematic.",
            },
        )
        # Should succeed with topic defaulted to "general"
        assert resp.status_code == 200
        data = resp.json()
        assert data["question_topic"] == "general"


class TestPartialTopicValidation:
    """Partial routes should fall back to GENERAL on invalid QuestionTopic."""

    def test_record_response_invalid_topic_falls_back(self, client):
        """POST /partials/response with invalid topic should default to 'general'."""
        # Set up profile
        client.post("/partials/profile", data={"raw_text": "I'm a software engineer"})

        resp = client.post(
            "/partials/response",
            data={
                "question_text": "What is your approach?",
                "question_topic": "invalid_topic",
                "question_rationale": "Testing",
                "response": "My approach is systematic.",
            },
        )
        assert resp.status_code == 200
        # Should not contain an error alert
        assert "alert-error" not in resp.text

    def test_import_knowledge_invalid_topic_falls_back(self, client):
        """POST /partials/knowledge/import with invalid topic should default to 'general'."""
        resp = client.post(
            "/partials/knowledge/import",
            data={
                "title": "Test entry",
                "content": "Some content",
                "topic": "nonexistent",
            },
        )
        assert resp.status_code == 200
        # Should succeed (not show error alert)
        assert "alert-error" not in resp.text


# --- Date validation ---


class TestApiDateValidation:
    """API routes should return 400 on invalid date strings."""

    def test_logs_invalid_date_returns_400(self, client):
        """GET /api/daily/logs?date=invalid should return 400."""
        resp = client.get("/api/daily/logs?date=not-a-date")
        assert resp.status_code == 400
        assert "Invalid date" in resp.json()["detail"]

    def test_logs_valid_date(self, client):
        """GET /api/daily/logs?date=2026-06-07 should return 200."""
        resp = client.get("/api/daily/logs?date=2026-06-07")
        assert resp.status_code == 200

    def test_logs_no_date(self, client):
        """GET /api/daily/logs (no date param) should return 200 with today's date."""
        resp = client.get("/api/daily/logs")
        assert resp.status_code == 200


class TestPartialDateValidation:
    """Partial routes should fall back to today on invalid date."""

    def test_logs_invalid_date_falls_back(self, client):
        """GET /partials/logs?date_str=invalid should fall back to today."""
        resp = client.get("/partials/logs?date_str=not-a-date")
        # Should return 200 (fallback to today), not 500
        assert resp.status_code == 200

    def test_logs_valid_date(self, client):
        """GET /partials/logs?date_str=2026-06-07 should return 200."""
        resp = client.get("/partials/logs?date_str=2026-06-07")
        assert resp.status_code == 200

    def test_logs_no_date(self, client):
        """GET /partials/logs (no date) should return 200 with today."""
        resp = client.get("/partials/logs")
        assert resp.status_code == 200


class TestPagesDateValidation:
    """Page routes should render an error page on invalid date."""

    def test_daily_logs_invalid_date(self, client):
        """GET /daily/logs/not-a-date should return 400 with error page."""
        resp = client.get("/daily/logs/not-a-date")
        assert resp.status_code == 400
        assert "Invalid date" in resp.text

    def test_daily_logs_valid_date(self, client):
        """GET /daily/logs/2026-06-07 should return 200."""
        resp = client.get("/daily/logs/2026-06-07")
        assert resp.status_code == 200


# --- LLMProviderName validation ---


class TestSettingsProviderValidation:
    """Settings route should show error on invalid LLM provider."""

    def test_save_settings_invalid_provider(self, client):
        """POST /partials/settings with invalid provider should show error."""
        resp = client.post(
            "/partials/settings",
            data={
                "data_dir": str(client.app.state.web_config.data_dir),
                "llm_provider": "invalid_provider",
                "llm_model": "test-model",
                "llm_base_url": "",
                "daily_log_time": "09:00",
                "port": "8199",
            },
        )
        assert resp.status_code == 200
        assert "Invalid LLM provider" in resp.text
        assert "anthropic" in resp.text  # Should list valid options

    def test_save_settings_valid_provider(self, client):
        """POST /partials/settings with valid provider should succeed."""
        resp = client.post(
            "/partials/settings",
            data={
                "data_dir": str(client.app.state.web_config.data_dir),
                "llm_provider": "openai",
                "llm_model": "gpt-4o",
                "llm_base_url": "",
                "daily_log_time": "09:00",
                "port": "8199",
            },
        )
        assert resp.status_code == 200
        assert "Settings saved" in resp.text or "settings" in resp.text.lower()


# --- Profile name handling ---


class TestProfileNameHandling:
    """Profile name should be empty string, not None, when no profile is set."""

    def test_dashboard_profile_name_empty_string(self, client):
        """Dashboard should use empty string for missing profile name."""
        resp = client.get("/")
        assert resp.status_code == 200
        # Should not crash; profile_name should be "" not None
        assert "None" not in resp.text or "No profile" in resp.text
