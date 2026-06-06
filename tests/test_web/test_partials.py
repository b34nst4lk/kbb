"""Tests for HTMX partial routes."""

from __future__ import annotations

import pytest


class TestProfileEditorPartial:
    def test_profile_editor_returns_fragment(self, client):
        resp = client.get("/partials/profile-editor")
        assert resp.status_code == 200
        assert "Edit Profile" in resp.text
        assert 'name="raw_text"' in resp.text

    def test_profile_editor_has_textarea(self, client):
        resp = client.get("/partials/profile-editor")
        assert "<textarea" in resp.text

    def test_profile_editor_has_cancel_button(self, client):
        resp = client.get("/partials/profile-editor")
        assert "Cancel" in resp.text
        # Cancel should load the profile view partial
        assert "/partials/profile-view" in resp.text


class TestProfileViewPartial:
    def test_profile_view_empty(self, client):
        resp = client.get("/partials/profile-view")
        assert resp.status_code == 200
        assert "No profile yet" in resp.text

    def test_profile_view_shows_edit_button_when_profile_exists(self, client):
        # First save a profile via the mock
        client.post("/partials/profile", data={"raw_text": "I'm a software engineer"})
        resp = client.get("/partials/profile-view")
        assert resp.status_code == 200
        assert "Edit Profile" in resp.text


class TestProfileSave:
    def test_save_profile_success(self, client):
        resp = client.post("/partials/profile", data={"raw_text": "I'm a software engineer"})
        assert resp.status_code == 200
        assert "Profile saved" in resp.text

    def test_save_profile_shows_profile_after_save(self, client):
        resp = client.post("/partials/profile", data={"raw_text": "I'm a software engineer"})
        assert resp.status_code == 200
        # Should show the profile view, not the editor
        assert "Edit Profile" in resp.text
        # Should NOT show the textarea anymore
        assert 'name="raw_text"' not in resp.text


class TestQuestionPartial:
    def test_generate_question_no_profile_shows_error(self, client):
        resp = client.get("/partials/question")
        assert resp.status_code == 200
        # Should show an error about missing profile, not a 500
        assert "No profile found" in resp.text

    def test_generate_question_with_profile(self, client):
        # First set up a profile
        client.post("/partials/profile", data={"raw_text": "I'm a software engineer"})
        resp = client.get("/partials/question")
        assert resp.status_code == 200
        # Should show a question (mock provider returns one)
        assert "question" in resp.text.lower() or "Today" in resp.text


class TestKnowledgeListPartial:
    def test_knowledge_list_empty(self, client):
        resp = client.get("/partials/knowledge")
        assert resp.status_code == 200
        assert "No knowledge entries found" in resp.text


class TestLogsPartial:
    def test_logs_by_date_empty(self, client):
        resp = client.get("/partials/logs")
        assert resp.status_code == 200
        assert "No logs found" in resp.text


class TestErrorPartial:
    """Test that error partials render correctly."""

    def test_error_alert_renders(self):
        from jinja2 import Environment, FileSystemLoader
        from pathlib import Path
        import kbb_web

        templates_dir = Path(kbb_web.__file__).parent / "templates"
        env = Environment(loader=FileSystemLoader(str(templates_dir)))
        template = env.get_template("partials/error_alert.html")
        html = template.render(error="Test error")
        assert "Test error" in html
        assert "alert-error" in html


class TestGlobalExceptionHandler:
    """Test that HTMX requests get 200 errors (so HTMX performs the swap)."""

    def test_htmx_error_returns_200(self, web_app):
        from starlette.testclient import TestClient
        # Force an error by accessing a route that will fail
        client = TestClient(web_app)
        # Generate question without a profile — should return error with 200 for HTMX
        resp = client.get("/partials/question", headers={"HX-Request": "true"})
        assert resp.status_code == 200
        assert "No profile found" in resp.text