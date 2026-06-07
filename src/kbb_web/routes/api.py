"""JSON API routes for the web adapter.

Provides programmatic access to the engine's functionality.
Useful for scripting, integrations, and future SPA migration.
"""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from kbb.engine import KBPEngine
from kbb.transcribe import SUPPORTED_AUDIO_EXTENSIONS
from kbb.models import Question, QuestionTopic
from kbb_web.dependencies import get_engine

router = APIRouter()


# --- Response schemas ---


class ProfileResponse(BaseModel):
    name: str = ""
    education: list[str] = []
    work_experience: list[str] = []
    life_experience: list[str] = []
    interests: list[str] = []
    raw_markdown: str = ""


class QuestionResponse(BaseModel):
    text: str
    topic: str
    rationale: str


class DailyLogResponse(BaseModel):
    log_timestamp: str
    question: str
    question_topic: str
    question_rationale: str
    response: str
    recorded_entry: str
    slug: str = ""


class KnowledgeEntryResponse(BaseModel):
    title: str
    content: str
    topic: str
    source: str
    created_at: str = ""
    tags: list[str] = []


class StatusResponse(BaseModel):
    profile_name: str = ""
    knowledge_count: int = 0
    log_count: int = 0
    pending_question: QuestionResponse | None = None


# --- Request schemas ---


class ProfileCreateRequest(BaseModel):
    raw_text: str = Field(min_length=1)


class ResponseCreateRequest(BaseModel):
    question_text: str
    question_topic: str
    question_rationale: str
    response: str = Field(min_length=1)


class KnowledgeImportRequest(BaseModel):
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    topic: str = "general"


# --- Routes ---


@router.get("/status")
def api_status(engine: KBPEngine = Depends(get_engine)):
    profile = engine.get_profile()
    entries = engine.get_knowledge_entries()
    log_paths = engine.get_all_daily_logs()
    pending = engine.get_pending_question()

    pending_q = None
    if pending:
        pending_q = QuestionResponse(
            text=pending.text,
            topic=pending.topic.value,
            rationale=pending.rationale,
        )

    return StatusResponse(
        profile_name=profile.name or "",
        knowledge_count=len(entries),
        log_count=len(log_paths),
        pending_question=pending_q,
    )


@router.get("/profile")
def api_get_profile(engine: KBPEngine = Depends(get_engine)):
    profile = engine.get_profile()
    raw = engine.get_raw_profile()
    return ProfileResponse(
        name=profile.name or "",
        education=profile.education,
        work_experience=profile.work_experience,
        life_experience=profile.life_experience,
        interests=profile.interests,
        raw_markdown=raw,
    )


@router.post("/profile")
async def api_create_profile(body: ProfileCreateRequest, engine: KBPEngine = Depends(get_engine)):
    profile = await engine.setup_profile_from_text(body.raw_text)
    return ProfileResponse(
        name=profile.name or "",
        education=profile.education,
        work_experience=profile.work_experience,
        life_experience=profile.life_experience,
        interests=profile.interests,
        raw_markdown=engine.get_raw_profile(),
    )


@router.get("/knowledge")
def api_list_knowledge(engine: KBPEngine = Depends(get_engine)):
    entries = engine.get_knowledge_entries()
    return [
        KnowledgeEntryResponse(
            title=e.title,
            content=e.content,
            topic=e.topic.value,
            source=e.source,
            created_at=str(e.created_at) if e.created_at else "",
            tags=e.tags,
        )
        for e in entries
    ]


@router.post("/knowledge")
async def api_import_knowledge(
    body: KnowledgeImportRequest, engine: KBPEngine = Depends(get_engine)
):
    try:
        topic_enum = QuestionTopic(body.topic)
    except ValueError:
        topic_enum = QuestionTopic.GENERAL
    entry = await engine.import_knowledge_from_text(
        title=body.title,
        content=body.content,
        topic=topic_enum,
    )
    return KnowledgeEntryResponse(
        title=entry.title,
        content=entry.content,
        topic=entry.topic.value,
        source=entry.source,
        created_at=str(entry.created_at) if entry.created_at else "",
        tags=entry.tags,
    )


@router.get("/daily/question")
async def api_get_question(engine: KBPEngine = Depends(get_engine)):
    pending = engine.get_pending_question()
    if pending:
        question = pending
    else:
        question = await engine.generate_daily_question()
    return QuestionResponse(
        text=question.text,
        topic=question.topic.value,
        rationale=question.rationale,
    )


@router.post("/daily/response")
async def api_record_response(body: ResponseCreateRequest, engine: KBPEngine = Depends(get_engine)):
    try:
        topic_enum = QuestionTopic(body.question_topic)
    except ValueError:
        topic_enum = QuestionTopic.GENERAL
    question = Question(
        text=body.question_text,
        topic=topic_enum,
        rationale=body.question_rationale,
    )
    log = await engine.record_response(question, body.response)
    return DailyLogResponse(
        log_timestamp=log.log_timestamp.isoformat(),
        question=log.question,
        question_topic=log.question_topic.value,
        question_rationale=log.question_rationale,
        response=log.response,
        recorded_entry=log.recorded_entry,
        slug=log.slug,
    )


@router.get("/daily/logs")
def api_list_logs(
    date_str: str = Query(None, alias="date"), engine: KBPEngine = Depends(get_engine)
):
    if date_str:
        try:
            d = date.fromisoformat(date_str)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {date_str}")
    else:
        d = date.today()
    logs = engine.find_daily_logs_by_date(d)
    return [
        DailyLogResponse(
            log_timestamp=log.log_timestamp.isoformat(),
            question=log.question,
            question_topic=log.question_topic.value,
            question_rationale=log.question_rationale,
            response=log.response,
            recorded_entry=log.recorded_entry,
            slug=log.slug,
        )
        for log in logs
    ]


class TranscriptionResponse(BaseModel):
    text: str
    provider: str


@router.post("/transcribe")
async def api_transcribe(
    file: UploadFile = File(...),
    language: str = "",
    engine: KBPEngine = Depends(get_engine),
):
    """Transcribe an uploaded audio file."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in SUPPORTED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio format: {suffix}. "
            f"Supported: {', '.join(sorted(SUPPORTED_AUDIO_EXTENSIONS))}",
        )

    # Save to temp file — both local Whisper and OpenAI API need a file path
    content = await file.read()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        text = await engine.transcribe(tmp_path, language=language)
        provider_name = engine.transcriber_provider_name
        return TranscriptionResponse(text=text, provider=provider_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}") from e
    finally:
        tmp_path.unlink(missing_ok=True)
