"""Tests for full-page routes."""

from __future__ import annotations


class TestDashboard:
    def test_dashboard_returns_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Knowledge Base Builder" in resp.text
        assert "nav-brand" in resp.text

    def test_dashboard_shows_empty_state(self, client):
        resp = client.get("/")
        assert "Set Up Profile" in resp.text or "Get Started" in resp.text

    def test_dashboard_has_nav_links(self, client):
        resp = client.get("/")
        assert 'href="/daily"' in resp.text
        assert 'href="/knowledge"' in resp.text
        assert 'href="/profile"' in resp.text
        assert 'href="/settings"' in resp.text


class TestProfilePage:
    def test_profile_page_no_profile(self, client):
        resp = client.get("/profile")
        assert resp.status_code == 200
        assert "No profile yet" in resp.text

    def test_profile_page_has_edit_button(self, client):
        resp = client.get("/profile")
        assert "Set Up Profile" in resp.text or "Edit Profile" in resp.text


class TestDailyPage:
    def test_daily_page_renders(self, client):
        resp = client.get("/daily")
        assert resp.status_code == 200
        assert "Daily Knowledge Extraction" in resp.text

    def test_daily_page_has_generate_button(self, client):
        resp = client.get("/daily")
        assert "Generate Question" in resp.text


class TestKnowledgePage:
    def test_knowledge_page_empty(self, client):
        resp = client.get("/knowledge")
        assert resp.status_code == 200
        assert "No knowledge entries yet" in resp.text

    def test_knowledge_import_page_renders(self, client):
        resp = client.get("/knowledge/import")
        assert resp.status_code == 200
        assert "Import Knowledge" in resp.text


class TestSettingsPage:
    def test_settings_page_renders(self, client):
        resp = client.get("/settings")
        assert resp.status_code == 200
        assert "Settings" in resp.text

    def test_settings_has_provider_options(self, client):
        resp = client.get("/settings")
        assert "anthropic" in resp.text
        assert "openai" in resp.text
        assert "ollama" in resp.text


class TestDailyLogsPage:
    def test_daily_logs_empty(self, client):
        resp = client.get("/daily/logs")
        assert resp.status_code == 200
        assert "No daily logs yet" in resp.text
