"""HTMX partial routes for the web adapter.

These return HTML fragments consumed by HTMX swaps.
LLM-powered actions show spinners during the request.
All LLM calls are wrapped in try/except so errors are shown inline.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from jinja2 import Environment

from kbb.engine import KBPEngine
from kbb.models import LLMProviderName, Question, QuestionTopic
from kbb_web.config import WebConfig, save_config
from kbb_web.dependencies import get_engine, get_templates, get_web_config

router = APIRouter()


@router.get("/question")
async def get_question(
    request: Request,
    engine: KBPEngine = Depends(get_engine),
    templates: Environment = Depends(get_templates),
):
    """Generate or retrieve today's question."""
    pending = engine.get_pending_question()
    if pending:
        question = pending
    else:
        try:
            question = await engine.generate_daily_question()
        except ValueError as e:
            # No profile or other validation error
            template = templates.get_template("partials/error_alert.html")
            html = template.render(error=str(e))
            return HTMLResponse(content=html)
        except Exception as e:
            # LLM API error
            template = templates.get_template("partials/error_alert.html")
            html = template.render(error=f"Failed to generate question: {e}")
            return HTMLResponse(content=html)
    template = templates.get_template("partials/question_card.html")
    html = template.render(question=question)
    return HTMLResponse(content=html)


@router.post("/response")
async def record_response(
    request: Request,
    question_text: str = Form(...),
    question_topic: str = Form(...),
    question_rationale: str = Form(...),
    response: str = Form(...),
    engine: KBPEngine = Depends(get_engine),
    templates: Environment = Depends(get_templates),
):
    """Record a response to a daily question."""
    question = Question(
        text=question_text,
        topic=QuestionTopic(question_topic),
        rationale=question_rationale,
    )
    try:
        log = await engine.record_response(question, response)
    except Exception as e:
        template = templates.get_template("partials/error_alert.html")
        html = template.render(error=f"Failed to record response: {e}")
        return HTMLResponse(content=html)
    template = templates.get_template("partials/response_result.html")
    html = template.render(log=log, date_str=date.today().isoformat())
    return HTMLResponse(content=html)


@router.get("/profile-editor")
def profile_editor(
    request: Request,
    engine: KBPEngine = Depends(get_engine),
    templates: Environment = Depends(get_templates),
):
    """Return the inline profile editor partial."""
    raw_profile = engine.get_raw_profile()
    template = templates.get_template("partials/profile_editor.html")
    html = template.render(raw_profile=raw_profile)
    return HTMLResponse(content=html)


@router.get("/profile-view")
def profile_view(
    request: Request,
    engine: KBPEngine = Depends(get_engine),
    templates: Environment = Depends(get_templates),
):
    """Return the profile view partial (used by Cancel button in editor)."""
    profile = engine.get_profile()
    raw_profile = engine.get_raw_profile()
    template = templates.get_template("partials/profile_view.html")
    html = template.render(profile=profile, raw_profile=raw_profile, success=False)
    return HTMLResponse(content=html)


@router.post("/profile")
async def save_profile(
    request: Request,
    raw_text: str = Form(...),
    engine: KBPEngine = Depends(get_engine),
    templates: Environment = Depends(get_templates),
):
    """Save profile text and return the profile view with success message."""
    try:
        profile = await engine.setup_profile_from_text(raw_text)
    except Exception as e:
        # Re-render the editor with the error so the user doesn't lose their text
        template = templates.get_template("partials/profile_editor.html")
        html = template.render(raw_profile=raw_text, error=f"Failed to save profile: {e}")
        return HTMLResponse(content=html)
    raw_profile = engine.get_raw_profile()
    template = templates.get_template("partials/profile_view.html")
    html = template.render(profile=profile, raw_profile=raw_profile, success=True)
    return HTMLResponse(content=html)


@router.post("/profile-refresh")
async def refresh_profile(
    request: Request,
    engine: KBPEngine = Depends(get_engine),
    templates: Environment = Depends(get_templates),
):
    """Re-parse the profile via LLM."""
    try:
        profile = await engine.refresh_profile()
    except ValueError as e:
        template = templates.get_template("partials/error_alert.html")
        html = template.render(error=str(e))
        return HTMLResponse(content=html)
    except Exception as e:
        template = templates.get_template("partials/error_alert.html")
        html = template.render(error=f"Failed to refresh profile: {e}")
        return HTMLResponse(content=html)
    raw_profile = engine.get_raw_profile()
    template = templates.get_template("partials/profile_view.html")
    html = template.render(profile=profile, raw_profile=raw_profile, success=True)
    return HTMLResponse(content=html)


@router.post("/knowledge/import")
async def import_knowledge(
    request: Request,
    title: str = Form(...),
    content: str = Form(...),
    topic: str = Form("general"),
    engine: KBPEngine = Depends(get_engine),
    templates: Environment = Depends(get_templates),
):
    """Import knowledge from text input."""
    try:
        entry = await engine.import_knowledge_from_text(
            title=title,
            content=content,
            topic=QuestionTopic(topic),
        )
    except Exception as e:
        template = templates.get_template("partials/error_alert.html")
        html = template.render(error=f"Failed to import: {e}")
        return HTMLResponse(content=html)
    template = templates.get_template("partials/knowledge_card.html")
    html = template.render(entry=entry)
    return HTMLResponse(content=html)


@router.get("/knowledge")
def knowledge_list_partial(
    request: Request,
    engine: KBPEngine = Depends(get_engine),
    templates: Environment = Depends(get_templates),
):
    """Return knowledge list fragment."""
    entries = engine.get_knowledge_entries()
    template = templates.get_template("partials/knowledge_list.html")
    html = template.render(entries=entries)
    return HTMLResponse(content=html)


@router.get("/logs")
def logs_by_date(
    request: Request,
    date: str = "",
    engine: KBPEngine = Depends(get_engine),
    templates: Environment = Depends(get_templates),
):
    """Return daily logs for a date as a fragment."""
    from datetime import date as date_type

    if date:
        d = date_type.fromisoformat(date)
    else:
        d = date_type.today()
    logs = engine.find_daily_logs_by_date(d)
    template = templates.get_template("partials/log_list.html")
    html = template.render(logs=logs)
    return HTMLResponse(content=html)


@router.post("/settings")
def save_settings(
    request: Request,
    data_dir: str = Form(...),
    llm_provider: str = Form(...),
    llm_model: str = Form(...),
    llm_base_url: str = Form(""),
    daily_log_time: str = Form("09:00"),
    port: str = Form("8199"),
    config: WebConfig = Depends(get_web_config),
    templates: Environment = Depends(get_templates),
):
    """Save settings to config file."""
    config.data_dir = Path(data_dir).expanduser()
    if not config.data_dir.is_absolute():
        config.data_dir = config.data_dir.resolve()
    config.llm_provider = LLMProviderName(llm_provider)
    config.llm_model = llm_model
    config.llm_base_url = llm_base_url
    config.daily_log_time = daily_log_time
    config.port = int(port)

    config_path = save_config(config)
    template = templates.get_template("partials/settings_saved.html")
    html = template.render(config_path=config_path)
    return HTMLResponse(content=html)
