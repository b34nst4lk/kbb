"""FastAPI dependency injection for the web adapter.

Provides access to the engine, config, and template engine
via Depends() in route handlers.
"""

from __future__ import annotations

from fastapi import Request
from jinja2 import Environment

from kbb.engine import KBPEngine
from kbb_web.config import WebConfig


def get_engine(request: Request) -> KBPEngine:
    """Get the KBPEngine instance from app state."""
    return request.app.state.engine


def get_web_config(request: Request) -> WebConfig:
    """Get the WebConfig instance from app state."""
    return request.app.state.web_config


def get_templates(request: Request) -> Environment:
    """Get the Jinja2 Environment instance from app state."""
    return request.app.state.templates
