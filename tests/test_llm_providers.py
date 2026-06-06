"""Tests for LLM abstraction layer."""

import json

import pytest

from kbb.llm.base import LLMClient, create_provider
from kbb.models import KnowledgeEntry, Question, QuestionTopic, UserProfile


class TestLLMClient:
    @pytest.mark.asyncio
    async def test_understand_profile(self, mock_llm_client):
        client, provider = mock_llm_client
        profile = await client.understand_profile("I'm a software engineer")
        assert profile["name"] == "Test User"
        assert "education" in profile
        # Verify the provider was called
        assert len(provider._calls) == 1

    @pytest.mark.asyncio
    async def test_generate_question(self, mock_llm_client):
        client, _ = mock_llm_client
        user_profile = UserProfile(
            name="Test",
            education=["BS CS"],
            work_experience=["Engineer"],
        )
        question = await client.generate_question(
            profile=user_profile,
            knowledge_entries=[],
            recent_questions=[],
        )
        assert isinstance(question, Question)
        assert question.text
        assert question.topic in list(QuestionTopic)

    @pytest.mark.asyncio
    async def test_record_response(self, mock_llm_client):
        client, _ = mock_llm_client
        user_profile = UserProfile(name="Test")
        result = await client.record_response(
            question="What testing framework?",
            response="I prefer pytest",
            profile=user_profile,
        )
        assert result  # Non-empty string

    @pytest.mark.asyncio
    async def test_understand_profile_with_custom_response(self):
        from tests.helpers import MockProvider

        custom_provider = MockProvider(
            responses={
                "profile": json.dumps(
                    {
                        "name": "Custom User",
                        "education": ["PhD Physics"],
                        "work_experience": ["Researcher"],
                        "life_experience": ["Traveled the world"],
                        "interests": ["Quantum mechanics"],
                    }
                )
            }
        )
        client = LLMClient(custom_provider)
        result = await client.understand_profile("Custom profile text")
        assert result["name"] == "Custom User"
        assert "PhD Physics" in result["education"]


class TestParseJsonResponse:
    def test_plain_json(self):
        text = '{"name": "Test", "education": ["BS"]}'
        result = LLMClient._parse_json_response(text)
        assert result["name"] == "Test"

    def test_json_with_code_fence(self):
        text = '```json\n{"name": "Test", "education": ["BS"]}\n```'
        result = LLMClient._parse_json_response(text)
        assert result["name"] == "Test"

    def test_json_embedded_in_text(self):
        text = 'Here is the result:\n{"name": "Test", "education": ["BS"]}\nThat is all.'
        result = LLMClient._parse_json_response(text)
        assert result["name"] == "Test"

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="Failed to parse"):
            LLMClient._parse_json_response("not json at all")

    def test_truncated_json_auto_closed(self):
        """Truncated JSON with missing closing braces should be auto-closed."""
        truncated = '{"name": "Test", "education": ["BS"'
        result = LLMClient._parse_json_response(truncated)
        assert result["name"] == "Test"
        assert result["education"] == ["BS"]

    def test_truncated_json_missing_brace_and_bracket(self):
        """Truncated JSON missing both } and ] should be auto-closed."""
        truncated = '{"name": "Test", "items": ["a", "b"'
        result = LLMClient._parse_json_response(truncated)
        assert result["name"] == "Test"
        assert result["items"] == ["a", "b"]

    def test_nested_truncated_json(self):
        """Nested truncated JSON should be auto-closed."""
        truncated = '{"name": "Test", "data": {"key": "value"'
        result = LLMClient._parse_json_response(truncated)
        assert result["name"] == "Test"
        assert result["data"]["key"] == "value"


class TestTryCloseJson:
    def test_balanced_json_returns_none(self):
        assert LLMClient._try_close_json('{"name": "Test"}') is None

    def test_missing_closing_brace(self):
        result = LLMClient._try_close_json('{"name": "Test"')
        assert result == '{"name": "Test"}'

    def test_missing_closing_bracket_and_brace(self):
        result = LLMClient._try_close_json('{"items": ["a"')
        assert result == '{"items": ["a"]}'

    def test_nested_missing_both(self):
        result = LLMClient._try_close_json('{"data": {"key": "val"')
        assert result == '{"data": {"key": "val"}}'

    def test_string_with_braces_ignored(self):
        result = LLMClient._try_close_json('{"text": "hello {world}"')
        assert result == '{"text": "hello {world}"}'

    def test_escaped_quotes_in_string(self):
        result = LLMClient._try_close_json('{"text": "he said \\"hi\\""')
        assert result == '{"text": "he said \\"hi\\""}'


class TestCreateProvider:
    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            create_provider("unknown_provider", api_key="test", model="test")

    def test_anthropic_provider_name(self):
        try:
            provider = create_provider("anthropic", api_key="test-key", model="claude-sonnet-4-20250514")
            assert "anthropic" in provider.name
        except ImportError:
            pytest.skip("anthropic package not installed")

    def test_openai_provider_name(self):
        try:
            provider = create_provider("openai", api_key="test-key", model="gpt-4o")
            assert "openai" in provider.name
        except ImportError:
            pytest.skip("openai package not installed")

    def test_ollama_provider_name(self):
        try:
            provider = create_provider("ollama", api_key="ollama", model="llama3")
            assert "ollama" in provider.name
        except ImportError:
            pytest.skip("ollama package not installed")

    def test_ollama_with_custom_host(self):
        try:
            provider = create_provider(
                "ollama", api_key="ollama", model="llama3",
                base_url="http://my-server:11434",
            )
            assert "my-server" in provider.name
        except ImportError:
            pytest.skip("ollama package not installed")

    def test_ollama_strips_v1_suffix(self):
        """Old configs with /v1 suffix should be handled gracefully."""
        try:
            provider = create_provider(
                "ollama", api_key="ollama", model="llama3",
                base_url="http://localhost:11434/v1",
            )
            assert "localhost" in provider.name
        except ImportError:
            pytest.skip("ollama package not installed")

    def test_openai_with_custom_base_url(self):
        try:
            provider = create_provider(
                "openai", api_key="test-key", model="gpt-4o",
                base_url="https://my-proxy.example.com/v1",
            )
            assert "my-proxy" in provider.name
        except ImportError:
            pytest.skip("openai package not installed")