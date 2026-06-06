"""Tests for CLI commands."""

from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from kbb_cli.app import app

runner = CliRunner()


class TestInitCommand:
    def test_init_creates_data_dir(self, tmp_path):
        result = runner.invoke(app, ["init"], env={"KBB_DATA_DIR": str(tmp_path / "test_data")})
        # Init should succeed (directories created)
        assert result.exit_code == 0
        assert "initialized" in result.output.lower() or "Knowledge" in result.output


class TestStatusCommand:
    def test_status_empty(self, tmp_path):
        result = runner.invoke(app, ["status"], env={"KBB_DATA_DIR": str(tmp_path / "data")})
        assert result.exit_code == 0
        assert "Knowledge Base Status" in result.output
        assert "Not configured" in result.output


class TestProfileShow:
    def test_profile_show_no_profile(self, tmp_path):
        result = runner.invoke(app, ["profile-show"], env={"KBB_DATA_DIR": str(tmp_path / "data")})
        assert result.exit_code == 0
        # Should show a message about no profile
        assert "No profile" in result.output or "profile" in result.output.lower()


class TestDailyLog:
    def test_daily_log_no_log(self, tmp_path):
        result = runner.invoke(app, ["daily-log"], env={"KBB_DATA_DIR": str(tmp_path / "data")})
        assert result.exit_code == 0
        assert "No log" in result.output


class TestKnowledgeList:
    def test_knowledge_list_empty(self, tmp_path):
        result = runner.invoke(app, ["knowledge-list"], env={"KBB_DATA_DIR": str(tmp_path / "data")})
        assert result.exit_code == 0
        assert "No knowledge entries" in result.output