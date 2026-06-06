"""Tests for JSON API routes."""

from __future__ import annotations

import pytest


class TestApiStatus:
    def test_status_empty(self, client):
        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["profile_name"] == ""
        assert data["knowledge_count"] == 0
        assert data["log_count"] == 0
        assert data["pending_question"] is None


class TestApiProfile:
    def test_get_profile_empty(self, client):
        resp = client.get("/api/profile")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == ""
        assert data["education"] == []
        assert data["raw_markdown"] == ""


class TestApiKnowledge:
    def test_list_knowledge_empty(self, client):
        resp = client.get("/api/knowledge")
        assert resp.status_code == 200
        assert resp.json() == []


class TestApiDailyLogs:
    def test_list_logs_empty(self, client):
        resp = client.get("/api/daily/logs")
        assert resp.status_code == 200
        assert resp.json() == []
