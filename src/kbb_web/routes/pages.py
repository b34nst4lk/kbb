"""Full-page routes for the web adapter.

Each route renders a complete HTML page extending base.html.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from jinja2 import Environment

from kbb.engine import KBPEngine
from kbb.models import LLMProviderName, TranscriptionProviderName
from kbb_web.config import WebConfig
from kbb_web.dependencies import get_engine, get_templates, get_web_config

router = APIRouter()


@router.get("/")
def dashboard(
    engine: KBPEngine = Depends(get_engine),
    templates: Environment = Depends(get_templates),
):
    profile = engine.get_profile()
    entries = engine.get_knowledge_entries()
    log_paths = engine.get_all_daily_logs()
    pending = engine.get_pending_question()

    template = templates.get_template("pages/dashboard.html")
    html = template.render(
        profile_name=profile.name or "",
        knowledge_count=len(entries),
        log_count=len(log_paths),
        pending_question=pending,
    )
    return HTMLResponse(content=html)


@router.get("/profile")
def profile_page(
    engine: KBPEngine = Depends(get_engine),
    templates: Environment = Depends(get_templates),
):
    profile = engine.get_profile()
    raw_profile = engine.get_raw_profile()
    template = templates.get_template("pages/profile.html")
    html = template.render(profile=profile, raw_profile=raw_profile)
    return HTMLResponse(content=html)


@router.get("/daily")
def daily_question_page(
    engine: KBPEngine = Depends(get_engine),
    templates: Environment = Depends(get_templates),
):
    pending = engine.get_pending_question()
    template = templates.get_template("pages/daily/question.html")
    html = template.render(pending_question=pending)
    return HTMLResponse(content=html)


@router.get("/daily/logs")
def daily_logs_list(
    engine: KBPEngine = Depends(get_engine),
    templates: Environment = Depends(get_templates),
):
    log_paths = engine.get_all_daily_logs()
    template = templates.get_template("pages/daily/log_list.html")
    html = template.render(log_paths=log_paths)
    return HTMLResponse(content=html)


@router.get("/daily/logs/{date_str}")
def daily_logs_by_date(
    date_str: str,
    engine: KBPEngine = Depends(get_engine),
    templates: Environment = Depends(get_templates),
):
    try:
        d = date.fromisoformat(date_str)
    except ValueError:
        template = templates.get_template("pages/error.html")
        html = template.render(error=f"Invalid date: {date_str}")
        return HTMLResponse(content=html, status_code=400)
    logs = engine.find_daily_logs_by_date(d)
    template = templates.get_template("pages/daily/log.html")
    html = template.render(date_str=date_str, logs=logs)
    return HTMLResponse(content=html)


@router.get("/knowledge")
def knowledge_list(
    engine: KBPEngine = Depends(get_engine),
    templates: Environment = Depends(get_templates),
):
    entries = engine.get_knowledge_entries()
    template = templates.get_template("pages/knowledge/list.html")
    html = template.render(entries=entries)
    return HTMLResponse(content=html)


@router.get("/knowledge/import")
def knowledge_import_form(templates: Environment = Depends(get_templates)):
    template = templates.get_template("pages/knowledge/import_form.html")
    html = template.render()
    return HTMLResponse(content=html)


@router.get("/knowledge/{slug}")
def knowledge_detail(
    slug: str,
    engine: KBPEngine = Depends(get_engine),
    templates: Environment = Depends(get_templates),
):
    entry = engine.get_knowledge_entry(slug)
    if not entry:
        return HTMLResponse(content="Knowledge entry not found.", status_code=404)
    template = templates.get_template("pages/knowledge/detail.html")
    html = template.render(entry=entry)
    return HTMLResponse(content=html)


@router.get("/settings")
def settings_page(
    config: WebConfig = Depends(get_web_config),
    templates: Environment = Depends(get_templates),
):
    providers = [p.value for p in LLMProviderName]
    transcription_providers = [p.value for p in TranscriptionProviderName]
    template = templates.get_template("pages/settings.html")
    html = template.render(
        web_config=config,
        config_file_path=config.config_file_path,
        providers=providers,
        transcription_providers=transcription_providers,
    )
    return HTMLResponse(content=html)
