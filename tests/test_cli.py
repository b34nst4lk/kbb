"""Tests for CLI commands."""

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
        result = runner.invoke(
            app, ["knowledge-list"], env={"KBB_DATA_DIR": str(tmp_path / "data")}
        )
        assert result.exit_code == 0
        assert "No knowledge entries" in result.output


class TestResolveApiKey:
    """Tests for _resolve_api_key provider-aware fallback."""

    def test_explicit_key_takes_priority(self, monkeypatch):
        from kbb.models import LLMProviderName

        from kbb_cli.app import _resolve_api_key

        monkeypatch.setenv("ANTHROPIC_API_KEY", "anth-key")
        monkeypatch.setenv("KBB_API_KEY", "generic-key")
        assert _resolve_api_key(LLMProviderName.ANTHROPIC, "explicit-key") == "explicit-key"

    def test_anthropic_provider_uses_anthropic_env(self, monkeypatch):
        from kbb.models import LLMProviderName

        from kbb_cli.app import _resolve_api_key

        monkeypatch.delenv("KBB_API_KEY", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "anth-key")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        assert _resolve_api_key(LLMProviderName.ANTHROPIC) == "anth-key"

    def test_openai_provider_uses_openai_env(self, monkeypatch):
        from kbb.models import LLMProviderName

        from kbb_cli.app import _resolve_api_key

        monkeypatch.delenv("KBB_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "oai-key")
        assert _resolve_api_key(LLMProviderName.OPENAI) == "oai-key"

    def test_wrong_provider_env_not_used(self, monkeypatch):
        """ANTHROPIC_API_KEY should NOT be picked up when provider is openai."""
        from kbb.models import LLMProviderName

        from kbb_cli.app import _resolve_api_key

        monkeypatch.delenv("KBB_API_KEY", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "anth-key")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        # No KBB_API_KEY, no OPENAI_API_KEY → empty string
        assert _resolve_api_key(LLMProviderName.OPENAI) == ""

    def test_kbb_api_key_fallback(self, monkeypatch):
        """KBB_API_KEY is used when provider-specific env is not set."""
        from kbb.models import LLMProviderName

        from kbb_cli.app import _resolve_api_key

        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("KBB_API_KEY", "generic-key")
        assert _resolve_api_key(LLMProviderName.ANTHROPIC) == "generic-key"

    def test_ollama_provider_no_env_required(self, monkeypatch):
        """Ollama doesn't need an API key."""
        from kbb.models import LLMProviderName

        from kbb_cli.app import _resolve_api_key

        monkeypatch.delenv("KBB_API_KEY", raising=False)
        assert _resolve_api_key(LLMProviderName.OLLAMA) == ""
