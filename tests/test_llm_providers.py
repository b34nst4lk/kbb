"""Tests for LLM abstraction layer."""

import json

import pytest

from kbb.llm.base import LLMClient, create_provider
from kbb.llm.schemas import ProfileSchema, QuestionSchema, PROFILE_JSON_SCHEMA, QUESTION_JSON_SCHEMA
from kbb.models import Question, QuestionTopic, UserProfile


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

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="provider should guarantee valid JSON"):
            LLMClient._parse_json_response("not json at all")

    def test_whitespace_stripped(self):
        text = '  \n  {"name": "Test", "education": ["BS"]}  \n  '
        result = LLMClient._parse_json_response(text)
        assert result["name"] == "Test"


class TestCreateProvider:
    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            create_provider("unknown_provider", api_key="test", model="test")

    def test_anthropic_provider_name(self):
        try:
            provider = create_provider(
                "anthropic", api_key="test-key", model="claude-sonnet-4-20250514"
            )
            assert "anthropic" in provider.name
        except ImportError:
            pytest.skip("anthropic package not installed")  # ty: ignore[too-many-positional-arguments]

    def test_openai_provider_name(self):
        try:
            provider = create_provider("openai", api_key="test-key", model="gpt-4o")
            assert "openai" in provider.name
        except ImportError:
            pytest.skip("openai package not installed")  # ty: ignore[too-many-positional-arguments]

    def test_ollama_provider_name(self):
        try:
            provider = create_provider("ollama", api_key="ollama", model="llama3")
            assert "ollama" in provider.name
        except ImportError:
            pytest.skip("ollama package not installed")  # ty: ignore[too-many-positional-arguments]

    def test_ollama_with_custom_host(self):
        try:
            provider = create_provider(
                "ollama",
                api_key="ollama",
                model="llama3",
                base_url="http://my-server:11434",
            )
            assert "my-server" in provider.name
        except ImportError:
            pytest.skip("ollama package not installed")  # ty: ignore[too-many-positional-arguments]

    def test_ollama_strips_v1_suffix(self):
        """Old configs with /v1 suffix should be handled gracefully."""
        try:
            provider = create_provider(
                "ollama",
                api_key="ollama",
                model="llama3",
                base_url="http://localhost:11434/v1",
            )
            assert "localhost" in provider.name
        except ImportError:
            pytest.skip("ollama package not installed")  # ty: ignore[too-many-positional-arguments]

    def test_openai_with_custom_base_url(self):
        try:
            provider = create_provider(
                "openai",
                api_key="test-key",
                model="gpt-4o",
                base_url="https://my-proxy.example.com/v1",
            )
            assert "my-proxy" in provider.name
        except ImportError:
            pytest.skip("openai package not installed")  # ty: ignore[too-many-positional-arguments]


class TestSchemas:
    """Tests for Pydantic schemas and strict JSON schema generation."""

    def test_profile_schema_validates_valid_data(self):
        data = {
            "name": "Jane",
            "education": ["BS CS"],
            "work_experience": ["Engineer"],
            "life_experience": ["Lived abroad"],
            "interests": ["Python"],
        }
        profile = ProfileSchema.model_validate(data)
        assert profile.name == "Jane"
        assert profile.education == ["BS CS"]

    def test_profile_schema_fills_defaults(self):
        profile = ProfileSchema.model_validate({})
        assert profile.name == ""
        assert profile.education == []

    def test_question_schema_validates_valid_data(self):
        data = {"text": "What is your approach?", "topic": "skill", "rationale": "Test"}
        question = QuestionSchema.model_validate(data)
        assert question.text == "What is your approach?"
        assert question.topic == QuestionTopic.SKILL

    def test_question_schema_defaults_topic_and_rationale(self):
        data = {"text": "What is your approach?"}
        question = QuestionSchema.model_validate(data)
        assert question.topic == QuestionTopic.GENERAL
        assert question.rationale == ""

    def test_profile_json_schema_has_strict_properties(self):
        assert PROFILE_JSON_SCHEMA["additionalProperties"] is False
        assert set(PROFILE_JSON_SCHEMA["required"]) == {
            "name",
            "education",
            "work_experience",
            "life_experience",
            "interests",
        }

    def test_question_json_schema_has_strict_properties(self):
        assert QUESTION_JSON_SCHEMA["additionalProperties"] is False
        assert set(QUESTION_JSON_SCHEMA["required"]) == {"text", "topic", "rationale"}
        # Topic should have enum values inlined (no $ref)
        topic_prop = QUESTION_JSON_SCHEMA["properties"]["topic"]
        assert "enum" in topic_prop
        assert "$ref" not in topic_prop

    def test_profile_json_schema_no_defaults(self):
        """OpenAI strict mode doesn't allow 'default' in properties."""
        for prop in PROFILE_JSON_SCHEMA["properties"].values():
            assert "default" not in prop

    def test_question_json_schema_no_defaults(self):
        """OpenAI strict mode doesn't allow 'default' in properties."""
        for prop in QUESTION_JSON_SCHEMA["properties"].values():
            assert "default" not in prop
