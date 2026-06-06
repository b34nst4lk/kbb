"""Pydantic form schemas for the web adapter.

Used for request validation in form and API endpoints.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from kbb.models import QuestionTopic


class ProfileForm(BaseModel):
    raw_text: str = Field(min_length=1)


class ResponseForm(BaseModel):
    question_text: str
    question_topic: QuestionTopic
    question_rationale: str
    response: str = Field(min_length=1)


class KnowledgeImportForm(BaseModel):
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    topic: QuestionTopic = QuestionTopic.GENERAL


class SettingsForm(BaseModel):
    llm_provider: str = "anthropic"
    llm_model: str = "claude-sonnet-4-20250514"
    llm_base_url: str = ""
    daily_log_time: str = "09:00"
    host: str = "127.0.0.1"
    port: int = 8199
